# ADR-0019: NATS JetStream es el bus de eventos entre el gateway y los workers del motor

* **Estado:** proposed
* **Fecha:** 2026-10-18
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 02-design
* **Versión:** 0.1.0
* **ID:** ADR-0019
* **Supersede:** — (sustituye a RabbitMQ, que decidió [ADR-0006](0006-publicacion-confirmada-y-503.md), cuando el motor
  lea del bus nuevo; [ADR-0011](0011-contrato-de-la-cola.md) pasa a su versión 2 en el AsyncAPI 2.0.0)
* **Controles OWASP afectados:** A01 (cada servicio solo publica y consume lo suyo), A04 (datos personales en el bus y
  en disco), A08 (integridad entre servicios), A10 (duplicados, desorden y pérdida)

Propuesta para el Gate 1 del refactor ([plan](../plan-topologia-de-workers.md), paso 2). Decisión D1 del 2026-10-18.

## Contexto

Hoy el gateway publica cada mensaje en la cola `llm` de Hermod, un RabbitMQ 4.3 en midgard, y responde `200` a Meta
cuando el broker confirma ([ADR-0006](0006-publicacion-confirmada-y-503.md)). La topología de ocho workers del plan
necesita un bus con enrutamiento por sujetos entre muchos servicios. El 2026-10-18 Jeremi eligió NATS JetStream (D1),
en contra de mi recomendación, que era seguir con RabbitMQ. El análisis de origen no compara los dos, y casi todo lo
que pide (enrutamiento jerárquico, entrega al menos una vez, mensajes en vuelo acotados, plazo de confirmación) lo
cubre también RabbitMQ. Lo que distingue a JetStream aquí es la deduplicación al publicar, el almacén clave-valor que
usará el contexto ([ADR-0017](0017-contexto-de-conversacion-e-historial.md)) y un servidor más ligero.

Hechos comprobados en la documentación de NATS el 2026-10-18:

- **La última versión menor es la 2.14** (abril de 2026). La 2.14.3 corrige CVE-2026-58208, que puede tumbar un
  servidor JetStream que solo escucha por WebSocket.
- **La deduplicación al publicar** rechaza un segundo mensaje con el mismo `Nats-Msg-Id` durante una ventana de 2
  minutos por defecto.
- **Por defecto, el almacén en fichero se sincroniza con el disco cada 2 minutos** (`sync_interval: 2m`). La propia
  documentación advierte que, sin réplicas, un fallo del sistema operativo puede perder mensajes ya confirmados. El
  análisis de Jepsen sobre la 2.12.1 lo reprodujo con cortes de luz. Con `sync_interval: always` el servidor hace
  `fsync` en cada escritura, a costa del rendimiento.
- **El orden por clave entre varios consumidores** se consigue repartiendo los sujetos en particiones fijas con la
  función `partition` del mapeo de sujetos, y consumiendo cada partición con un solo mensaje en vuelo
  (`max_ack_pending: 1`). Desde la 2.11 hay además grupos de prioridad con cliente fijado.
- **Los permisos son por usuario y por sujeto**, para publicar y para suscribirse. Con una lista `allow`, todo lo
  demás queda denegado.
- **JetStream puede cifrar el almacén en disco** con una clave del servidor (`encryption_key`).

## Decisión

**NATS JetStream 2.14, con la 2.14.3 como mínimo, en un solo servidor: Bifröst**
([ADR-0020](0020-placement-de-bifrost.md)).

### Durabilidad

- **`sync_interval: always`.** Es un solo nodo, sin réplicas, en un servidor que pierde la luz a menudo. Con el
  valor por defecto, un mensaje que el webhook ya confirmó a Meta podría perderse sin que Meta lo reenvíe.
  Cuánto cuesta el `fsync` en el disco de midgard se mide en I0, antes de que el webhook dependa de ello.
- **El webhook responde `200` solo con el acuse de JetStream** (`PubAck`), igual que hoy con la confirmación de
  RabbitMQ. Si no llega, responde `503` y Meta reenvía.

### Streams

