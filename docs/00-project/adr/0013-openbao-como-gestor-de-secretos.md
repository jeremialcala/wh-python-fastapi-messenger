# ADR-0013: OpenBao como gestor de secretos y controlador central de claves

* **Estado:** accepted
* **Fecha:** 2026-10-12
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 02-design
* **Versión:** 0.1.0
* **ID:** ADR-0013
* **Supersede:** —
* **Controles OWASP afectados:** A04 (custodia de claves), A02 (configuración del gestor), A09 (registro de cada uso de una clave), A01 (qué servicio puede usar qué clave)

Aceptada el 2026-10-12 y desplegada ese mismo día en el servidor con el nombre de **Andvari**. Su proyecto de
despliegue vive en un repositorio propio, `andvari`; este documento registra la decisión y lo que el gateway
puede esperar de él.

## Contexto

[ADR-0010](0010-clave-de-cifrado-de-datos-por-cliente.md) fijó que cada cliente tiene una clave de datos, guardada
en su registro envuelta con una **clave maestra**, y dejó abierto dónde vive esa clave maestra. La opción de
partida era la configuración del servidor: un valor en el `.env` del gateway.

Eso tiene dos defectos. La clave maestra estaría en el fichero de configuración y en la memoria del gateway, de modo
que quien lea uno u otro se la lleva. Y no habría registro de cuándo se usa ni forma de rotarla sin tocar el
gateway. Además el motor de respuestas y los servicios que vengan necesitarán lo mismo.

Datos del servidor, comprobados el 2026-10-12: no tiene TPM, el disco no está cifrado y no tiene UPS, así que
arranca sin nadie delante después de cada corte de luz.

## Decisión

**Un OpenBao propio es el gestor de secretos de la plataforma y el único sitio donde vive la clave maestra.** Ningún
servicio la ve: le piden a OpenBao que la use.

1. **Infraestructura compartida, con el nombre de Andvari.** Se despliega como Hermod: un proyecto compose
   propio en el servidor, con su repositorio, fuera del ciclo de despliegue continuo, en una red Docker privada y
   sin puertos publicados.
2. **Motor Transit, con una clave maestra derivada por cliente.** Una clave `clientes`, de tipo `aes256-gcm96`, con
   derivación activada. El contexto de derivación es el identificador del cliente, así que la clave de datos de un
   cliente no se puede abrir con el contexto de otro.
3. **El gateway solo hace dos operaciones.** Pedir una clave de datos nueva al registrar un cliente
   (`transit/datakey/plaintext/clientes`) y abrir una ya envuelta (`transit/decrypt/clientes`). Guarda la clave
   envuelta en el registro del cliente y mantiene la clave abierta en memoria unos minutos.
4. **Un AppRole por servicio, con política mínima.** El gateway no puede leer la configuración de la clave, rotarla,
   exportarla ni listar nada.
5. **Auditoría declarada en la configuración**, hacia la salida estándar, que Docker conserva y rota.
6. **Almacenamiento integrado (Raft) de un solo nodo**, en un volumen, con una copia diaria.
7. **Arranque con sello estático.** La clave que abre OpenBao al arrancar es un fichero de 32 bytes en el servidor,
   legible solo por la cuenta de sistema de Andvari. Es lo que permite arrancar sin intervención. Cuando entre el
   primer cliente externo se sustituye por un servicio de claves externo al servidor.
8. **TLS entre los servicios y OpenBao**, con una autoridad de certificación privada creada en la instalación.
9. **Una sola clave de recuperación**, que custodia el operador fuera del servidor.

### Configuración

La instalada en el servidor (`config/andvari.hcl` del repositorio `andvari`):

```hcl
ui            = false
disable_mlock = true
api_addr      = "https://andvari:8200"
cluster_addr  = "https://andvari:8201"

storage "raft" {
  path    = "/openbao/file"
  node_id = "andvari-1"
}

listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_cert_file = "/openbao/tls/andvari.crt"
  tls_key_file  = "/openbao/tls/andvari.key"
}

seal "static" {
  current_key_id = "sello-1"
  current_key    = "file:///openbao/secrets/sello.key"
}

audit "file" "stdout" {
  description = "Auditoria a la salida estandar"
  options {
    file_path = "stdout"
  }
}
```

El contenedor corre con una cuenta de sistema propia, sin capacidades, con la raíz de solo lectura y con un tope
de 256 MB de memoria. Solo escribe en `/var/lib/andvari`.

Política del gateway:

```hcl
path "transit/datakey/plaintext/clientes" {
  capabilities = ["update"]
}

path "transit/decrypt/clientes" {
  capabilities = ["update"]
}
```

Imagen: `openbao/openbao:2.7.1@sha256:6d2b93856e3fcf7b18ad855a0b51eaba474dc8b79cf554379ea32034797d2acf`.

### Lo que se comprobó

Primero con un OpenBao desechable en local, y después sobre el Andvari instalado en el servidor, el 2026-10-12:

