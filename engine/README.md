# ms-python-metamsghandler

Microservicio en Python que **consume, procesa e interpreta** los mensajes entrantes de las plataformas de Meta (**Messenger, WhatsApp e Instagram**). Determina la intención del usuario mediante IA (Ollama), aplica una capa de seguridad (NVIDIA NeMo Guardrails) y publica un resultado clasificado para que un servicio aguas abajo entregue la respuesta.

El servicio consume webhooks crudos de Meta desde una cola de **RabbitMQ (AMQP)** y publica el `ResultadoClasificado` en otra cola.

---

## Pilares

- **Clean Architecture** — capas independientes de la tecnología: `domain`, `application`, `infrastructure`, `presentation`.
- **SOLID** — la aplicación depende de **puertos** (interfaces) del dominio; la infraestructura los implementa (inversión de dependencias).
- **OWASP** — sanitización estricta de inputs e IDs, mitigación de inyección de prompts (guardrails + validación de la salida del LLM).
- **SOC2** — logs de auditoría estructurados por etapa con PII enmascarada.

---

## Pipeline

```text
[RabbitMQ: cola de entrada]
        │
        ▼
AmqpConsumer (hilos + ACK threadsafe)        src/infrastructure/amqp
        │
        ▼
WebhookResolver → MessengerParser / WhatsAppParser / InstagramParser   (Fase 1)
        │   (identifica origen por el campo `object` y normaliza a MensajeEntrante)
        ▼
NeMoGuardrailsPolicy.evaluar()               (Fase 3)  → bloquea jailbreak / off-topic
        │
        ▼
OllamaIntentEngine.detectar()                (Fase 2)  → Intencion {etiqueta, tipo_respuesta, ...}
        │
        ▼
ResultadoClasificado → AmqpPublisher.publicar()  → [RabbitMQ: cola de salida]
```

La orquestación vive en [`ProcesarMensajeUseCase`](src/application/procesar_mensaje.py).

### Matriz de clasificación

| `tipo_respuesta` | Descripción |
|---|---|
| `texto`   | Consulta común / conversación simple. |
| `action`  | Requiere lógica de negocio externa (ej: consultar stock). |
| `adjunto` | Recepción de archivos (imágenes, PDFs, audios). |

> Esta entrega cubre las **Fases 1–3** (identificación de origen, intención y guardrails). Las estrategias de respuesta (Fase 4) y el hardening completo OWASP/SOC2 (Fase 5) son trabajo posterior.

---

## Estructura

```text
main.py                              # entrypoint; delega en presentation
src/
├── domain/
│   ├── enums/                       # Origen, TipoRespuesta, Status, ResponseCodes, KeyTypes
│   ├── models/                      # MensajeEntrante, Adjunto, Intencion, ResultadoClasificado, ResultadoGuardrail
│   └── ports/                       # WebhookParser, GuardrailsPolicy, IntentEngine, MessagePublisher
├── application/
│   └── procesar_mensaje.py          # ProcesarMensajeUseCase (orquesta el pipeline)
├── infrastructure/
│   ├── config/                      # Settings (pydantic-settings ← config.env)
│   ├── logging/                     # configure_logging (logging_config.yaml)
│   ├── shared/                      # constantes y utilidades (enmascarar PII, etc.)
│   ├── amqp/                        # AmqpConsumer + AmqpPublisher
│   ├── adapters/                    # parsers de webhooks Meta + WebhookResolver + sanitización
│   ├── llm/                         # OllamaIntentEngine + prompts
│   ├── guardrails/                  # NeMoGuardrailsPolicy + config/ (rails .yml/.co)
│   ├── persistence/                 # generación dinámica de modelos ORM/DTO
│   └── security/                    # operaciones JWE/JWK (opcional)
└── presentation/
    └── bootstrap.py                 # composición de dependencias + arranque del consumer
tests/                               # pirámide: unit, integration, contract, e2e, security
docs/                                # documentación AI-DLC por fase (00 a 06)
.ai-dlc/                             # gates, plantillas y mapeo OWASP
```

