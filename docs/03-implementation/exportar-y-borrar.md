# Exportar y borrar: contactos, bots y clientes

* **Estado:** review
* **Fecha:** 2026-10-13
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 03-implementation
* **Versión:** 0.1.0

Lo que un cliente necesita para atender a quien le pide sus datos, y lo que pasa cuando un bot o un cliente se
van. Cubre RF08, RF09 y RF10 del [PRD](../01-requirements/mvp-baas-gateway.md); esto es cómo quedó construido y
hasta dónde llega.

## Los endpoints

Todos piden el token de [autenticacion.md](autenticacion.md). Un cliente solo alcanza lo suyo: lo ajeno responde
`404`, igual que lo inexistente.

| Para | Endpoint | Quién |
|---|---|---|
| Ver los contactos de un bot | `GET /chat/{bot_id}/contacts?offset=0&limit=100` | El cliente dueño |
| Encontrar a una persona en todos sus bots | `POST /contacts/search` | El cliente |
| Exportar lo guardado de un contacto | `GET /chat/{bot_id}/contacts/{contact_id}` | El cliente dueño |
| Borrar un contacto | `DELETE /chat/{bot_id}/contacts/{contact_id}` | El cliente dueño |
| Borrar un bot con todo lo suyo | `DELETE /bot/{bot_id}` | El cliente dueño |
| Dar de baja a un cliente | `DELETE /clients/{client_id}` | Solo el operador |

- **La lista** va de más antiguo a más nuevo, de 100 en 100 por defecto y de 500 como máximo, y dice cuántos hay
  en total.
- **La búsqueda** recibe en el cuerpo `{"waId": "<número>"}` o `{"fbId": "<identificador de Messenger>"}`, uno de
  los dos. El número se encuentra se escriba como se escriba: solo cuentan sus cifras. Va en el cuerpo y no en
  la dirección porque una dirección queda escrita en los registros de cada intermediario.

## Atender a quien pide sus datos

Quien ejerce sus derechos se dirige al cliente, que es el responsable del tratamiento, y se identifica por su
número o por su cuenta de Messenger. El cliente:

1. Busca a la persona con `POST /contacts/search`. La respuesta trae un contacto por cada bot al que escribió.
2. Para el acceso y la portabilidad (arts. 15 y 20), cada contacto de esa respuesta ya es la exportación
   completa, en JSON. `GET /chat/{bot_id}/contacts/{contact_id}` devuelve lo mismo para uno solo.
3. Para la supresión (art. 17), borra cada contacto con `DELETE /chat/{bot_id}/contacts/{contact_id}`.

### Qué se exporta

Todo lo que el gateway guarda de un contacto, con el número descifrado:

| Campo | Qué es |
|---|---|
| `uuid`, `botId` | Los identificadores que le dio el servicio y el bot al que escribió |
| `firstName`, `lastName`, `profilePic` | El nombre que envía WhatsApp, o el perfil que devuelve Messenger |
| `waId` | Su número de WhatsApp |
| `fbId` | Su identificador de Messenger |
| `isAdmin`, `status`, `createdAt`, `statusDate` | Estado del contacto y cuándo se creó |

**El gateway no guarda los mensajes.** Los publica en la cola para el motor de respuestas y no conserva copia. Lo
que el motor guarde de una conversación no sale por aquí.

## Qué borra cada cosa

Los tres borrados son definitivos: quitan los documentos de la base, no los marcan.

| Se borra | Con él se va | No toca |
|---|---|---|
| Un contacto | Todos los documentos de esa persona en ese bot | A la misma persona en otros bots del cliente |
| Un bot | Sus contactos, números, reglas e intents, y sus credenciales de Meta | Los demás bots del cliente |
| Un cliente | Sus claves de firma, todos sus bots con todo lo anterior, sus tokens ya usados y su clave de datos envuelta | A los demás clientes |

- **La respuesta dice cuánto se borró**, por tipo. Sirve de constancia.
- **Una persona borrada que vuelve a escribir** se guarda de nuevo, como un contacto nuevo. Si no debe volver a
  tratarse, el cliente tiene que impedirlo por su lado.
- **El webhook de un bot borrado responde `404`.** Hay que quitar también la suscripción en Meta, o seguirá
  enviando notificaciones.
- **Borrar no necesita el servicio de claves.** Si Andvari no responde, exportar y buscar contestan `503`, pero
  borrar funciona.