| Stream | Sujetos | Quién publica | Quién consume | Retención |
|---|---|---|---|---|
| `WEBHOOK` | `webhook.meta.whatsapp`, `.messenger` e `.instagram` | El webhook: cada mensaje verificado, tal como lo firmó Meta | El worker de ingesta | Cola de trabajo (se borra al confirmarse), y 24 horas como máximo (RNF05) |
| `MENSAJES` | `gateway.message.<partición>.<botId>.<contactId>` | El worker de ingesta: el mensaje identificado | Los workers del motor, una partición por consumidor | 24 horas como máximo |
| `RESPUESTAS` | `engine.reply.sent.<botId>` | El notificador del motor, cuando Meta acepta un envío | El worker de ingesta, para el historial | 24 horas como máximo |
| `SUPRESIONES` | `gateway.contact.erased`, `gateway.bot.erased`, `gateway.client.erased` | La API de gestión | El coordinador, para borrar el contexto | 7 días |

Los nombres exactos, los campos y los esquemas se fijan en el AsyncAPI 2.0.0, que es el siguiente entregable de este
gate.

### Duplicados y orden

- **`Nats-Msg-Id` = bot e identificador de Meta.** Así una publicación repetida del propio gateway se descarta en
  JetStream.
- **Los reintentos de Meta duran días, no minutos:** 7 días en WhatsApp, 36 horas en Instagram. Esos duplicados los
  detiene el índice único del historial ([ADR-0017](0017-contexto-de-conversacion-e-historial.md)), no el bus.
- **El orden por conversación** sale de la clave en el sujeto: la ingesta publica en la partición que le toca a cada
  bot y contacto. Cada partición la atiende un solo consumidor con un mensaje en vuelo. Las particiones se fijan en
  16, y cambiarlas obliga a vaciar el stream.

### Seguridad

- **Un usuario por servicio** (RS20), con una lista `allow` de sus sujetos para publicar y para suscribirse, más los
  sujetos de la API de JetStream que necesita, y nada más. Sus credenciales viven en Andvari
  ([ADR-0013](0013-openbao-como-gestor-de-secretos.md)).
- **TLS en todas las conexiones**, con una CA propia de Bifröst.
- **Almacén cifrado en disco** con `encryption_key`, también guardada en Andvari. Por el bus pasa el contenido de
  los mensajes, que es dato restringido.

## Alternativas consideradas

| Opción | Por qué no |
|---|---|
| Seguir con RabbitMQ (Hermod) | Era mi recomendación: ya está desplegado y cubre el enrutamiento por *topic*, las confirmaciones y el `prefetch`. Jeremi eligió NATS por la deduplicación al publicar, el almacén clave-valor y la ligereza |
| Redis Streams | Persistencia más débil y sin permisos por sujeto. Habría que montarlo y operarlo igual |
| Kafka | Demasiado para dos núcleos y 7,6 GB: necesita más memoria y más operación que el resto de la plataforma junta |

## Consecuencias

- **La deduplicación de NATS no basta sola.** Hace falta el índice único del historial y que el motor no responda dos
  veces al mismo identificador.
- **`sync_interval: always` puede encarecer el acuse** en un disco mecánico de 2013. Si en I0 no cabe en el plazo
  del webhook (RNF01), la alternativa es un SSD en midgard, no volver al valor por defecto.
- **Un solo nodo:** si Bifröst cae, el webhook responde `503` y Meta reenvía, como hoy con Hermod. No hay réplicas.
- **El motor tiene que cambiar:** leer de NATS el contrato v2, consumir por particiones y deduplicar. Hasta que lo
  haga, el gateway sigue publicando en Hermod, y el paso de uno a otro necesita su propio plan.
- **Hermod se retira** cuando el motor deje de leer la cola `llm`.
- **La clasificación de datos** suma el bus y sus credenciales, y el threat model, sus fronteras: cada servicio con
  su usuario y el almacén en disco.

## Condiciones de revisión

- El `fsync` en cada escritura no cabe en el plazo del webhook.
- Se necesita alta disponibilidad: entonces, un clúster de tres nodos, que no cabe en midgard.
- El motor no puede leer NATS en el plazo del refactor.