| Comprobación | Resultado |
|---|---|
| Inicialización con sello estático | Devuelve claves de recuperación, no de desellado, y queda abierto sin intervención |
| Reinicio del contenedor | Vuelve abierto y sano por sí solo |
| Arranque con otra clave de sello (solo en local) | Se queda sellado y lo dice en el log |
| Clave de datos pedida con el contexto del cliente A | 32 bytes; se abre con el contexto de A |
| Abrir esa clave con el contexto del cliente B | Rechazado |
| Exportar o borrar la clave maestra (solo en local) | Rechazado |
| Rotar la clave maestra (solo en local) | Lo envuelto con la versión anterior se sigue abriendo |
| Token con la política del gateway (solo en local) | Puede pedir y abrir claves; no puede leer la clave, rotarla ni listar nada |
| Auditoría | Registra cada operación; el token raíz no aparece en claro en el log |
| Activar la auditoría por API | Rechazado: OpenBao exige declararla en la configuración |
| TLS desde otro contenedor de la red | Conecta con la autoridad de certificación; sin ella, o sin TLS, es rechazado |
| Endurecimiento del contenedor | Cuenta propia, sin capacidades, raíz de solo lectura y ningún puerto en el servidor |
| Memoria | 49 MiB tras la configuración |

No se probó: el arranque tras un corte de luz real, la restauración desde una copia, ni la integración con el
gateway, que no existe todavía.

## Alternativas consideradas

| Opción | Pros | Contras | Riesgo de seguridad |
|---|---|---|---|
| **OpenBao propio** | Software abierto y probado para esto; una pieza para todos los servicios; rotación y auditoría incluidas | Un servicio más que operar; el gateway pasa a depender de él | La raíz de confianza sigue en el servidor mientras el sello sea un fichero |
| Clave maestra en la configuración del gateway | Nada que operar | La clave está en un fichero y en la memoria del gateway; sin registro de uso; cada servicio la repetiría | Quien lea el `.env` se lleva la clave |
| Un servicio de claves escrito a medida | A la medida de las convenciones propias | Hay que resolver bien el almacenamiento sellado, la autenticación, la auditoría, la rotación y el respaldo | Alto: es reimplementar un gestor de claves |
| Un servicio de claves gestionado en la nube, usado directamente | La raíz de confianza queda fuera del servidor; sin nada que operar | Cada operación depende de internet; coste por uso; otro proveedor | El más fuerte frente a un compromiso del servidor |

## Consecuencias

- Positivas:
  - La clave maestra no está en el gateway ni en su configuración. No se puede exportar ni borrar.
  - Cada uso de una clave queda registrado con quién lo hizo, lo que da la base para la auditoría por cliente (RS14).
  - La baja de un cliente y la rotación de la clave maestra tienen un único sitio.
- Negativas / deuda asumida:
  - **El sello estático deja la raíz de confianza en el mismo disco que protege.** La documentación de OpenBao lo
    advierte y solo lo recomienda cuando hay otra fuente de confianza. Se acepta para la fase de un solo operador
    porque el servidor no tiene TPM y debe arrancar solo; no protege frente a quien sea root en el servidor.
  - **No elimina el secreto del gateway, lo cambia.** El gateway sigue guardando una credencial, la de su AppRole.
    Quien la robe puede pedir a OpenBao que abra claves mientras no se revoque, pero no puede llevarse la clave
    maestra, y cada petición queda registrada.
  - **Dependencia nueva.** Si OpenBao no responde, el gateway no puede abrir la clave de un cliente que no tenga en
    memoria: responde `503` y Meta reintenta, igual que cuando falla el broker.
  - Hay que custodiar fuera del servidor las claves de recuperación y una copia de la clave de sello. Sin la clave
    de sello, las copias del almacenamiento no se pueden abrir.
- Impacto en threat model: reduce la amenaza T15 para la clave maestra. Añade dos situaciones que el threat model
  debe recoger al aceptar este ADR: que OpenBao caiga o quede sellado, y que se filtre la clave de sello.

## Abierto

- **Copia de seguridad.** No hay todavía copia del almacenamiento ni de la clave de sello fuera del servidor. Debe
  existir antes de que ningún servicio cifre datos reales: perder la clave de sello es perder la clave maestra.
- **El token raíz sigue vigente.** Está, junto con la clave de recuperación, en el fichero que dejó la
  instalación; el operador debe moverlo fuera del servidor. Queda por decidir si se revoca y se regenera solo
  cuando haga falta.
- **Sello externo.** Cuándo y con qué servicio se sustituye el sello estático.
- **Tiempo en memoria** de la clave de datos abierta en el gateway.
- **Secretos de los servicios.** Mover a Andvari los que hoy viven en ficheros `.env` (credenciales de MongoDB y de
  RabbitMQ, App Secret) queda para una segunda fase.
- **Vigilancia.** Que un Andvari sellado o caído avise.

## Referencias

- [Sello estático — OpenBao](https://openbao.org/docs/configuration/seal/static/)
- [Almacenamiento integrado (Raft) — OpenBao](https://openbao.org/docs/configuration/storage/raft/)
- [Dispositivos de auditoría en la configuración — OpenBao](https://openbao.org/docs/configuration/audit/)
- [API del motor Transit — OpenBao](https://openbao.org/api-docs/secret/transit)
