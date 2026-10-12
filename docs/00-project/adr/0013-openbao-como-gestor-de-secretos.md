# ADR-0013: OpenBao como gestor de secretos y controlador central de claves

* **Estado:** proposed
* **Fecha:** 2026-10-12
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 02-design
* **Versión:** 0.1.0
* **ID:** ADR-0013
* **Supersede:** —
* **Controles OWASP afectados:** A04 (custodia de claves), A02 (configuración del gestor), A09 (registro de cada uso de una clave), A01 (qué servicio puede usar qué clave)

Está decidido que el gestor es OpenBao. El resto de este documento, es decir, cómo se configura y cómo se arranca,
es una propuesta pendiente de aprobación, comprobada en una prueba de concepto.

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

1. **Infraestructura compartida.** OpenBao se despliega como Hermod: un proyecto compose propio en el servidor,
   fuera del ciclo de despliegue continuo, en una red Docker privada y sin puertos hacia la LAN.
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
   legible solo por root. Es lo que permite arrancar sin intervención. Cuando entre el primer cliente externo se
   sustituye por un servicio de claves externo al servidor.
8. **TLS entre los servicios y OpenBao**, con una autoridad de certificación privada creada en la instalación.

### Configuración

Es la configuración de la prueba con OpenBao 2.7.1, con dos diferencias que no se probaron: el TLS, que en la
prueba estaba desactivado, y las direcciones de `api_addr` y `cluster_addr`, que allí eran las de loopback.

```hcl
ui            = false
disable_mlock = true
api_addr      = "https://openbao:8200"
cluster_addr  = "https://openbao:8201"

storage "raft" {
  path    = "/openbao/file"
  node_id = "nodo-1"
}

listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_cert_file = "/openbao/tls/openbao.crt"
  tls_key_file  = "/openbao/tls/openbao.key"
}

seal "static" {
  current_key_id = "20261012-1"
  current_key    = "file:///openbao/secrets/unseal.key"
}

audit "file" "stdout" {
  description = "Auditoria a la salida estandar: la recoge y la rota Docker."
  options {
    file_path = "stdout"
  }
}
```

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

Con un OpenBao desechable en local, el 2026-10-12:

| Comprobación | Resultado |
|---|---|
| Inicialización con sello estático | Devuelve claves de recuperación, no de desellado, y queda abierto sin intervención |
| Reinicio del contenedor | Vuelve abierto solo y sigue abriendo las claves anteriores |
| Arranque con otra clave de sello | Se queda sellado y lo dice en el log |
| Clave de datos pedida con el contexto del cliente A | 32 bytes; se abre con el contexto de A |
| Abrir esa clave con el contexto del cliente B, o sin contexto | Rechazado |
| Exportar o borrar la clave maestra | Rechazado |
| Rotar la clave maestra | Las claves envueltas con la versión anterior se siguen abriendo; las nuevas salen con la versión 2 |
| Token del gateway: pedir y abrir claves | Permitido |
| Token del gateway: leer la clave, rotarla, listar motores, leer su política | Denegado |
| Auditoría | Registra petición y respuesta; la clave de datos y el token aparecen como HMAC, nunca en claro |
| Activar la auditoría por API | Rechazado: OpenBao exige declararla en la configuración |
| Memoria en reposo | 34 MiB |
| Copia del almacenamiento (`raft snapshot save`) | Funciona |

No se probó: el TLS, el despliegue en el servidor, ni la integración con el gateway, que no existe todavía.

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

Requiere decisión antes de aceptar este ADR:

- **Alcance y nombre.** Si es infraestructura de toda la plataforma, con su propio repositorio y su nombre, como
  Hermod; este ADR lo da por supuesto.
- **Modo de sello.** Fichero en el servidor ahora y servicio externo después, como se propone, o directamente otra
  opción.
- **TLS desde el primer día**, como se propone, o red Docker privada sin TLS en la primera fase, que es como está
  Hermod.
- **Claves de recuperación.** Cuántas partes y dónde se guardan. Con un solo operador, repartirlas entre personas
  no es posible.
- **Tiempo en memoria** de la clave de datos abierta en el gateway.
- **Secretos de los servicios.** Mover a OpenBao los que hoy viven en ficheros `.env` (credenciales de MongoDB y de
  RabbitMQ, App Secret) es el paso natural de un gestor de secretos, y queda para una segunda fase.

## Referencias

- [Sello estático — OpenBao](https://openbao.org/docs/configuration/seal/static/)
- [Almacenamiento integrado (Raft) — OpenBao](https://openbao.org/docs/configuration/storage/raft/)
- [Dispositivos de auditoría en la configuración — OpenBao](https://openbao.org/docs/configuration/audit/)
- [API del motor Transit — OpenBao](https://openbao.org/api-docs/secret/transit)