---

## Stack tecnológico

| Categoría | Tecnología |
|---|---|
| Lenguaje | Python 3.12 |
| Mensajería | RabbitMQ / AMQP (`pika`) |
| Motor de IA | Ollama (`ollama`, instancia local en `localhost:11434`) |
| Seguridad IA | NVIDIA NeMo Guardrails (`nemoguardrails`) |
| Validación / Settings | `pydantic`, `pydantic-settings` |
| Base de datos | MongoDB (`mongoengine`) — para JWK/JWE |
| Testing / Calidad | `pytest`, `pytest-cov`, `pylint`, `flake8`, `tox` |
| Contenerización | Docker, Kubernetes |

---

## Configuración

Copia [`config.env.example`](config.env.example) a `config.env` y completa los valores. Variables nuevas relevantes:

| Variable | Descripción |
|---|---|
| `queue_name`, `amqp_exchange`, `amqp_routing_key` | Cola/exchange de **entrada** (webhooks Meta). |
| `output_queue_name`, `output_routing_key` | Cola/exchange de **salida** (resultado clasificado). |
| `ollama_host` | URL de Ollama (por defecto `http://localhost:11434`). |
| `ollama_model` | Modelo a usar para intención y guardrails (ej: `llama3.1`). |
| `guardrails_config_path` | Ruta a la config de NeMo (`src/infrastructure/guardrails/config`). |

Requisitos de ejecución: **RabbitMQ** accesible y **Ollama** con el modelo descargado (`ollama pull llama3.1`).

---

## Desarrollo y pruebas (Docker / WSL)

> ⚠️ `nemoguardrails` arrastra `annoy`, una extensión nativa **sin wheel para Windows** que requiere un compilador C++. Por eso el desarrollo y los tests se ejecutan en **Docker/WSL (Linux)**, donde `annoy` compila con `build-essential`. La imagen está fijada a **Python 3.12** para respetar los *pins* de `requirements.txt`.

```bash
# Construir la imagen (instala dependencias, compila annoy)
docker build -t ms-metamsg .

# Ejecutar la batería de pruebas con cobertura dentro del contenedor
docker run --rm ms-metamsg pytest --cov=src tests/ -p no:warnings

# Ejecutar el servicio (montando config.env)
docker run --rm --env-file config.env ms-metamsg
```

Las pruebas unitarias mockean Ollama y el motor de guardrails, por lo que **no requieren** servicios externos.

---

## Despliegue

El servicio aún no está desplegado. [`deployment.yaml`](deployment.yaml) es un borrador heredado
de un template (nombre e imagen de otro servicio) y no sirve tal cual. Dónde y cómo se despliega
se decide en [ADR-0006](docs/02-design/adr/ADR-0006-placement-worker.md) y
[ADR-0007](docs/02-design/adr/ADR-0007-placement-serving-llm.md).

---

## Metodología AI-DLC

El repositorio sigue el estándar AI-DLC en su variante de un solo servicio
([ADR-0001](docs/00-project/adr/0001-adopcion-estructura-ai-dlc.md)).

| Carpeta | Contenido |
|---|---|
| [`docs/`](docs/README.md) | Charter, requisitos, arquitectura, threat model, ADRs y contrato AsyncAPI, por fase |
| [`.ai-dlc/`](.ai-dlc/) | Checklists de los gates 0 a 5 con su estado, plantillas y mapeo OWASP |
| [`tests/`](tests/README.md) | Pirámide de pruebas |
| [`CHANGELOG.md`](CHANGELOG.md) | Cambios notables |
| [`SECURITY.md`](SECURITY.md) · [`CONTRIBUTING.md`](CONTRIBUTING.md) | Política de seguridad y flujo de trabajo |

Ningún gate está cerrado todavía. Las brechas de seguridad conocidas están en
[`docs/02-design/threat-model.md`](docs/02-design/threat-model.md).

---

## Autor

**Jeremi Alcalá** — [github.com/jeremialcala](https://github.com/jeremialcala)
