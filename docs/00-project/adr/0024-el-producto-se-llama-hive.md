# ADR-0024: El producto se llama Hive, con su API en hive-api y su webhook en hive-webhook

* **Estado:** accepted
* **Fecha:** 2026-10-20
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 00-project
* **Versión:** 0.2.0
* **ID:** ADR-0024
* **Supersede:** —
* **Controles OWASP afectados:** A05 (cada superficie con sus propias reglas en Cloudflare), A07 (la audiencia de los
  tokens es el dominio de la API)

Decisiones de Jeremi del 2026-10-20. La primera versión (PR #72) ponía la API en `hive.higerotech.com` y dejaba el
webhook para el E7. Ese mismo día Jeremi separó los dos en subdominios propios, y esta versión lo recoge.

## Contexto

El gateway y el motor de respuestas son un solo producto: un BaaS de chatbots para WhatsApp, Messenger e Instagram,
multi-cliente. Hasta ahora no tenía nombre. El repositorio se llama `wh-python-fastapi-messenger`, los contenedores
de midgard `bots-*`, y los documentos dicen «el gateway» y «el motor».

En el E7 el producto se publica por primera vez, y tiene dos superficies distintas:
- el **webhook**, que solo llama Meta;
- la **API de gestión**, que usan los clientes, el operador y los workers del motor.

El subdominio de la API es también la audiencia de los tokens (`GATEWAY_AUDIENCE`). Cada cliente y cada worker la
ponen en cada token, así que cambiarla después obliga a todos a cambiarla a la vez.

Los componentes de la plataforma llevan nombres nórdicos: Yggdrasil, Bifröst, Andvari, Hermod, Bragi, Saga, Mímir,
Heimdall, Thor, Odín.

## Decisión

1. **El producto se llama Hive.** El nombre describe lo que es el motor: seis workers, cada uno con su tarea, que se
   pasan el mensaje (ADR-0008 del motor). Es el nombre que ven los clientes, en inglés y fácil de decir. Los
   componentes de la plataforma conservan sus nombres nórdicos.
2. **Un subdominio por superficie:**

   | Superficie | URL | Quién la llama |
   |---|---|---|
   | API de gestión | `https://hive-api.higerotech.com` | Los clientes, el operador y los workers del motor |
   | Webhook de Meta | `https://hive-webhook.higerotech.com` | Solo Meta: la URL de cada bot es `https://hive-webhook.higerotech.com/chat/{bot_id}` |

   Así cada una se protege a su manera en Cloudflare, y la URL configurada en Meta no cambia si la API se mueve.
3. **La audiencia de los tokens es la URL de la API:** `GATEWAY_AUDIENCE=https://hive-api.higerotech.com`. La
   usan los clientes, el operador y los workers del motor.
4. **Un solo nivel de subdominio**, como Criterio (`criterio`, `criterio-api-dev`). El certificado gratuito de
   Cloudflare cubre `*.higerotech.com`, no `*.hive.higerotech.com`. Si hace falta publicar desarrollo:
   `hive-api-dev` y `hive-webhook-dev`.
5. **`hive.higerotech.com` queda reservado para el producto**, por ejemplo para su página. No se publica en el E7.
6. **No se renombra lo que ya existe:** el repositorio, la imagen `chatbot-engine`, los contenedores `bots-*` ni los
   paquetes. Cambiarlos no aporta nada al cliente y rompería el despliegue continuo y los enlaces.

## Alternativas consideradas

**El nombre:**

| Opción | Pros | Contras |
|---|---|---|
| **Hive** | Describe los workers; fácil para los clientes; en inglés | Rompe la convención nórdica de la plataforma. Es un nombre muy usado (Apache Hive, Hive Social, la cadena de bloques Hive), así que es difícil de distinguir como marca propia |
| Kvasir | El ser más sabio del mito, que respondía cualquier pregunta; distintivo; nórdico | Difícil de decir para un cliente |
| Huginn | El cuervo mensajero de Odín; nórdico | Ya es el nombre de un proyecto de código abierto conocido |

**Los subdominios:**

| Opción | Pros | Contras |
|---|---|---|
| **`hive-api` y `hive-webhook`** | Cada superficie con sus reglas. La URL de Meta no depende de la API. `hive` queda libre para el producto | Dos nombres en el túnel |
| API en `hive`, webhook en `hive-webhook` (la primera versión) | El nombre más corto para la API | El nombre del producto queda atado a la API |
| Todo en `hive`, el webhook por ruta | Un solo nombre | Las reglas de Cloudflare del webhook y de la API van por ruta, sobre el mismo host |

## Consecuencias

- **En el E7, el túnel publica los dos subdominios:** `hive-api.higerotech.com` hacia el gateway y
  `hive-webhook.higerotech.com` hacia el webhook. La URL del webhook de cada bot se configura en Meta.
- **La instancia de medición de midgard cambia su `GATEWAY_AUDIENCE`:** hoy tiene otra, de 23 caracteres. Con ella
  pasan a la nueva audiencia los tokens del operador, los de `ops.engine_keys` y la configuración del coordinador y
  del notificador (`GATEWAY_AUDIENCE`).
- **Los documentos para clientes** dicen Hive. Los de diseño siguen diciendo «el gateway» y «el motor», que son sus
  partes.
- **Si Hive llega a ser una marca propia**, con su propio dominio o un registro de marca, se revisa el nombre: es
  entonces cuando pesa que sea un nombre tan usado.

## Condiciones de revisión

- Hive pasa a tener un dominio propio o se registra como marca.
- El producto se publica fuera de `higerotech.com`.
