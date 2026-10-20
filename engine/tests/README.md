# Tests — pirámide AI-DLC

| Nivel | Qué prueba | Estado |
|---|---|---|
| `unit/` | Parsers, sanitización, caso de uso, motor de intención, guardrails y publicador, con Ollama, NeMo y pika mockeados | 29 tests |
| `integration/` | Contra RabbitMQ real: ACK y NACK, DLQ, reentrega, publicación confirmada | Vacío |
| `contract/` | Que lo publicado cumple `docs/02-design/contracts/asyncapi.yaml` | Vacío |
| `e2e/` | Webhook en la cola de entrada hasta resultado en la de salida, con el modelo real | Vacío |
| `security/` | Amenazas T1 a T12: corpus de jailbreaks, payloads hostiles, URL internas, PII en logs | Vacío |

```bash
pytest                                  # toda la pirámide
pytest tests/unit --cov=src --cov-branch
```

`pyproject.toml` añade la raíz del repo al `sys.path`, así que `from src...` resuelve desde
cualquier nivel. Las fixtures de webhooks están en `tests/unit/conftest.py`; al añadir otro
nivel que las necesite, hay que subirlas a `tests/conftest.py`.

`nemoguardrails` no se instala en Windows (ver README). Los tests unitarios no lo necesitan.
