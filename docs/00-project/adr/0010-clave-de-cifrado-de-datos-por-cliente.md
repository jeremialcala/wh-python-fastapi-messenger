# ADR-0010: Cada cliente tiene una clave de cifrado de datos, custodiada por la plataforma

* **Estado:** accepted
* **Fecha:** 2026-10-12
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 02-design
* **Versión:** 0.1.0
* **ID:** ADR-0010
* **Supersede:** —
* **Controles OWASP afectados:** A04 (cifrado en reposo y custodia de claves), A01 (separación entre clientes)

Aceptada el 2026-10-12.

## Contexto

El requisito es que los números de teléfono se guarden cifrados con la clave del cliente (RS05), y lo mismo los
tokens de Meta y el App Secret (RS06). Hoy todo está en claro.

Hay una restricción que decide el diseño: el gateway necesita **leer** el número para encontrar al contacto cuando
llega un mensaje, y el motor de respuestas lo necesita para contestar. Una clave que solo tuviera el cliente no lo
permitiría. Por eso la clave con la que el cliente firma
([ADR-0005](0005-jwt-firmado-por-el-cliente-dentro-del-jwe.md)) no sirve para esto.

## Decisión

**Cifrado en sobre, con una clave por cliente.**

1. Al registrar un cliente, la plataforma genera para él una **clave de datos** (AES-256).
2. La clave de datos se guarda en el registro del cliente **envuelta** (cifrada) con una **clave maestra** de la
   plataforma.
3. La clave maestra vive fuera de la base de datos: en la configuración del servidor al principio, en un gestor de
   secretos cuando lo haya.
4. Los campos sensibles de un cliente se cifran con su clave de datos, con cifrado autenticado (AES-256-GCM) y un
   valor aleatorio distinto en cada cifrado.

**Campos cifrados.** El número del contacto, el número del bot, los tokens de Meta, el App Secret y el token de
verificación.

**Búsqueda por número sin guardarlo en claro.** Junto al número cifrado se guarda un **índice ciego**: un HMAC-SHA-256
del número normalizado, con una clave derivada de la clave de datos del cliente. El gateway busca por el índice,
no por el número. Dos clientes con el mismo contacto producen índices distintos.

**Borrado.** Destruir la clave de datos de un cliente deja ilegibles todos sus datos cifrados, también los que
queden en respaldos. Es lo que da cumplimiento práctico a la baja de un cliente (RF10).

> **Corregido el 2026-10-13 por [ADR-0014](0014-supresion-en-respaldos-por-caducidad.md).** Tal como quedó
> construido, esto no se cumple en los respaldos: la clave envuelta se guarda en la misma base que los datos, y
> la clave maestra, una sola derivada por cliente, la sigue abriendo. La baja borra los datos y la clave envuelta
> de la base en uso; en los respaldos, la supresión se cumple cuando caducan, a los 365 días como mucho.

## Alternativas consideradas

| Opción | Pros | Contras | Riesgo de seguridad |
|---|---|---|---|
| **Clave por cliente generada y custodiada por la plataforma** | El servicio puede leer lo que necesita; una fuga de la base sola no revela nada; el borrado por destrucción de clave alcanza a los respaldos | El operador, con la clave maestra y la base, puede descifrar | Depende de proteger la clave maestra |
| El cliente aporta y custodia su clave en su propio gestor | El operador no puede descifrar sin el cliente | Cada mensaje dependería del gestor del cliente; complejidad alta para ambos | El más fuerte frente al operador |
| Cifrado de campos del propio MongoDB en el cliente | Lo mantiene el proveedor; permite igualdad sobre campos cifrados | Requiere una librería nativa adicional y ata el cifrado a MongoDB; sin probar con el ODM que usa el código | Equivalente si se configura bien |
| Una sola clave para todos los clientes | Lo más simple | No es "la clave del cliente"; no permite borrar a un cliente destruyendo su clave | Una clave comprometida expone a todos |

## Consecuencias

- Positivas: una copia de la base, un volcado o un respaldo no exponen números ni credenciales (AB03). La baja de
  un cliente es verificable en la base en uso; en los respaldos depende de su caducidad (ADR-0014).
- Negativas / deuda asumida:
  - **"Bajo la llave del cliente" significa aquí una clave por cliente, no una clave que solo tenga el cliente.**
    El operador puede descifrar, porque el servicio lo necesita para funcionar. Hay que decírselo así al cliente.
  - Hay que migrar los datos que ya existen en claro.
  - El índice ciego revela que dos registros del mismo cliente tienen el mismo número. Se acepta.
  - Perder la clave maestra es perder todos los datos cifrados: necesita su propio respaldo, separado de la base.
- Impacto en threat model: cubre la fuga de la base (T3). La supresión incompleta en respaldos (T17) no la cubre
  el cifrado, sino la caducidad de los respaldos (ADR-0014). La clave maestra se suma a los secretos del servidor
  (T15).

## Abierto

- Dónde vive la clave maestra y cómo se rota: resuelto en
  [ADR-0013](0013-openbao-como-gestor-de-secretos.md), un OpenBao propio como controlador central de claves.
- Si el identificador de Messenger del contacto (PSID) se cifra también. El requisito habla de números.
