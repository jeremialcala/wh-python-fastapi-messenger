# wh-python-fastapi-messenger

A generic, multi-tenant **webhook gateway for Facebook Messenger and WhatsApp Business chatbots**, built with FastAPI.

It manages the full chatbot lifecycle (registration, verification, configuration), receives inbound messages from Meta's Graph platform, identifies contacts, encrypts the message payload as a JWE, and publishes it to a RabbitMQ queue (`llm`) for downstream processing (e.g. an LLM responder). Every request is tracked as an **event** with fine-grained **actions** for observability and metrics.

---

## Table of contents

- [Architecture overview](#architecture-overview)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Request lifecycle](#request-lifecycle)
- [API endpoints](#api-endpoints)
- [Data model (MongoDB collections)](#data-model-mongodb-collections)
- [Event tracking & cryptography](#event-tracking--cryptography)
- [Configuration](#configuration)
- [Running locally](#running-locally)
- [Running with Docker](#running-with-docker)
- [Logging](#logging)
- [⚠️ Security notice](#️-security-notice)
- [License](#license)

---

## Architecture overview

```
                 ┌──────────────────────────────────────────────┐
   Meta Graph    │                 FastAPI app                  │
  (Messenger /   │                                              │
   WhatsApp)     │   HTTP middleware (interceptor)              │
       │         │     • timing (X-Processing-Time)             │
       │  POST   │     • per-request Event scaffolding          │
       ├────────►│                                              │
       │         │   Routers:  /bot   /chat/{bot_id}/*          │
       │         │        │                                     │
       │         │        ▼                                     │
       │         │   Controllers (chatbot / facebook /          │
       │         │     messages / events / amqp_broker)         │
       │         │        │                │                    │
       │         │        ▼                ▼                    │
       │         │   MongoDB          Meta Graph API            │
       │         │  (mongoengine)    (contact profiles,         │
       │         │                    WhatsApp send)            │
       │         │        │                                     │
       │         │        ▼                                     │
       │         │   JWE-encrypt payload ──► RabbitMQ "llm"     │
       └─────────┤                              queue           │
                 └──────────────────────────────────────────────┘
```

- **Inbound webhook**: Meta sends a verification challenge (`GET`) and message notifications (`POST`) to `/chat/{bot_id}`.
- **Contact resolution**: Senders are resolved/created as `Contact` records, enriching Messenger users via the Graph API profile endpoint.
- **Asynchronous fan-out**: The normalized message body is wrapped in a per-event RSA **JWE** and published to RabbitMQ for an external consumer to generate replies.
- **Event sourcing-lite**: Each request can spawn an `Event` plus multiple `EventAction` rows recording method name, step, status and elapsed time.

---

## Tech stack

| Concern | Technology |
|---|---|
| Web framework | [FastAPI](https://fastapi.tiangolo.com/) + Starlette |
| ASGI server | Uvicorn (4 workers) |
| Database | MongoDB via [mongoengine](https://mongoengine.org/) ODM (+ `pymongo`, `dnspython`) |
| Validation / settings | Pydantic v2, `pydantic-settings`, `pydantic-extra-types`, `phonenumbers` |
| Messaging | RabbitMQ via [`pika`](https://pika.readthedocs.io/) |
| Cryptography / tokens | `jwcrypto` (JWK/JWE/JWT), `pyjwt`, `pycryptodome`, `cryptography` |
| HTTP client | `requests` |
| Logging | `PyYAML`-driven `logging.config` + `asgi-correlation-id` |
| Misc | `segno` + `pillow` (QR), `faker` (sample data), `pytz` |
| Testing | `pytest` |

Full pinned list lives in [requirements.txt](requirements.txt).

---

## Project structure

```
.
├── app.py                  # FastAPI app: middleware + all route definitions
├── Dockerfile              # Ubuntu-based image, runs uvicorn on :5002
├── bootstrap.sh            # Clone + rebuild + run the container (develop branch)
├── compose-dev.yaml        # Docker "dev environment" helper (not the app runtime)
├── requirements.txt        # Python dependencies
├── config.env              # Environment variables (loaded by pydantic-settings)
├── logging_config.yaml     # Per-environment logging configuration
│
├── classes/                # Pydantic DTOs + mongoengine entities
│   ├── tool_settings.py        # Settings (reads config.env)
│   ├── entity_*.py             # MongoDB documents (ChatBot, Contact, Event, Jwk, ...)
│   └── dto_*.py                # Request/response & Facebook payload models
│
├── controller/             # Business logic layer
│   ├── chatbot.py              # CRUD for bots, phones and rules
│   ├── facebook.py             # Contact identification + Graph API profile lookups
│   ├── messages.py             # Inbound message processing + WhatsApp send
│   ├── events.py               # Event / EventAction tracking
│   └── amqp_broker.py          # RabbitMQ publisher
│
├── constants/              # Static strings: docs metadata, headers, FB keys, formats
├── enums/                  # Status, Environment, KeyTypes enums
├── utils/                  # logging config, code generators, JWK/PEM key helpers
├── certs/                  # Per-event RSA private keys (*.pem)  ⚠️ see Security notice
├── prototypes/             # Throwaway experiments (ignored in .gitignore)
└── test/                   # Test package (currently empty scaffold)
```

### Package responsibilities

- **`classes/`** — single import surface (`from classes import ...`). Mixes two roles:
  - **Entities** (`entity_*.py`): `mongoengine.Document` subclasses. Each module opens its own MongoDB connection on import using `Settings`.
  - **DTOs** (`dto_*.py`): Pydantic models for request bodies, responses, and the nested Facebook/WhatsApp webhook payload (`dto_facebook_*.py`).
- **`controller/`** — async functions prefixed `ctr_*`, re-exported via `controller/__init__.py`. They build a `ResponseData` body, persist data, emit event actions, and return a `starlette.Response`.
- **`constants/`** — `documentation.py` powers the OpenAPI metadata; `facebook.py` holds the `hub.*` verification keys; `headers.py`/`formats.py` hold header names and content types.
- **`enums/`** — `Status` (REG/ACT/LOK/DIS/OVR/ERR/COM), `Environment` (development/staging/production), `KeyTypes`.
- **`utils/`** — `configure_logging()` (startup hook), `generate_code()`, and JWK/PEM helpers (`get_private_key`, `get_public_key`).

---

## Request lifecycle

Defined in [app.py](app.py):

1. **`interceptor` HTTP middleware** runs for every request:
   - Records start time and sets `X-Processing-Time` on the response.
   - Builds an `EventTransport` DTO (uuid, resource, method, client origin) — event creation is currently scaffolded (`ctr_create_event` call is commented out) and `request.state.event_id` is set to `None`.
   - Wraps `call_next` in try/except/finally so a baseline `500` `ResponseData` is always returned on failure.
2. **Route handlers** call the matching `ctr_*` controller and return its `Response`.
3. **Controllers** optionally emit `EventAction` records (only when an `eventId` is present), persist via mongoengine, and—for inbound messages—publish a JWE to RabbitMQ via `asyncio.ensure_future`.

---

## API endpoints

Base URL (local Docker): `http://localhost:5002`
Interactive docs: `http://localhost:5002/docs` (Swagger) · `http://localhost:5002/redoc`

### Bot management — tag `Bot`

| Method | Path | Body | Description |
|---|---|---|---|
| `POST` | `/bot` | `ChatbotRequest` | Create a chatbot. Generates a `uuid` and a signed `verifyToken` (JWT). Returns `BotResponse`. |

`ChatbotRequest` fields: `name`, `role`, `description`, `tone`.

### Chat / webhook — tag `Chat`

| Method | Path | Description |
|---|---|---|
| `GET`  | `/chat/{bot_id}` | **Meta webhook verification.** Validates `hub.mode=subscribe` and `hub.verify_token` against the bot's `verifyToken`, then echoes `hub.challenge`. |
| `POST` | `/chat/{bot_id}` | **Inbound message handler.** Accepts a `FacebookRequest`; dispatches Messenger (`object=page`) or WhatsApp (`object=whatsapp_business_account`) payloads. Processing runs in the background. |
| `POST` | `/chat/{bot_id}/phones` | Register a WhatsApp phone number (`ChatbotPhoneRequest`: `environment`, `phoneNumber`, `phoneId`). |
| `GET`  | `/chat/{bot_id}/phones?environment=` | List the bot's phone numbers; with `environment` returns the latest match for that environment. |
| `GET`  | `/chat/{bot_id}/info` | Return the bot's stored info (`chatbot_info()`). |
| `GET`  | `/chat/{bot_id}/rules` | Build and return the assembled LLM system prompt from the bot's persona + stored rules. |
| `POST` | `/chat/{bot_id}/rules` | Add one or more rules (`RulesRequest.rules: list[str]`) to the bot. |

> The `/answers` endpoint is described in the OpenAPI prose but is **not yet implemented** in `app.py`.

---

## Data model (MongoDB collections)

All entities are mongoengine `Document`s and connect to the database configured in `config.env`.

| Entity | File | Key fields | Purpose |
|---|---|---|---|
| `ChatBot` | `entity_chatbot.py` | `uuid`, `name`, `role`, `description`, `tone`, `verifyToken`, `facebookToken`, `whatsappToken`, `status` | A chatbot tenant. `generate_verification_token()` mints a signed JWT used for Meta webhook verification. |
| `ChatbotPhone` | `entity_chatbot_phones.py` | `uuid`, `bot_id`, `environment`, `phoneNumber`, `phoneId` | WhatsApp numbers bound to a bot, segmented by environment. |
| `Contact` | `entity_contact.py` | `_uuid`, `botId`, `firstName`, `lastName`, `profilePic`, `fbId`, `waId` | A person messaging a bot. Lookups by `fbId` or `waId`; Messenger contacts are enriched from the Graph API. |
| `Rule` | `entity_chatbot_rules.py` | `uuid`, `botId`, `rule` | A single system-prompt rule for a bot. |
| `Event` | `entity_event.py` | `uuid`, `resource`, `operation`, `origen`, `result`, `status` | One tracked request. Can provision an RSA key on creation. |
| `EventAction` | `entity_event_action.py` | `uuid`, `eventId`, `method`, `step`, `description`, `totalTime`, `status` | A step within an event, with elapsed-time measurement on completion. |
| `Jwk` | `entity_jwk.py` | `kid`, `kty`, `n`, `e`, `use`, `x5t` | Public JWK metadata. `create_key_for_event()` generates an RSA keypair, writes the PEM to `certs/`, stores the public JWK, and links it via `EventJwk`. |
| `EventJwk` | `entity_event_jwk.py` | `eventId`, `jwkId` | Join table mapping an event to its encryption key. |
| `Credentials` | `entity_credentials.py` | `uuid`, `_header`, `_claims`, `_key`, `jwt` | Symmetric (HS256) credential holder used to sign bot verification tokens. |
| `QueueMessage` | `entity_amqp_message.py` | `_uuid`, `eventId`, `endpoint`, `operation`, `jwe_body`, `status` | The message published to RabbitMQ. `set_jwe_body()` encrypts the body to the event's JWK as a compact JWE. |

---

## Event tracking & cryptography

- **Per-event RSA keys** — `Jwk.create_key_for_event()` generates an RSA keypair (size from `KEY_SIZE`, default 3072), writes the private key to `certs/{UUID}_private.pem`, and persists only the public JWK in MongoDB.
- **JWE payloads** — Before publishing to RabbitMQ, `QueueMessage.set_jwe_body()` looks up the event's JWK and encrypts the normalized `MessageBody` (botId, type, contact, message) as a compact JWE. Downstream consumers decrypt with the corresponding private PEM (see `utils/key_management.py`).
- **Bot verification tokens** — `Credentials` builds an HS256-signed JWT stored as the bot's `verifyToken`, compared against Meta's `hub.verify_token` during webhook setup.

---

## Configuration

Settings are loaded by `classes/tool_settings.py` (`pydantic-settings`) from **`config.env`**. Required variables:

| Variable | Description |
|---|---|
| `CLIENT_ID`, `NATIONAL_ID_URL` | Misc client identifiers. |
| `DB_NAME`, `DB_HOST`, `DB_USERNAME`, `DB_PASSWORD` | MongoDB connection (Atlas SRV host supported). |
| `SENDER_EMAIL`, `SENDER_PASSWORD`, `GMAIL_SERVER_URL`, `GMAIL_SERVER_PORT` | Email/SMTP settings. |
| `EXPIRATION_TIME`, `ACTIVATION_CODE_LENGTH`, `PASSWORD_LENGTH` | Code/token generation parameters. |
| `QMS_SERVER`, `QMS_USER`, `QMS_PASSWORD` | RabbitMQ host and credentials. |
| `KEY_SIZE`, `PRIVATE_KEY_FILENAME`, `PUBLIC_KEY_FILENAME` | Key generation and on-disk PEM path templates (`{UUID}` placeholder). |
| `ENVIRONMENT` | One of `development` / `staging` / `production` (selects the logger). |
| `VERSION` | App version surfaced in OpenAPI. |
| `VERIFY_TOKEN` | Default verification token. |
| `FACEBOOK_GRAPH_URL`, `FACEBOOK_WHATSAPP_MESSAGE`, `FACEBOOK_GRAPH_VERSION` | Meta Graph API endpoint templates and version (e.g. `v19.0`). |

> `config.env` is listed in `.gitignore` but a copy is **currently committed** — see the Security notice below. Treat the checked-in values as compromised.

---

## Running locally

Prerequisites: Python 3.11+ (uses `str | None` unions and `match` statements), a reachable MongoDB, and a RabbitMQ broker.

```bash
# 1. Create and activate a virtualenv
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Provide configuration
#    Edit config.env with your own MongoDB / RabbitMQ / Meta credentials

# 4. Run the API
uvicorn app:app --host 0.0.0.0 --port 5002 --reload
```

Open `http://localhost:5002/docs` for the Swagger UI.

---

## Running with Docker

```bash
# Build the image
docker build -t wh-python-fastapi-messenger:latest .

# Run it (exposes port 5002, 4 uvicorn workers)
docker run -it -p 5002:5002 --name wh-python-fastapi-messenger -d wh-python-fastapi-messenger:latest
```

Or use the convenience script [bootstrap.sh](bootstrap.sh), which clones the repo (`develop` branch), prunes old images/containers, rebuilds, and runs the container.

> Note: [compose-dev.yaml](compose-dev.yaml) is a Docker *Dev Environments* helper (it just runs `sleep infinity`), **not** a production compose file for this service.

---

## Logging

Configured via [logging_config.yaml](logging_config.yaml), applied on startup by `utils.configure_logging` (registered as a FastAPI `on_startup` hook). Logger selection is driven by `ENVIRONMENT`:

| Environment | Level | Handlers |
|---|---|---|
| `development` | DEBUG | console |
| `staging` | INFO | console + `application.log` |
| `production` | WARNING | `application.log` |

---


## License

Licensed under the **Apache License 2.0**. See [LICENSE](LICENSE).

Maintainer: **Jeremi Alcala** — <jeremialcala@gmail.com> · https://jeremi.web-ones.com