- **El operador no se puede dar de baja**: responde `409`.

### La baja de un cliente, paso a paso

El orden está pensado para que se pueda interrumpir y repetir:

1. Se le retiran las claves de firma y se le marca como inactivo. Desde ese instante no entra ningún token
   suyo, tampoco uno emitido antes.
2. Se borran sus bots, y con ellos sus webhooks dejan de responder; después, lo guardado para ellos.
3. Se borra su registro, y con él su clave de datos envuelta. La clave abierta se quita de la memoria del
   proceso que atiende la baja; cualquier otro proceso la suelta en cinco minutos como mucho.

Si algo falla a mitad, el cliente ya no entra y la baja se termina repitiendo la llamada. Lo mismo vale para un
bot: `DELETE /bot/{bot_id}` borra lo que quedara de una llamada anterior que falló.

Antes de la baja, el cliente puede llevarse sus datos: la lista de contactos de cada bot, por páginas, y la
configuración de cada bot con los endpoints de siempre.

### Mientras se borra sigue llegando tráfico

Un mensaje puede estar en camino mientras se borra su bot. Lo que se intenta guardar para un bot que ya no existe
se descarta en el momento, y un cambio sobre un documento ya borrado no lo devuelve a la base.

## Lo que el borrado no alcanza

Borrar aquí quita los datos de la base en uso. No llega a:

| Dónde quedan datos | Hasta cuándo | Estado |
|---|---|---|
| Mensajes en la cola `llm` | 24 horas como máximo: cada mensaje se publica con esa caducidad | Construido |
| El motor de respuestas y su LLM | Lo que el motor guarde. No tiene todavía forma de recibir un borrado, y no está revisado qué conserva | Abierto, en su repositorio |
| Logs del gateway | La rotación de Docker. Por debajo de `production` contienen números y nombres | Abierto (RS07) |
| Respaldos de la base | 365 días como máximo desde el borrado: es la retención de los respaldos (ADR-0014) | Decidido; sin configurar ni comprobar en Atlas |
| Meta | Sus propios términos con el cliente | Fuera del servicio |

**Los respaldos, en concreto.** [ADR-0010](../00-project/adr/0010-clave-de-cifrado-de-datos-por-cliente.md) cuenta
con que destruir la clave de datos de un cliente deje ilegibles sus datos también en los respaldos. Tal como está
construido, no es así: la clave de datos envuelta se guarda en la misma base que los datos, de modo que un respaldo
anterior a la baja la contiene, y la clave maestra de Andvari, que es una sola derivada por cliente, la sigue
abriendo. Además, lo que no está cifrado (nombres, identificador de Messenger, reglas e intents) se lee en un
respaldo sin clave alguna. Es el hallazgo H11 del [threat model](../02-design/threat-model.md).

Decidido el 2026-10-13 en [ADR-0014](../00-project/adr/0014-supresion-en-respaldos-por-caducidad.md): se acepta,
y en los respaldos la supresión se cumple por caducidad. Los respaldos de la base se conservan 365 días como
máximo, así que lo borrado desaparece del último respaldo, como mucho, 365 días después. Esto trae tres
obligaciones:

- **Decírselo al cliente.** Una supresión no es completa hasta pasado ese plazo, y es él quien responde ante quien
  pidió el borrado.
- **Si se restaura un respaldo, repetir los borrados** hechos después de su fecha. Lo restaurado trae de vuelta lo
  que se había borrado.
- **Configurar y comprobar la retención en Atlas.** Solo se puede en un clúster `M10` o superior, y el plan del
  clúster no consta.

## Rastro

Cada borrado deja una línea en el log, a nivel de aviso para que se conserve también en `production`: quién
borró, qué identificador y cuánto. No lleva nombres, números ni identificadores de Messenger. No es todavía la
auditoría por cliente que pide RS14.

## Lo que no hace todavía

- **Caducidad de los contactos.** El máximo de 12 meses sin actividad de la
  [clasificación de datos](../00-project/data-classification.md) no se aplica: el contacto no guarda cuándo
  escribió por última vez.
- **Avisar al motor de respuestas** de que un contacto, un bot o un cliente se han borrado.
- **Guardar un registro de supresiones** que dure lo que los respaldos, para poder repetirlas tras una
  restauración. Hoy solo queda la línea del log, que Docker rota.
- **Destruir la clave de un cliente de forma que alcance a los respaldos.** Descartado en ADR-0014.
