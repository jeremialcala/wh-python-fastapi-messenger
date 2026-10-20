# ADR-0024: El producto se llama Hive, en hive.higerotech.com

* **Estado:** accepted
* **Fecha:** 2026-10-20
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 00-project
* **Versión:** 0.1.0
* **ID:** ADR-0024
* **Supersede:** —
* **Controles OWASP afectados:** A07 (la audiencia de los tokens es el dominio de la API)

Decisión de Jeremi del 2026-10-20.

## Contexto

El gateway y el motor de respuestas son un solo producto: un BaaS de chatbots para WhatsApp, Messenger e Instagram,
multi-cliente. Hasta ahora no tenía nombre. El repositorio se llama `wh-python-fastapi-messenger`, los contenedores
de midgard `bots-*`, y los documentos dicen «el gateway» y «el motor».

En el E7 el producto se publica por primera vez: necesita un subdominio de `higerotech.com`, y ese subdominio es
también la audiencia de los tokens (`GATEWAY_AUDIENCE`). Cada cliente y cada worker del motor la ponen en cada
token, así que cambiarla después obliga a todos a cambiarla a la vez.

Los componentes de la plataforma llevan nombres nórdicos: Yggdrasil, Bifröst, Andvari, Hermod, Bragi, Saga, Mímir,
Heimdall, Thor, Odín.

## Decisión

1. **El producto se llama Hive.** El nombre describe lo que es el motor: seis workers, cada uno con su tarea, que se
   pasan el mensaje (ADR-0008 del motor). Es el nombre que ven los clientes, en inglés y fácil de decir. Los
   componentes de la plataforma conservan sus nombres nórdicos.
2. **La API de gestión vive en `https://hive.higerotech.com`.** Esa es también la audiencia de los tokens
   (`GATEWAY_AUDIENCE=https://hive.higerotech.com`): la de los clientes, la del operador y la de los workers del motor.
3. **Un solo nivel de subdominio**, como Criterio (`criterio`, `criterio-dev`). El certificado gratuito de Cloudflare
   cubre `*.higerotech.com`, no `*.hive.higerotech.com`. Si hace falta un entorno de desarrollo publicado, será
   `hive-dev.higerotech.com`.
4. **No se renombra lo que ya existe:** el repositorio, la imagen `chatbot-engine`, los contenedores `bots-*` ni los
   paquetes. Cambiarlos no aporta nada al cliente y rompería el despliegue continuo y los enlaces.

## Pendiente: la URL del webhook de Meta

Se decide en el E7, al crear el túnel. Hay dos opciones:

| Opción | A favor | En contra |
|---|---|---|
| `hive-webhook.higerotech.com`, un subdominio aparte (lo que recomendé) | Cada uno se protege a su manera en Cloudflare: el webhook solo lo llama Meta, la API los clientes. La URL que se configura en Meta no cambia si la API se mueve | Un nombre más en el túnel |
| `https://hive.higerotech.com/webhook`, por ruta, en el mismo túnel | Un solo nombre | Las reglas de Cloudflare del webhook y de la API se escriben por ruta, sobre el mismo host |

## Alternativas consideradas

| Opción | Pros | Contras |
|---|---|---|
| **Hive** | Describe los workers; fácil para los clientes; en inglés | Rompe la convención nórdica de la plataforma. Es un nombre muy usado (Apache Hive, Hive Social, la cadena de bloques Hive), así que es difícil de distinguir como marca propia |
| Kvasir | El ser más sabio del mito, que respondía cualquier pregunta; distintivo; nórdico | Difícil de decir para un cliente |
| Huginn | El cuervo mensajero de Odín; nórdico | Ya es el nombre de un proyecto de código abierto conocido |

## Consecuencias

- **En el E7:** el túnel publica `hive.higerotech.com`.
  - La instancia de medición de midgard cambia su `GATEWAY_AUDIENCE`: hoy tiene otra, de 23 caracteres.
  - Los tokens del operador y los de los workers del motor pasan a llevar la nueva audiencia, que es la de la
    configuración del coordinador y del notificador (`GATEWAY_AUDIENCE`).
- **Los documentos para clientes** dicen Hive. Los de diseño siguen diciendo «el gateway» y «el motor», que son sus
  partes.
- **Si Hive llega a ser una marca propia**, con su propio dominio o un registro de marca, se revisa el nombre: es
  entonces cuando pesa que sea un nombre tan usado.

## Condiciones de revisión

- Hive pasa a tener un dominio propio o se registra como marca.
- El producto se publica fuera de `higerotech.com`.
