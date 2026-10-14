# ADR-0002: El motor de respuestas entrega la respuesta al usuario final

* **Estado:** accepted
* **Fecha:** 2026-10-12
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 00-project
* **Versión:** 0.1.0
* **ID:** ADR-0002
* **Supersede:** —
* **Controles OWASP afectados:** A01 (quién accede a las credenciales de cada bot), A04 (custodia de los tokens), A08 (integridad del mensaje entre servicios)

## Contexto

El gateway recibe los mensajes de Meta y los publica en la cola `llm`. Quien los procesa es el motor de respuestas,
`ms-python-metamsghandler`, un servicio aparte que está en implementación. Faltaba decidir quién llama a la API de
Meta para devolver la respuesta al usuario final (RF07 del [PRD](../../01-requirements/mvp-baas-gateway.md)).

El código tenía indicios en las dos direcciones. En el gateway, la documentación de OpenAPI describe un endpoint
`/answers` que nunca se implementó, y existe una función de envío por WhatsApp sin conectar. En el motor, la fase
de respuesta figura como trabajo futuro.

## Decisión

**El motor de respuestas procesa el mensaje completo, incluido el envío de la respuesta al destinatario.** El
gateway se queda en la entrada: verifica a Meta, identifica al contacto y encola.

## Alternativas consideradas

| Opción | Pros | Contras | Riesgo de seguridad |
|---|---|---|---|
| **El motor envía la respuesta** | Un solo servicio decide y ejecuta la respuesta; el gateway queda pequeño y sin lógica de salida; cada lado tiene un sentido único del tráfico | El motor necesita las credenciales de Meta de cada bot; hay que darle una forma de obtenerlas | Los tokens de los clientes pasan a ser accesibles desde dos servicios en vez de uno |
| El gateway envía la respuesta (endpoint `/answers` o cola de vuelta) | Los tokens no salen del servicio que ya los guarda | El gateway crece con lógica de salida y reintentos; el motor depende de él para cerrar cada conversación | Menor superficie para los tokens |

## Consecuencias

- Positivas: la responsabilidad queda nítida. El gateway es la frontera de entrada con Meta; el motor es dueño de
  la conversación de principio a fin.
- Negativas / deuda asumida:
  - El motor necesita, por cada mensaje, el bot de destino, el destinatario y el token de Meta de ese bot. Hoy
    descarta el bot y no tiene forma propia de obtener el token (RF07, RF12).
  - El requisito RS06 cambia: ya no puede ser "ningún endpoint devuelve los tokens". Pasa a ser que la API de
    gestión no los devuelve y que solo el motor los obtiene, con una credencial de servicio propia.
  - En el gateway sobran la función de envío por WhatsApp y la mención a `/answers` en la documentación de OpenAPI.
    Se retiran en un cambio de código aparte. Hecho: las dos están retiradas desde el 2026-10-13.
- Impacto en threat model: el motor entra en el perímetro de las credenciales Restringidas. Comprometer el motor
  expone los tokens de todos los clientes a los que pueda pedírselos, así que el acceso debe ser de mínimo
  privilegio y quedar registrado. Es el escenario de abuso AB15 del PRD.

## Abierto

Resuelto en [ADR-0003](0003-el-bot-id-es-la-llave-de-la-configuracion.md): el motor pide la configuración al
gateway con el `bot_id` del mensaje. Queda por definir la credencial con la que se autentica.
