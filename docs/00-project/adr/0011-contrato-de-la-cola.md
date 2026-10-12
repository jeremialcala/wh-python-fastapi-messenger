# ADR-0011: Contrato de la cola `llm` entre el gateway y el motor de respuestas

* **Estado:** accepted
* **Fecha:** 2026-10-12
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 02-design
* **Versión:** 0.1.0
* **ID:** ADR-0011
* **Supersede:** —
* **Controles OWASP afectados:** A08 (integridad entre servicios), A04 (datos personales en tránsito y en la cola), A10 (duplicados y mensajes inválidos)

Aceptada el 2026-10-12. Afecta a dos repositorios: este y `ms-python-metamsghandler`.

## Contexto

El gateway publica y el motor consume, pero hasta ahora no había contrato escrito. Al contrastar los dos códigos
aparecieron estas diferencias, todas comprobadas ejecutándolos:

| Hallazgo | Dónde |
|---|---|
| El motor rechaza los mensajes de Messenger: exige el webhook crudo de Meta y recibe el sobre del gateway | Motor |
| El motor descarta el `botId`, sin el cual no puede pedir la configuración del bot | Motor |
| `_uuid`, `createdAt` y `statusDate` valen lo mismo en todos los mensajes de un proceso: se calculan una vez al arrancar | Gateway |
| `metadata` de WhatsApp llega como lista de pares y no como objeto; contiene el `phone_number_id` que el motor necesita para responder | Gateway |
| Ningún lado deduplica | Ambos |
| El contenido viaja sin cifrar y la cola no caduca los mensajes | Gateway |

El contrato de hoy, defectos incluidos, está descrito en
[`asyncapi.yaml`](../../02-design/contracts/asyncapi.yaml) y lo verifica `tests/contract/test_queue_contract.py`.

## Decisión

**El gateway es dueño del contrato**, porque es quien publica. Vive en este repositorio y el motor lo referencia.

**El sobre del gateway es el formato para los dos canales.** Es el único que lleva el bot de destino
([ADR-0003](0003-el-bot-id-es-la-llave-de-la-configuracion.md)).

**Versión 1 del sobre.** Cambios sobre lo que hay hoy:

| Cambio | Lado | Motivo |
|---|---|---|
| Aceptar el sobre también para Messenger | Motor | RF12 |
| Conservar `botId` en el mensaje normalizado y en el resultado | Motor | ADR-0003 |
| Añadir `schemaVersion: 1` | Gateway | Poder evolucionar el formato |
| Añadir `messageId` con el identificador de Meta (`wamid` o `mid`) | Gateway | Clave de deduplicación común a los dos canales |
| `_uuid` único por mensaje y `createdAt` con la hora real | Gateway | Hoy son constantes |
| `metadata` como objeto | Gateway | El motor necesita `phone_number_id` |
| Caducidad de 24 horas en cada mensaje | Gateway | RNF05 |
| Deduplicar por `botId` y `messageId` durante 24 horas | Motor | RNF04 |

La caducidad se fija en cada mensaje al publicarlo, no como propiedad de la cola: así ningún lado tiene que
redeclarar la cola con argumentos nuevos, que es un cambio que RabbitMQ rechaza sobre una cola existente.

**Cifrado, en una segunda fase.** Cuando el motor esté registrado como cliente de servicio, `jwe_body` pasará a ser
un JWE cifrado para su clave pública, que es lo que su nombre promete. Hasta entonces la protección es que la cola
vive en una red privada y cada servicio entra con su propio usuario (RS08).

## Alternativas consideradas

| Opción | Pros | Contras | Riesgo de seguridad |
|---|---|---|---|
| **Sobre del gateway, versionado, para los dos canales** | Lleva el bot; un solo formato; el motor ya lo entiende para WhatsApp | El motor tiene que adaptar su parser de Messenger | Bajo |
| Publicar el webhook crudo de Meta | El motor ya lo entiende | No lleva el bot: el motor no sabría a quién pertenece el mensaje | No sirve con varios bots |
| Deduplicar en el gateway | El motor no cambia | El gateway tendría que guardar los identificadores vistos; el duplicado puede nacer después, en la cola | Protección incompleta |

## Consecuencias

- Positivas: el contrato queda escrito y probado, y los dos repositorios tienen una lista concreta de cambios.
- Negativas / deuda asumida: los cambios del lado del gateway son código por escribir (Gate 2). Los del motor
  dependen de su propio repositorio y calendario. Hasta que ambos estén, Messenger no funciona de extremo a extremo.
- Impacto en threat model: cubre los duplicados (T7) y, en la segunda fase, la lectura de la cola (T13).
