# ADR-0003: El `bot_id` identifica cada mensaje y es la llave con la que el motor pide la configuración

* **Estado:** accepted
* **Fecha:** 2026-10-12
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 00-project
* **Versión:** 0.1.0
* **ID:** ADR-0003
* **Supersede:** —
* **Controles OWASP afectados:** A01 (el identificador no autoriza), A07 (credencial del motor ante el gateway), A08 (integridad del mensaje entre servicios)

## Contexto

[ADR-0002](0002-el-motor-entrega-las-respuestas.md) dejó decidido que el motor de respuestas envía la respuesta al
usuario final, y abierta la pregunta de cómo obtiene lo que necesita para hacerlo: las reglas del bot, sus
herramientas y su token de Meta.

Cada notificación llega al gateway en la URL de un bot, `/chat/{bot_id}`, y solo se procesa si su firma
`X-Hub-Signature-256` es válida. El webhook crudo de Meta no dice a qué bot va dirigido: ese dato solo existe en la
URL, y el gateway lo añade al mensaje que publica.

## Decisión

**Cada mensaje de la cola va identificado por su `bot_id` y ha pasado la verificación de firma del webhook. Con ese
`bot_id`, el motor le pide al gateway la configuración que necesita para generar y enviar la respuesta.**

El gateway es la única fuente de la configuración de un bot. El motor no guarda copia propia ni lee la base del
gateway.

## Alternativas consideradas

| Opción | Pros | Contras | Riesgo de seguridad |
|---|---|---|---|
| **El motor pide la configuración al gateway por `bot_id`** | Una sola fuente de verdad; el motor no conoce el esquema de la base; el acceso se puede acotar, registrar y revocar en un único sitio | El gateway pasa a ser dependencia del motor en cada respuesta | El punto de control es uno: la credencial del motor ante el gateway |
| El motor lee la base del gateway | Sin llamada intermedia | Acopla al motor con el esquema y con el cifrado por cliente; dos servicios con credenciales de la base | Más superficie y sin registro por acceso |
| La configuración viaja dentro de cada mensaje | El motor no depende del gateway | Los tokens de Meta quedarían en la cola, en claro y persistidos | Alto: multiplica las copias del dato más sensible |

## Consecuencias

- Positivas: el motor queda sin estado propio sobre los bots, y dar de baja o rotar la credencial de un bot tiene
  efecto inmediato.
- Negativas / deuda asumida:
  - **El sobre del gateway es el contrato de la cola para los dos canales.** Solo él lleva el `bot_id`. El motor
    debe aceptarlo también para Messenger, donde hoy exige el webhook crudo, y conservar el `bot_id`, que hoy
    descarta (RF12).
  - El gateway ya expone la configuración por bot (`/rules`, `/tools` e `/info`), pero bajo la clave única del
    operador. El motor necesita una credencial de servicio propia, de solo lectura (RS02, RS06).
  - El gateway debe estar disponible para que el motor responda. Conviene que el motor guarde la configuración en
    memoria por poco tiempo; el plazo es decisión del Gate 1.
- Impacto en threat model:
  - **El `bot_id` identifica, no autoriza.** Aparece en la URL pública del webhook y en la configuración de Meta de
    cada cliente, así que no es un secreto. Ninguna configuración puede entregarse solo por conocerlo (RS18).
  - La firma se verifica una vez, en el gateway. El motor confía en el mensaje porque la cola es privada y de
    acceso autenticado (RS08), no porque vuelva a verificar la firma.

## Abierto

Resuelto en [ADR-0004](0004-firma-en-el-webhook-jwe-en-el-resto.md): el motor se autentica ante el gateway con
JWE, como cualquier otro cliente registrado, y la firma del webhook no viaja con el mensaje. Queda por diseñar el
formato del token y el alcance de solo lectura del motor.

Resueltos los dos: el formato en [ADR-0009](0009-parametros-del-token-de-autenticacion.md) y el alcance en
[ADR-0016](0016-credencial-del-motor-por-cliente.md), con una clave del motor por cliente. Además del `bot_id`, el
mensaje lleva el cliente dueño del bot, para que el motor sepa cuál de sus claves usar.
