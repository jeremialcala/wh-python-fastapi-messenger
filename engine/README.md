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
test/                                # pruebas unitarias (pytest)
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
docker run --rm ms-metamsg pytest --cov=src test/ -p no:warnings

# Ejecutar el servicio (montando config.env)
docker run --rm --env-file config.env ms-metamsg
```

Las pruebas unitarias mockean Ollama y el motor de guardrails, por lo que **no requieren** servicios externos.

---

## Despliegue en Kubernetes

[`deployment.yaml`](deployment.yaml) define un `Deployment` en el namespace `chatters-pro`.

```bash
kubectl apply -f deployment.yaml
```

---

## Autor

**Jeremi Alcalá** — [github.com/jeremialcala](https://github.com/jeremialcala)
