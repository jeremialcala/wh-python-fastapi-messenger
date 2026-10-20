# 02 — Diseño (Gate 1)

| Documento | Contenido |
|---|---|
| [architecture.md](architecture.md) | El servicio de antes (RabbitMQ, NeMo y Ollama): se rehace con ADR-0008 y ADR-0009 |
| [threat-model.md](threat-model.md) | El del servicio de antes: se rehace con ADR-0009 (T1, T5, T7 y T12) |
| [contracts/asyncapi-motor.yaml](contracts/asyncapi-motor.yaml) | Contrato AsyncAPI 3.0 del sobre que se pasan los workers por el stream `MOTOR` |

## Registro de ADRs

La numeración es única. Las ADRs de sistema viven en `docs/00-project/adr/`; las de placement,
en `docs/02-design/adr/`.

| ID | Decisión | Estado |
|---|---|---|
| [ADR-0001](../00-project/adr/0001-adopcion-estructura-ai-dlc.md) | Adopción de AI-DLC en variante polyrepo | accepted |
| [ADR-0002](../00-project/adr/0002-arquitectura-hexagonal-puertos-adaptadores.md) | Arquitectura limpia con puertos y adaptadores | accepted (retroactiva) |
| [ADR-0003](../00-project/adr/0003-consumo-amqp-hilos-ack-manual.md) | Consumo AMQP con un hilo por mensaje y confirmación manual | superseded por ADR-0008 |
| [ADR-0004](../00-project/adr/0004-intencion-llm-local-salida-no-confiable.md) | LLM autoalojado con salida tratada como no confiable | superseded por ADR-0009 |
| [ADR-0005](../00-project/adr/0005-guardrails-entrada-nemo-fail-closed.md) | Rail de entrada con NeMo Guardrails, fail-closed | superseded por ADR-0009, salvo fail-closed |
| [ADR-0006](adr/ADR-0006-placement-worker.md) | Placement del worker | proposed (se revisa: ADR-0009) |
| [ADR-0007](adr/ADR-0007-placement-serving-llm.md) | Placement del serving del LLM | superseded por ADR-0009 |
| [ADR-0008](adr/ADR-0008-seis-workers-sobre-bifrost.md) | El motor, seis workers sobre Bifröst | accepted |
| [ADR-0009](adr/ADR-0009-claude-como-llm.md) | Claude, por la API de Anthropic, como LLM del motor | accepted |

## El contrato

`contracts/asyncapi-motor.yaml` se escribe a mano, junto al sobre de `src/domain/models/sobre.py`, y
`tests/contract/test_contrato_motor.py` comprueba que el sobre que construye el código lo cumple. Para validar
el fichero con la CLI de AsyncAPI:

```bash
npx -y @asyncapi/cli validate docs/02-design/contracts/asyncapi-motor.yaml
```

Cierre: `.ai-dlc/gates/gate-1-design.md`.
