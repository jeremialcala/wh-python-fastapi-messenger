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
- [Deployment](#deployment)
- [Logging](#logging)
- [Security](#security)
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
| ASGI server | Uvicorn (workers from `WEB_CONCURRENCY`) |
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
├── src/                    # The application (this is all the image contains)
│   ├── app.py                  # FastAPI app: middleware, auth dependencies and all route definitions
│   ├── logging_config.yaml     # Per-environment logging configuration
│   ├── classes/                # Pydantic DTOs + mongoengine entities
│   │   ├── tool_settings.py        # Settings (reads config.env)
│   │   ├── entity_*.py             # MongoDB documents (ChatBot, Contact, Event, Jwk, ...)
│   │   └── dto_*.py                # Request/response & Facebook payload models
│   ├── controller/             # Business logic layer
│   │   ├── chatbot.py              # CRUD for bots, phones and rules
│   │   ├── intents.py              # CRUD for intents and their tool schemas
│   │   ├── facebook.py             # Contact identification + Graph API profile lookups
│   │   ├── messages.py             # Inbound message processing + WhatsApp send
│   │   ├── events.py               # Event / EventAction tracking
│   │   └── amqp_broker.py          # RabbitMQ publisher
│   ├── constants/              # Static strings: docs metadata, headers, FB keys, formats
│   ├── enums/                  # Status, Environment, KeyTypes enums
│   └── utils/                  # logging config, code generators, signature check, JWK/PEM key helpers
│
├── tests/                  # Test pyramid: unit/ integration/ contract/ e2e/ security/ (see tests/README.md)
├── docs/                   # AI-DLC documentation, one folder per phase (00-project ... 06-monitoring)
├── .ai-dlc/                # Gate checklists, templates and OWASP mapping
├── deploy/                 # docker-compose.yml for the server (see Deployment)
├── .github/                # Workflows (ci, build, GitFlow guard) and CODEOWNERS
│
├── Dockerfile              # python:3.12-slim image, unprivileged user, uvicorn on :5002
├── .dockerignore           # Keeps config.env, certs/ and dev files out of the build context
├── requirements.txt        # Python dependencies
├── pytest.ini              # Puts src/ on the path: run `pytest` from the root
├── config.env.example      # Template for config.env (git-ignored, loaded by pydantic-settings)
├── CHANGELOG.md  SECURITY.md  CONTRIBUTING.md
├── bootstrap.sh            # Legacy: clone + rebuild + run. It prunes ALL unused Docker data on the host
├── compose-dev.yaml        # Docker "dev environment" helper (not the app runtime)
├── certs/                  # Per-event RSA private keys (*.pem), git-ignored
└── prototypes/             # Throwaway experiments (ignored in .gitignore)
```

The repository follows the AI-DLC structure for a single service ([ADR-0001](docs/00-project/adr/0001-adopcion-estructura-ai-dlc.md)). The methodology documents under `docs/` and `.ai-dlc/` are written in Spanish.

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

Defined in [src/app.py](src/app.py):

1. **`interceptor` HTTP middleware** runs for every request:
   - Records start time and sets `X-Processing-Time` on the response.
   - Builds an `EventTransport` DTO (uuid, resource, method, client origin) — event creation is currently scaffolded (`ctr_create_event` call is commented out) and `request.state.event_id` is set to `None`.
   - Wraps `call_next` in try/except/finally so a baseline `500` `ResponseData` is always returned on failure.
2. **Dependencies** authenticate the request before any handler runs: `X-API-Key` on the management endpoints, `X-Hub-Signature-256` on inbound notifications (see [Security](#security)).
3. **Route handlers** call the matching `ctr_*` controller and return its `Response`.
4. **Controllers** optionally emit `EventAction` records (only when an `eventId` is present), persist via mongoengine, and—for inbound messages—publish to RabbitMQ. The publish is awaited and confirmed by the broker before Meta gets its `200`.

---

## API endpoints

Base URL (local Docker): `http://localhost:5002`
Interactive docs: `http://localhost:5002/docs` (Swagger) · `http://localhost:5002/redoc`

Only the two webhook routes (`GET` and `POST /chat/{bot_id}`) and `GET /health` are public. Every other endpoint requires the `X-API-Key` header and answers `401` without it.

### Bot management — tag `Bot`

| Method | Path | Body | Description |
|---|---|---|---|
| `POST` | `/bot` | `ChatbotRequest` | Create a chatbot. Generates a `uuid` and a signed `verifyToken` (JWT). Returns `BotResponse`. |

`ChatbotRequest` fields: `name`, `role`, `description`, `tone`.

### Chat / webhook — tag `Chat`

| Method | Path | Description |
|---|---|---|
| `GET`  | `/chat/{bot_id}` | **Meta webhook verification.** Validates `hub.mode=subscribe` and `hub.verify_token` against the bot's `verifyToken`, then echoes `hub.challenge` as plain text. Anything else is a `403`. |
| `POST` | `/chat/{bot_id}` | **Inbound message handler.** Requires a valid `X-Hub-Signature-256` (`403` otherwise). Accepts a `FacebookRequest`; dispatches Messenger (`object=page`) or WhatsApp (`object=whatsapp_business_account`) payloads. Answers `200` once RabbitMQ has confirmed the message, `503` if the broker is unavailable so that Meta retries. |
| `POST` | `/chat/{bot_id}/phones` | Register a WhatsApp phone number (`ChatbotPhoneRequest`: `environment`, `phoneNumber`, `phoneId`). |
| `GET`  | `/chat/{bot_id}/phones?environment=` | List the bot's phone numbers; with `environment` returns the latest match for that environment. |
| `GET`  | `/chat/{bot_id}/info` | Return the bot's stored info (`chatbot_info()`). |
| `GET`  | `/chat/{bot_id}/rules` | Build and return the assembled LLM system prompt from the bot's persona + stored rules. |
| `POST` | `/chat/{bot_id}/rules` | Add one or more rules (`RulesRequest.rules: list[str]`) to the bot. |

> The `/answers` endpoint is described in the OpenAPI prose but is **not yet implemented** in `src/app.py`.

---

## Data model (MongoDB collections)

All entities are mongoengine `Document`s and connect to the database configured in `config.env`.

| Entity | File | Key fields | Purpose |
|---|---|---|---|
| `ChatBot` | `entity_chatbot.py` | `uuid`, `name`, `role`, `description`, `tone`, `verifyToken`, `facebookToken`, `whatsappToken`, `appSecret`, `status` | A chatbot tenant. `generate_verification_token()` mints a signed JWT used for Meta webhook verification. |
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
- **JWE payloads** — Before publishing to RabbitMQ, `QueueMessage.set_jwe_body()` looks up the event's JWK and encrypts the normalized `MessageBody` (botId, type, contact, message) as a compact JWE. Downstream consumers decrypt with the corresponding private PEM (see `src/utils/key_management.py`).
- **Bot verification tokens** — `Credentials` builds an HS256-signed JWT stored as the bot's `verifyToken`, compared against Meta's `hub.verify_token` during webhook setup.

---

## Configuration

Settings are loaded by `src/classes/tool_settings.py` (`pydantic-settings`) from **`config.env`**; start from [config.env.example](config.env.example). Environment variables override the file. Required variables:

| Variable | Description |
|---|---|
| `ADMIN_API_KEY` | Key for the management endpoints (`X-API-Key` header). At least 32 characters; the app does not start without it. |
| `FACEBOOK_APP_SECRET` | Meta App Secret that verifies webhook signatures. Optional only if every chatbot carries its own `appSecret`. |
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

> `config.env` and `certs/` are git-ignored and have never been committed. Keep it that way: the repository is public.

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
#    Copy config.env.example to config.env and fill in your own
#    MongoDB / RabbitMQ / Meta credentials and the ADMIN_API_KEY

# 4. Run the API
uvicorn app:app --app-dir src --host 0.0.0.0 --port 5002 --reload

# 5. Run the tests (no services nor config.env needed)
pytest
```

Open `http://localhost:5002/docs` for the Swagger UI.

---

## Running with Docker

```bash
# Build the image
docker build -t wh-python-fastapi-messenger:latest .

# Run it. Settings are not baked into the image: pass them at run time
docker run -d -p 127.0.0.1:5002:5002 --env-file config.env --name wh-python-fastapi-messenger wh-python-fastapi-messenger:latest
```

The image runs as an unprivileged user, ships neither `config.env` nor `certs/` (see [.dockerignore](.dockerignore)), and starts one worker unless `WEB_CONCURRENCY` says otherwise. `GET /health` is its liveness probe.

> [bootstrap.sh](bootstrap.sh) predates this image and runs `docker system prune -a -f`: do not use it on a host that runs anything else.
>
> [compose-dev.yaml](compose-dev.yaml) is a Docker *Dev Environments* helper (it just runs `sleep infinity`), **not** a compose file for this service.

---

## Deployment

Merging to `main` builds and deploys:

1. The [build](.github/workflows/build.yml) workflow runs the tests and, if they pass, pushes `ghcr.io/jeremialcala/wh-python-fastapi-messenger:sha-<7>` to GHCR.
2. GitHub sends `workflow_run` to the server's webhook receiver ([despliegue-continuo](https://github.com/higerotech/despliegue-continuo)), which pulls that tag, brings the compose project up, checks `/health` and rolls back to the previous tag if it fails.

One-time setup on the server:

- `/srv/apps/bots-gateway/docker-compose.yml`, copied from [deploy/docker-compose.yml](deploy/docker-compose.yml), and next to it a `.env` with the keys of [config.env.example](config.env.example).
- The external Docker network `hermod` and a RabbitMQ user for the gateway (`QMS_SERVER=hermod`).
- The GHCR package set to **Public**, because the receiver pulls anonymously.
- An entry in the receiver's `apps.yml`, and the `workflow_run` webhook on this repository:

  ```yaml
  - name: bots-gateway
    repo: jeremialcala/wh-python-fastapi-messenger
    branch: main
    event: workflow_run
    workflow: build
    project_dir: /srv/apps/bots-gateway
    image: ghcr.io/jeremialcala/wh-python-fastapi-messenger
    health_url: http://127.0.0.1:5002/health
    health_timeout: 120
    health_interval: 3
    rollback: true
  ```

The container listens on loopback only. The tunnel in front of it must publish `/chat/<uuid>` and nothing else.

---

## Logging

Configured via [src/logging_config.yaml](src/logging_config.yaml), applied on startup by `utils.configure_logging` (registered as a FastAPI `on_startup` hook). Logger selection is driven by `ENVIRONMENT`:

| Environment | Level | Handlers |
|---|---|---|
| `development` | DEBUG | console |
| `staging` | INFO | console + `application.log` |
| `production` | WARNING | console (kept and rotated by Docker) |

---

## Security

| Surface | Control |
|---|---|
| Management endpoints (`/bot`, `/chat/{bot_id}/phones`, `/info`, `/rules`, `/intents`, `/tools`) | `X-API-Key` header compared in constant time against `ADMIN_API_KEY`. `401` otherwise. |
| `GET /chat/{bot_id}` (verification) | `hub.verify_token` compared in constant time against the bot's `verifyToken`. `403` otherwise. |
| `POST /chat/{bot_id}` (notifications) | `X-Hub-Signature-256`: HMAC-SHA256 of the raw body keyed with the Meta App Secret. `403` otherwise. |

- **App Secret lookup** — the chatbot's own `appSecret` if the document has one, else `FACEBOOK_APP_SECRET`. With neither, every notification is rejected. Like the page and WhatsApp tokens, `appSecret` is written straight into the chatbot document; no endpoint returns it.
- **Delivery** — a notification gets its `200` only after RabbitMQ confirms the publish. Meta redelivers on `503`, so the consumer of the `llm` queue must tolerate duplicates (deduplicate on the message id).
- **Logs** — the request interceptor logs neither query strings nor headers, and the key that signs a bot's `verifyToken` is no longer written to the log.
- **Still open** — `/docs`, `/redoc` and `/openapi.json` are served without a key, and there is no rate limiting: publish only `/chat/{bot_id}` at the edge and keep everything else on the private network. `src/controller/messages.py` still logs the content of inbound messages at `INFO`.

To sign a test notification by hand:

```bash
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$FACEBOOK_APP_SECRET" | sed 's/^.* //')
curl -X POST "http://localhost:5002/chat/$BOT_ID" -H 'Content-Type: application/json' \
     -H "X-Hub-Signature-256: sha256=$SIG" -d "$BODY"
```

---


## License

Licensed under the **Apache License 2.0**. See [LICENSE](LICENSE).

Maintainer: **Jeremi Alcala** — <jeremialcala@gmail.com> · https://jeremi.web-ones.com
