# ADR-0021: El webhook solo comprueba la firma y publica; la ingesta identifica al contacto

* **Estado:** proposed
* **Fecha:** 2026-10-18
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 02-design
* **Versión:** 0.1.0
* **ID:** ADR-0021
* **Supersede:** [ADR-0006](0006-publicacion-confirmada-y-503.md) y la tabla de [ADR-0015](0015-que-se-responde-a-meta.md),
  cuando se acepte. Lo demás de ADR-0015 sigue: el cuerpo no se lee antes de la firma, y lo firmado que no se
  entiende recibe `200`.
* **Controles OWASP afectados:** A04 (disponibilidad del webhook), A08 (integridad de lo que se publica), A10
  (fallos, duplicados y pérdida)

Propuesta para el Gate 1 del refactor ([plan](../plan-topologia-de-workers.md), R1). Decisión D2 del 2026-10-18.

## Contexto

Hoy el webhook hace todo antes de contestar a Meta:

- busca el bot;
- abre el App Secret con la clave del cliente;
- busca o crea el contacto, preguntando además a la Graph API en Messenger;
- publica en Hermod.

Con 60 ms de ida y vuelta a Atlas, un contacto nuevo de WhatsApp cuesta unos 300 ms solo de red, por encima de los
250 ms de mediana de RNF01. Cualquier fallo de la base o de Andvari acaba en un `503`, y Meta lo reintenta. En
Messenger, una hora de fallos da de baja la página.

El 2026-10-18 se decidió sacar la identificación del contacto del webhook (D2). El webhook ya corre aparte de la
gestión ([ADR-0018](0018-webhook-y-gestion-por-separado.md)), y el bus es NATS JetStream
([ADR-0019](0019-nats-jetstream-como-bus.md)).

## Decisión

### El webhook

1. **Comprueba la firma**, con el bot y su App Secret. Los dos se guardan en memoria, el bot 30 segundos (#29) y la
   clave de datos del cliente cinco minutos, así que casi siempre no cuesta ningún viaje.
2. **Lee la notificación y publica un evento por mensaje** en `webhook.meta.<canal>`. Cada evento lleva el
   identificador de Meta en `Nats-Msg-Id` y el contexto de traza (`traceparent`).
3. **Responde `200` cuando Bifröst acusa todos los eventos** de la notificación.

No escribe en la base ni llama a la Graph API.

| Situación | Respuesta a Meta |
|---|---|
| El cuerpo pasa de 3 MiB | `413` |
| Sin firma válida | `403`, sin leer el cuerpo |
| Bot inexistente | `404` |
| Firmado, pero no se entiende o es de un objeto que no se atiende | `200` y aviso en el log |
| Firmado, con mensajes incompletos entre otros que están bien | `200`; se publican los que están bien |
| No responden la base o Andvari al buscar el bot o abrir su App Secret | `503` |
| Bifröst no acusa algún evento | `503`. Meta reenvía la notificación entera, y lo ya publicado se descarta por `Nats-Msg-Id` si llega dentro de 2 minutos |

### El worker de ingesta

Es un servicio nuevo del gateway, de la misma imagen. Consume el stream `WEBHOOK` con confirmación explícita y, por
cada evento:

1. Comprueba en el historial si el mensaje ya se recibió, por bot e identificador de Meta. Si ya está, lo confirma
   sin hacer nada más: es un reintento de Meta.
2. Identifica o crea el contacto, como hoy, con la Graph API en Messenger e Instagram.
3. Guarda el mensaje en el historial ([ADR-0017](0017-contexto-de-conversacion-e-historial.md)).
4. Publica el mensaje identificado en la partición de su conversación (`gateway.message.<partición>.<bot>.<contacto>`).
5. Confirma el evento.

Si cae entre la publicación y la confirmación, el evento se reentrega y el paso 1 lo reconoce.

| Situación en la ingesta | Qué hace |
|---|---|
| No responden la base, Andvari o Bifröst | No confirma: el evento se reentrega con una espera creciente, hasta que caduca en el stream |
| La Graph API no da el perfil | Sigue sin el nombre, como hoy |
| El mensaje falla por sí mismo, o el bot ya no existe | Lo da por terminado y lo deja en el log |

## Alternativas consideradas

| Opción | Pros | Contras |
|---|---|---|
| **El webhook solo publica; la ingesta identifica** | El plazo del webhook ya no depende de Atlas ni de la Graph API; las caídas de la base las absorbe el bus | Un servicio más; si la base cae más tiempo del que guarda el stream, el mensaje se pierde, aunque Meta ya recibió `200` |
| Seguir identificando en el webhook (lo que hay) | Nada nuevo | Con un contacto nuevo no cabe en 250 ms, y una caída de la base da de baja las páginas de Messenger |
| Guardar la notificación en la base y procesarla después (outbox) | Sin bus en el camino | Vuelve a poner a Atlas, a 60 ms, en el plazo del webhook |

## Consecuencias

- **El plazo del webhook depende de Bifröst**, en una red Docker local, y del `fsync` en cada escritura. Se mide en I0
  y en I1.
- **Una caída de la base ya no la reintenta Meta, sino la ingesta.** Meta reintenta 7 días en WhatsApp. La ingesta
  solo reintenta mientras el evento siga en el stream `WEBHOOK`.
- **El stream `WEBHOOK` guarda 7 días**, lo mismo que reintenta Meta en WhatsApp. Lo decidió Jeremi el 2026-10-18,
  frente a las 24 horas que proponía esta ADR. Una caída de Atlas tiene así el mismo margen que antes, a cambio de
  que, mientras dura, los mensajes sin procesar esperen en el bus hasta una semana. En condiciones normales la
  ingesta los confirma en segundos y se borran. Gjallarhorn avisa en cuanto haya eventos sin confirmar de más de 15
  minutos.
- **Desaparece RD-05 en el webhook:** ya no tiene llamadas bloqueantes por cada mensaje, salvo al buscar el bot sin
  caché.
- **La deduplicación tiene un sitio:** el historial (paso 1 de la ingesta). El motor sigue teniendo que tolerar un
  duplicado entre la publicación y la confirmación.
- **El contrato cambia** a la versión 2 (`asyncapi-v2.yaml`).

## Condiciones de revisión

- La mediana del webhook medida en I1 pasa de 250 ms con Bifröst en el camino.
- Hay que guardar el evento más de 7 días.
