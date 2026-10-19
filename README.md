# wh-python-fastapi-messenger

Un **gateway de webhooks para chatbots de Facebook Messenger y WhatsApp Business**, genérico y multi-tenant, construido con FastAPI.

Gestiona el ciclo de vida completo de un chatbot (registro, verificación y configuración), recibe los mensajes entrantes de la plataforma Graph de Meta, identifica al contacto y publica el mensaje en una cola de RabbitMQ (`llm`) para que otro servicio lo procese (por ejemplo, un LLM que genere la respuesta). El cifrado del mensaje como JWE y el registro de cada petición como **evento** con sus **acciones** están implementados, pero hoy están desactivados en el código.

---

## Índice

- [Visión de la arquitectura](#visión-de-la-arquitectura)
- [Tecnologías](#tecnologías)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Ciclo de vida de una petición](#ciclo-de-vida-de-una-petición)
- [Endpoints de la API](#endpoints-de-la-api)
- [Modelo de datos (colecciones de MongoDB)](#modelo-de-datos-colecciones-de-mongodb)
- [Registro de eventos y criptografía](#registro-de-eventos-y-criptografía)
- [Configuración](#configuración)
- [Ejecución en local](#ejecución-en-local)
- [Ejecución con Docker](#ejecución-con-docker)
- [Despliegue](#despliegue)
- [Logging](#logging)
- [Seguridad](#seguridad)
- [Licencia](#licencia)

---

## Visión de la arquitectura

```
                 ┌──────────────────────────────────────────────┐
   Meta Graph    │                  App FastAPI                 │
  (Messenger /   │                                              │
   WhatsApp)     │   Middleware HTTP (interceptor)              │
       │         │     • tiempos (X-Processing-Time)            │
       │  POST   │     • andamiaje del Event por petición       │
       ├────────►│                                              │
       │         │   Rutas:  /bot   /chat/{bot_id}/*            │
       │         │        │                                     │
       │         │        ▼                                     │
       │         │   Controladores (chatbot / intents /         │
       │         │     facebook / messages / events / amqp)     │
       │         │        │                │                    │
       │         │        ▼                ▼                    │
       │         │   MongoDB          API Graph de Meta         │
       │         │  (mongoengine)    (perfiles de contacto,     │
       │         │                    envío por WhatsApp)       │
       │         │        │                                     │
       │         │        ▼                                     │
       │         │   Mensaje normalizado ──► RabbitMQ, cola     │
       └─────────┤                              "llm"           │
                 └──────────────────────────────────────────────┘
```

- **Webhook de entrada**: Meta envía el reto de verificación (`GET`) y las notificaciones de mensajes (`POST`) a `/chat/{bot_id}`.
- **Resolución de contactos**: cada remitente se busca o se crea como `Contact`; los de Messenger se enriquecen con su perfil de la API Graph.
- **Publicación**: cada mensaje que una persona envía se publica en RabbitMQ en un sobre propio, con el bot de destino y el identificador que Meta le dio, para que el motor de respuestas genere la respuesta. El contrato es [`docs/02-design/contracts/asyncapi.yaml`](docs/02-design/contracts/asyncapi.yaml).
- **Registro de eventos**: una petición puede generar un `Event` y varias `EventAction` con el método, el paso, el estado y el tiempo transcurrido.

---

## Tecnologías

| Ámbito | Tecnología |
|---|---|
| Framework web | [FastAPI](https://fastapi.tiangolo.com/) + Starlette |
| Servidor ASGI | Uvicorn (workers según `WEB_CONCURRENCY`) |
| Base de datos | MongoDB con el ODM [mongoengine](https://mongoengine.org/) (+ `pymongo`, `dnspython`) |
| Validación y ajustes | Pydantic v2, `pydantic-settings` |
| Mensajería | RabbitMQ con [`pika`](https://pika.readthedocs.io/) |
| Criptografía y tokens | `jwcrypto` (JWK/JWE/JWT) |
| Cliente HTTP | `requests` |
| Logging | `logging.config` configurado con `PyYAML` |
| Otros | `faker` (valores de ejemplo de los modelos de petición) |
| Pruebas | `pytest`, `pytest-cov`, `jsonschema` |

Las dependencias se declaran en [requirements.txt](requirements.txt) y se fijan con hashes en [requirements.lock](requirements.lock); las de pruebas, en `requirements-dev.txt` y su lock.

---

## Estructura del proyecto

```
.
├── src/                    # La aplicación (es lo único que contiene la imagen)
│   ├── app.py                  # App FastAPI: middleware, dependencias de autenticación y todas las rutas
│   ├── logging_config.yaml     # Configuración de logging por entorno
│   ├── classes/                # DTO de Pydantic + entidades de mongoengine
│   │   ├── tool_settings.py        # Settings (lee config.env)
│   │   ├── entity_*.py             # Documentos de MongoDB (ChatBot, Contact, Event, Jwk, ...)
│   │   └── dto_*.py                # Modelos de petición/respuesta y del payload de Facebook
│   ├── controller/             # Capa de lógica de negocio
│   │   ├── chatbot.py              # CRUD de bots, teléfonos y reglas
│   │   ├── intents.py              # CRUD de intents y su esquema de herramientas
│   │   ├── facebook.py             # Identificación de contactos + perfiles de la API Graph
│   │   ├── messages.py             # Procesado de mensajes entrantes + envío por WhatsApp
│   │   ├── events.py               # Registro de Event / EventAction
│   │   └── amqp_broker.py          # Publicador de RabbitMQ
│   ├── constants/              # Cadenas estáticas: metadatos de la doc, cabeceras, claves de FB, formatos
│   ├── enums/                  # Enums Status, Environment y KeyTypes
│   └── utils/                  # Logging, generadores de códigos, verificación de firma, claves JWK/PEM
│
├── tests/                  # Pirámide de pruebas: unit/ integration/ contract/ e2e/ security/ (ver tests/README.md)
├── docs/                   # Documentación AI-DLC, una carpeta por fase (00-project ... 06-monitoring)
├── .ai-dlc/                # Checklists de los gates, plantillas, mapeo OWASP y scripts (contrato OpenAPI)
├── deploy/                 # docker-compose.yml del servidor (ver Despliegue)
├── .github/                # Workflows (ci, build, guardia GitFlow) y CODEOWNERS
│
├── Dockerfile              # Imagen python:3.12-slim, usuario sin privilegios, uvicorn en :5002
├── .dockerignore           # Deja config.env, certs/ y los ficheros de desarrollo fuera del contexto de build
├── requirements.txt        # Dependencias de ejecución, como rangos; requirements-dev.txt añade las de pruebas
├── requirements.lock       # Las mismas, fijadas con hashes; requirements-dev.lock para las pruebas
├── pytest.ini              # Añade src/ al path: `pytest` se ejecuta desde la raíz
├── config.env.example      # Plantilla de config.env (ignorado por git, lo carga pydantic-settings)
├── CHANGELOG.md  SECURITY.md  CONTRIBUTING.md
├── bootstrap.sh            # Heredado: clona, reconstruye y arranca. Borra TODOS los datos de Docker sin usar del host
├── compose-dev.yaml        # Ayuda de "Dev Environments" de Docker (no es el runtime de la app)
├── certs/                  # Claves privadas RSA por evento (*.pem), ignoradas por git
└── prototypes/             # Experimentos desechables (ignorados en .gitignore)
```

El repositorio sigue la estructura AI-DLC para un único servicio ([ADR-0001](docs/00-project/adr/0001-adopcion-estructura-ai-dlc.md)).

### Responsabilidad de cada paquete

- **`classes/`** — única superficie de importación (`from classes import ...`). Mezcla dos papeles:
  - **Entidades** (`entity_*.py`): subclases de `mongoengine.Document`. Cada módulo abre su propia conexión a MongoDB al importarse, con los valores de `Settings`.
  - **DTO** (`dto_*.py`): modelos de Pydantic para los cuerpos de petición, las respuestas y el payload anidado del webhook de Facebook/WhatsApp (`dto_facebook_*.py`).
- **`controller/`** — funciones asíncronas con prefijo `ctr_*`, reexportadas desde `controller/__init__.py`. Construyen un `ResponseData`, persisten datos, emiten acciones de evento y devuelven un `starlette.Response`.
- **`crypto/`** — el cifrado de los datos de cada cliente: los campos y el índice ciego (`fields.py`) y el cliente del servicio de claves (`key_service.py`).
- **`auth/`** — la autenticación de todo lo que no es el webhook: verificación del token (`tokens.py`), el par de claves del gateway (`gateway_keys.py`), qué clave pública se le acepta a un cliente (`client_keys.py`) y el lado del cliente como referencia (`client.py`).
- **`ops/`** — comandos que se ejecutan a mano: `gateway_key` crea y rota el par del gateway, `operator_key` registra la primera clave del operador y `client` es el cliente de referencia.
- **`repository/`** — la única vía a los datos de un cliente. `TenantRepository` se construye con el cliente y lo añade a cada consulta: lo ajeno responde igual que lo inexistente ([ADR-0012](docs/00-project/adr/0012-aislamiento-por-cliente-en-la-capa-de-datos.md)). Los controladores no consultan la base.
- **`migrations/`** — pasos de datos que se ejecutan a mano. `assign_operator_client` asigna al cliente del operador los documentos anteriores a la existencia de clientes: `python -m migrations.assign_operator_client` informa y `--apply` escribe.
- **`constants/`** — `documentation.py` alimenta los metadatos de OpenAPI; `facebook.py` contiene las claves de verificación `hub.*`; `headers.py` y `formats.py`, los nombres de cabecera y los tipos de contenido.
- **`enums/`** — `Status` (REG/ACT/LOK/DIS/OVR/ERR/COM), `Environment` (development/staging/production), `KeyTypes` y `Role` (cliente, operador, servicio).
- **`utils/`** — `configure_logging()` (se ejecuta al arrancar), `generate_code()`, la verificación de firmas y las ayudas de JWK/PEM (`get_private_key`, `get_public_key`).

---

## Ciclo de vida de una petición

Definido en [src/app.py](src/app.py):

1. **El middleware HTTP `interceptor`** se ejecuta en cada petición:
   - Anota la hora de inicio y añade `X-Processing-Time` a la respuesta.
   - Construye un DTO `EventTransport` (uuid, recurso, método y origen del cliente). La creación del evento está solo esbozada: la llamada a `ctr_create_event` está comentada y `request.state.event_id` vale `None`.
   - Envuelve `call_next` en try/except/finally, de modo que ante un fallo siempre se devuelve un `ResponseData` con `500`.
2. **Las dependencias** autentican la petición antes de que corra ningún handler: el token del cliente en todo lo que no es el webhook, y `X-Hub-Signature-256` en las notificaciones entrantes (ver [Seguridad](#seguridad)). Las rutas de un cliente reciben su repositorio; las del registro exigen además que sea el operador.
3. **Los handlers de ruta** llaman al controlador `ctr_*` que corresponde y devuelven su `Response`.
4. **Los controladores** emiten registros `EventAction` (solo cuando hay un `eventId`), persisten con mongoengine y, para los mensajes entrantes, publican en RabbitMQ. La publicación se espera y el broker la confirma antes de que Meta reciba su `200`.

---

## Endpoints de la API

URL base en local: `http://localhost:5002` para la API de gestión y `http://localhost:5003` para el webhook, que son dos servicios (ADR-0018).
Documentación interactiva, solo en `development`: `/docs` (Swagger) y `/redoc` en cada uno.

Solo son públicas las dos rutas del webhook (`GET` y `POST /chat/{bot_id}`) y `GET /health`. Cualquier otro endpoint exige un token en `Authorization: Bearer` y responde `401` sin uno válido: un JWT firmado por el cliente dentro de un JWE cifrado para el gateway. Cómo se construye, y cómo se da de alta a un cliente, está en [docs/03-implementation/autenticacion.md](docs/03-implementation/autenticacion.md).

### Gestión de bots — etiqueta `Bot`

| Método | Ruta | Cuerpo | Descripción |
|---|---|---|---|
| `POST` | `/bot` | `ChatbotRequest` | Crea un chatbot. Genera un `uuid` y un `verifyToken` firmado (JWT). Devuelve `BotResponse`. |
| `DELETE` | `/bot/{bot_id}` | — | Borra un chatbot con todo lo guardado para él: contactos, números, reglas e intents. No se puede deshacer. |

Campos de `ChatbotRequest`: `name`, `role`, `description`, `tone`.

### Chat y webhook — etiqueta `Chat`

| Método | Ruta | Descripción |
|---|---|---|
| `GET`  | `/chat/{bot_id}` | **Verificación del webhook de Meta.** Valida `hub.mode=subscribe` y compara `hub.verify_token` con el `verifyToken` del bot; después devuelve `hub.challenge` como texto plano. Cualquier otra cosa es un `403`. |
| `POST` | `/chat/{bot_id}` | **Mensajes entrantes.** Exige un `X-Hub-Signature-256` válido (`403` si no). Recibe un `FacebookRequest` y despacha payloads de Messenger (`object=page`) o de WhatsApp (`object=whatsapp_business_account`). Publica un sobre por cada mensaje de la notificación; los acuses de entrega y de lectura, los ecos de lo que envía la página y las pulsaciones de botones se aceptan y no se publican. Responde `200` cuando RabbitMQ ha confirmado todos los mensajes, y también a lo firmado que no entiende o no puede procesar, que deja en el log. Responde `503`, para que Meta reintente, solo si no están el broker, la base de datos o el servicio de claves. |
| `POST` | `/chat/{bot_id}/phones` | Registra un número de WhatsApp (`ChatbotPhoneRequest`: `environment`, `phoneNumber`, `phoneId`). |
| `GET`  | `/chat/{bot_id}/phones?environment=` | Lista los números del bot; con `environment` devuelve el más reciente de ese entorno. |
| `GET`  | `/chat/{bot_id}/info` | Devuelve la información guardada del bot (`chatbot_info()`) y su token de verificación. De las credenciales de Meta solo dice cuáles están cargadas. |
| `PUT`  | `/chat/{bot_id}/credentials` | Carga o rota las credenciales de Meta del bot (`BotCredentialsRequest`: `facebookToken`, `whatsappToken`, `appSecret`). No las devuelve. |
| `GET`  | `/chat/{bot_id}/tokens` | Los tokens de Meta del bot, **solo para el motor de respuestas**, con la clave que tiene para el cliente dueño del bot. Cada entrega queda en el log. |
| `GET`  | `/chat/{bot_id}/rules` | Construye y devuelve el system prompt del LLM a partir de la persona del bot y sus reglas. |
| `POST` | `/chat/{bot_id}/rules` | Añade una o varias reglas al bot (`RulesRequest.rules: list[str]`). |

### Contactos — etiqueta `Contacts`

| Método | Ruta | Descripción |
|---|---|---|
| `GET`  | `/chat/{bot_id}/contacts?offset=&limit=` | Lista los contactos del bot, por páginas, con todo lo guardado de cada uno. |
| `POST` | `/contacts/search` | Encuentra a una persona en todos los bots del cliente (`ContactSearchRequest`: `waId` o `fbId`). |
| `GET`  | `/chat/{bot_id}/contacts/{contact_id}` | Exporta lo guardado de un contacto. |
| `DELETE` | `/chat/{bot_id}/contacts/{contact_id}` | Borra un contacto. No se puede deshacer. |

Cómo se atiende con ellos a quien pide sus datos, y qué no alcanza el borrado, está en
[docs/03-implementation/exportar-y-borrar.md](docs/03-implementation/exportar-y-borrar.md).

### Intents — etiqueta `Intents`

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/chat/{bot_id}/intents` | Crea un intent para el bot (`IntentRequest`). |
| `GET`  | `/chat/{bot_id}/intents` | Lista los intents del bot. |
| `GET`  | `/chat/{bot_id}/intents/{intent_id}` | Devuelve un intent. |
| `PUT`  | `/chat/{bot_id}/intents/{intent_id}` | Actualiza un intent. |
| `DELETE` | `/chat/{bot_id}/intents/{intent_id}` | Borra un intent. |
| `GET`  | `/chat/{bot_id}/tools` | Devuelve las acciones activas de los intents activos del bot como una lista plana de definiciones de herramientas para el LLM. |

### Salud — etiqueta `Health`

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Sonda de vida. Responde sin tocar MongoDB ni RabbitMQ. |

---

## Modelo de datos (colecciones de MongoDB)

Todas las entidades son `Document` de mongoengine y se conectan a la base configurada en `config.env`.

| Entidad | Fichero | Campos clave | Propósito |
|---|---|---|---|
| `ChatBot` | `entity_chatbot.py` | `uuid`, `name`, `role`, `description`, `tone`, `verifyToken`, `facebookToken`, `whatsappToken`, `appSecret`, `status` | Un chatbot (tenant). `generate_verification_token()` emite el JWT firmado que se usa para verificar el webhook ante Meta. |
| `ChatbotPhone` | `entity_chatbot_phones.py` | `uuid`, `bot_id`, `environment`, `phoneNumber`, `phoneId` | Números de WhatsApp asociados a un bot, separados por entorno. |
| `Contact` | `entity_contact.py` | `_uuid`, `botId`, `firstName`, `lastName`, `profilePic`, `fbId`, `waId` | Una persona que escribe a un bot. Se busca por `fbId` o `waId`; los contactos de Messenger se enriquecen desde la API Graph. |
| `Rule` | `entity_chatbot_rules.py` | `uuid`, `botId`, `rule` | Una regla del system prompt de un bot. |
| `Intent` | `entity_intent.py` | `uuid`, `botId`, `name`, `description`, `samplePhrases`, `actions`, `status` | Algo que el bot sabe hacer. Cada acción (`Action`, con sus `ActionParameter` y su `ApiCall`) se expone al LLM como una herramienta. |
| `Event` | `entity_event.py` | `uuid`, `resource`, `operation`, `origen`, `result`, `status` | Una petición registrada. Puede provisionar una clave RSA al crearse. |
| `EventAction` | `entity_event_action.py` | `uuid`, `eventId`, `method`, `step`, `description`, `totalTime`, `status` | Un paso dentro de un evento, con el tiempo medido al completarse. |
| `Jwk` | `entity_jwk.py` | `kid`, `kty`, `n`, `e`, `use`, `x5t` | Metadatos del JWK público. `create_key_for_event()` genera un par RSA, escribe el PEM en `certs/`, guarda el JWK público y lo enlaza con `EventJwk`. |
| `EventJwk` | `entity_event_jwk.py` | `eventId`, `jwkId` | Tabla de unión entre un evento y su clave de cifrado. |
| `Credentials` | `entity_credentials.py` | `uuid`, `_header`, `_claims`, `_key`, `jwt` | Credencial simétrica (HS256) con la que se firman los tokens de verificación de los bots. |
| `QueueMessage` | `entity_amqp_message.py` | `schemaVersion`, `_uuid`, `messageId`, `eventId`, `endpoint`, `operation`, `jwe_body`, `status` | El sobre que se publica en RabbitMQ, versión 1. `messageId` es el identificador que Meta dio al mensaje. `set_jwe_body()` cifra el cuerpo con el JWK del evento como JWE compacto. |

---

## Registro de eventos y criptografía

- **Claves RSA por evento** — `Jwk.create_key_for_event()` genera un par RSA (tamaño según `KEY_SIZE`, 3072 por defecto), escribe la clave privada en `certs/{UUID}_private.pem` y persiste en MongoDB solo el JWK público.
- **Payloads JWE** — `QueueMessage.set_jwe_body()` busca el JWK del evento y cifra el `MessageBody` normalizado (botId, type, contact, message) como JWE compacto; el consumidor lo descifra con el PEM privado correspondiente (ver `src/utils/key_management.py`). **Hoy no se usa**: la llamada está comentada en `src/controller/messages.py` y el mensaje se publica sin cifrar.
- **Tokens de verificación de los bots** — `Credentials` construye un JWT firmado con HS256 que se guarda como `verifyToken` del bot y se compara con el `hub.verify_token` de Meta al configurar el webhook.

---

## Configuración

Los ajustes los carga `src/classes/tool_settings.py` (`pydantic-settings`) desde **`config.env`**; parte de [config.env.example](config.env.example). Las variables de entorno tienen prioridad sobre el fichero. Variables necesarias:

| Variable | Descripción |
|---|---|
| `GATEWAY_KEYS_FILE` | Ruta del fichero con el par de claves del gateway, al que los clientes cifran sus tokens. Fuera del repositorio y de la imagen; la app no arranca sin él. Se crea con `python -m ops.gateway_key generate`. |
| `GATEWAY_AUDIENCE` | Lo que los clientes ponen en el `aud` de sus tokens: la URL pública del despliegue. |
| `ANDVARI_ADDR`, `ANDVARI_ROLE_ID` | Dirección del servicio de claves (OpenBao) y rol con el que entra el gateway. Fuera de desarrollo la dirección tiene que ser `https`. |
| `ANDVARI_SECRET_ID_FILE`, `ANDVARI_CA_FILE` | Rutas del fichero con la credencial de ese rol y de la autoridad que firmó el certificado del servicio de claves. |
| `ERASURES_DIR` | Directorio del registro de supresiones: cada borrado se apunta ahí antes de hacerse. Tiene que sobrevivir al contenedor, estar en los respaldos y no ser la base de datos. Si no se puede escribir, no se borra nada. Por defecto, `erasures`. |
| `FACEBOOK_APP_SECRET` | App Secret de Meta con el que se verifican las firmas del webhook. Solo es opcional si cada chatbot lleva su propio `appSecret`. |
| `CLIENT_ID`, `NATIONAL_ID_URL` | Identificadores de cliente varios. |
| `DB_NAME`, `DB_HOST`, `DB_USERNAME`, `DB_PASSWORD` | Conexión a MongoDB (admite host SRV de Atlas). |
| `SENDER_EMAIL`, `SENDER_PASSWORD`, `GMAIL_SERVER_URL`, `GMAIL_SERVER_PORT` | Ajustes de correo/SMTP. |
| `EXPIRATION_TIME`, `ACTIVATION_CODE_LENGTH`, `PASSWORD_LENGTH` | Parámetros de generación de códigos y tokens. |
| `QMS_SERVER`, `QMS_USER`, `QMS_PASSWORD` | Host y credenciales de RabbitMQ. |
| `KEY_SIZE`, `PRIVATE_KEY_FILENAME`, `PUBLIC_KEY_FILENAME` | Generación de claves y plantillas de ruta de los PEM (marcador `{UUID}`). |
| `ENVIRONMENT` | `development`, `staging` o `production`: selecciona el logger, y solo en `development` se sirven `/docs`, `/redoc` y `/openapi.json`. Con cualquier otro valor el servicio no arranca. El compose de despliegue lo fija en `production`. |
| `VERSION` | Versión de la app que muestra OpenAPI. |
| `VERIFY_TOKEN` | Token de verificación por defecto. |
| `FACEBOOK_GRAPH_URL`, `FACEBOOK_WHATSAPP_MESSAGE`, `FACEBOOK_GRAPH_VERSION` | Plantillas de los endpoints de la API Graph de Meta y su versión (por ejemplo, `v19.0`). |

> `config.env` y `certs/` están ignorados por git y nunca se han commiteado. Que siga así: el repositorio es público.

---

## Ejecución en local

Requisitos: Python 3.11 o superior (usa uniones `str | None` y sentencias `match`), un MongoDB alcanzable y un broker RabbitMQ.

```bash
# 1. Crea y activa un entorno virtual
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate

# 2. Instala las dependencias, fijadas y con verificación de hashes
pip install --require-hashes -r requirements-dev.lock

# 3. Configura
#    Copia config.env.example a config.env y rellena tus credenciales de
#    MongoDB / RabbitMQ / Meta, y crea el par de claves del gateway:
#    PYTHONPATH=src python -m ops.gateway_key generate gateway-keys.json

# 4. Arranca los dos servicios (ADR-0018), cada uno en su terminal
uvicorn app:app --app-dir src --host 0.0.0.0 --port 5002 --reload       # API de gestión
uvicorn webhook:app --app-dir src --host 0.0.0.0 --port 5003 --reload   # webhook de Meta

# 5. Ejecuta las pruebas (no necesitan servicios ni config.env)
pytest
```

Abre `http://localhost:5002/docs` para ver la interfaz de Swagger de la gestión, y `http://localhost:5003/docs` para la del webhook. Solo se sirven con `ENVIRONMENT=development`.

---

## Ejecución con Docker

```bash
# Construye la imagen
docker build -t wh-python-fastapi-messenger:latest .

# Arráncala. Los ajustes no van dentro de la imagen: se pasan al ejecutar
docker run -d -p 127.0.0.1:5002:5002 --env-file config.env --name wh-python-fastapi-messenger wh-python-fastapi-messenger:latest
```

La imagen arranca la API de gestión. El webhook es la misma imagen con otro comando:
`uvicorn webhook:app --host 0.0.0.0 --port 5002 --no-access-log`, como en
[deploy/docker-compose.yml](deploy/docker-compose.yml).

La imagen corre con un usuario sin privilegios, no incluye `config.env` ni `certs/` (ver [.dockerignore](.dockerignore)) y arranca un solo worker salvo que `WEB_CONCURRENCY` diga otra cosa. `GET /health` es su sonda de vida.

> [bootstrap.sh](bootstrap.sh) es anterior a esta imagen y ejecuta `docker system prune -a -f`: no lo uses en un host que corra cualquier otra cosa.
>
> [compose-dev.yaml](compose-dev.yaml) es una ayuda de *Dev Environments* de Docker (solo ejecuta `sleep infinity`), **no** un compose de este servicio.

---

## Despliegue

Fusionar a `main` construye y despliega:

1. El workflow [build](.github/workflows/build.yml) ejecuta las pruebas y, si pasan, publica `ghcr.io/jeremialcala/wh-python-fastapi-messenger:sha-<7>` en GHCR.
2. GitHub envía `workflow_run` al receptor de webhooks del servidor ([despliegue-continuo](https://github.com/higerotech/despliegue-continuo)), que descarga ese tag, levanta el proyecto compose, comprueba `/health` y vuelve al tag anterior si falla.

Preparación única en el servidor:

- `/srv/apps/bots-gateway/docker-compose.yml`, copiado de [deploy/docker-compose.yml](deploy/docker-compose.yml), y junto a él un `.env` con las claves de [config.env.example](config.env.example).
- El par de claves del gateway en `keys/gateway-keys.json` y la primera clave del operador registrada: los tres pasos de la puesta en marcha de [autenticacion.md](docs/03-implementation/autenticacion.md).
- La red Docker externa `andvari`, la credencial del gateway en `keys/andvari-secret-id` y las dos migraciones de datos: la puesta en marcha de [cifrado-de-datos.md](docs/03-implementation/cifrado-de-datos.md).
- El directorio `erasures/`, con dueño `10001` e incluido en los respaldos del servidor: es el registro de supresiones de [exportar-y-borrar.md](docs/03-implementation/exportar-y-borrar.md). Sin él, borrar responde `503`.
- La red Docker externa `hermod` y un usuario de RabbitMQ para el gateway (`QMS_SERVER=hermod`). Lo usa el worker de ingesta mientras el motor lea la cola `llm`.
- La red Docker externa `bifrost` y los ficheros que Bifröst escribe para el webhook y para el worker, `/srv/infra/bifrost/credenciales/webhook.env`, `ingesta.env` y `gestion.env`, con el consumidor `ingesta` de `WEBHOOK` ya creado ([bus-de-eventos.md](docs/03-implementation/bus-de-eventos.md)). Sin `NATS_URL`, el webhook no arranca fuera de desarrollo.
- El paquete de GHCR en **Public**, porque el receptor hace pull anónimo.
- Una entrada en el `apps.yml` del receptor y el webhook `workflow_run` de este repositorio:

  ```yaml
  - name: bots-gateway
    repo: jeremialcala/wh-python-fastapi-messenger
    branch: main
    event: workflow_run
    workflow: build
    project_dir: /srv/apps/bots-gateway
    image: ghcr.io/jeremialcala/wh-python-fastapi-messenger
    health_url: http://127.0.0.1:5003/health
    health_timeout: 120
    health_interval: 3
    rollback: true
  ```

Son tres contenedores de la misma imagen. Los dos HTTP escuchan solo en loopback:

- `bots-webhook`, en el 5003. Comprueba la firma y publica en Bifröst (ADR-0021). Es lo único que publica el túnel.
- `bots-gateway`, la API de gestión, en el 5002 (ADR-0018). Sigue privada.
- `bots-ingest`, el worker de ingesta, sin puerto. Identifica al contacto, guarda el historial y pasa cada mensaje al motor.

El webhook arranca cuando la gestión está sana, así que el `health_url` del receptor, el del webhook, responde por los dos.

---

## Logging

Se configura en [src/logging_config.yaml](src/logging_config.yaml) y lo aplica al arrancar `utils.configure_logging` (registrado como hook `on_startup` de FastAPI). El logger se elige según `ENVIRONMENT`:

| Entorno | Nivel | Salidas |
|---|---|---|
| `development` | INFO | consola |
| `staging` | INFO | consola + `application.log` |
| `production` | WARNING | consola (Docker la conserva y la rota) |

---

## Seguridad

| Superficie | Control |
|---|---|
| Todo lo que no es el webhook ni `/health` | Token en `Authorization: Bearer`: un JWT firmado por el cliente (`ES256`) dentro de un JWE cifrado para el gateway (`RSA-OAEP-256`, `A256CBC-HS512`). Dura 60 segundos como máximo y vale una vez. `401` si no es válido, sin decir por qué. |
| Rutas de un cliente (`/bot`, `/chat/{bot_id}/...`) | El token dice quién es; solo alcanza lo suyo. Lo ajeno responde `404`, igual que lo inexistente. |
| Registro de clientes (`/clients`) | Solo el operador, que también da de baja a un cliente con `DELETE /clients/{client_id}`. `403` para cualquier otro cliente. |
| Motor de respuestas | Una clave por cliente, que registra el operador en `/clients/{client_id}/service-keys`. Con ella el motor lee las reglas, las herramientas y los tokens de los bots de ese cliente, y nada más: cualquier otra ruta le responde `403`. Ver [autenticacion.md](docs/03-implementation/autenticacion.md). |
| Datos en reposo | Números de teléfono, tokens de Meta, App Secret y token de verificación, cifrados con una clave por cliente (AES-256-GCM). La clave maestra no sale del servicio de claves. Ver [cifrado-de-datos.md](docs/03-implementation/cifrado-de-datos.md). |
| `GET /chat/{bot_id}` (verificación) | `hub.verify_token` comparado en tiempo constante con el `verifyToken` del bot. `403` si no coincide. |
| `POST /chat/{bot_id}` (notificaciones) | `X-Hub-Signature-256`: HMAC-SHA256 del cuerpo crudo con el App Secret de Meta como clave. `403` si no coincide, sin leer nada del cuerpo. |
| Cualquier petición | Cuerpo de 3 MiB como máximo, que es lo más que envía Meta. `413` por encima, antes de comprobar firma o token. |

- **Qué App Secret se usa** — el `appSecret` del propio chatbot si su documento lo tiene; si no, `FACEBOOK_APP_SECRET`. Sin ninguno de los dos, se rechaza toda notificación. Igual que los tokens de página y de WhatsApp, `appSecret` se carga con `PUT /chat/{bot_id}/credentials`; ningún endpoint lo devuelve.
- **Entrega** — una notificación recibe su `200` solo después de que RabbitMQ confirme la publicación. Si no responden el broker, la base de datos o el servicio de claves, recibe `503`. Lo firmado que no se entiende, y el mensaje que falla por sí mismo, reciben `200` y quedan en el log: reenviarlos no cambiaría nada, y Meta da de baja el webhook que falla durante una hora ([ADR-0015](docs/00-project/adr/0015-que-se-responde-a-meta.md)). Meta reenvía ante un `503`, así que el consumidor de la cola `llm` debe tolerar duplicados: cada sobre lleva en `messageId` el identificador de Meta, que se repite en cada reentrega. Un mensaje que nadie consume caduca en la cola a las 24 horas.
- **Logs** — no se escribe nada de lo que envía quien llama, ni de lo que Meta envía sobre una persona: ni números, ni nombres, ni mensajes, ni tokens. Cada petición deja una línea con su método, la ruta tal como está declarada y los identificadores bien formados de su dirección; de un fallo se escribe su tipo y su línea, nunca su texto. El log de accesos de Uvicorn, que escribe la query string, está apagado.
- **Errores** — un fallo inesperado responde `500` sin su texto, y un `422` dice dónde está el error sin repetir lo enviado.
- **Pendiente** — no hay límite de tasa: publica en el borde solo el servicio del webhook y deja la gestión en la red privada. `/docs`, `/redoc` y `/openapi.json` solo se sirven en `development`. El mensaje viaja a la cola sin cifrar.

Para firmar a mano una notificación de prueba:

```bash
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$FACEBOOK_APP_SECRET" | sed 's/^.* //')
curl -X POST "http://localhost:5003/chat/$BOT_ID" -H 'Content-Type: application/json' \
     -H "X-Hub-Signature-256: sha256=$SIG" -d "$BODY"
```

La política de reporte de vulnerabilidades está en [SECURITY.md](SECURITY.md).

---

## Licencia

Publicado bajo la **Apache License 2.0**. Ver [LICENSE](LICENSE).

Mantenedor: **Jeremi Alcala** — <jeremialcala@gmail.com> · https://jeremi.web-ones.com
