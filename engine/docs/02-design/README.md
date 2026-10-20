# 02 — Diseño (Gate 1)

| Documento | Contenido |
|---|---|
| [architecture.md](architecture.md) | Contextos acotados, C4 Container y Component, secuencia, estados, modelo de datos, patrones de seguridad |
| [threat-model.md](threat-model.md) | DFD, STRIDE, DREAD (T1 a T12), controles y observaciones para revisión humana |
| [contracts/asyncapi.yaml](contracts/asyncapi.yaml) | Contrato AsyncAPI 3.0 de las colas de entrada y de salida |

## Registro de ADRs

La numeración es única. Las ADRs de sistema viven en `docs/00-project/adr/`; las de placement,
en `docs/02-design/adr/`.

| ID | Decisión | Estado |
|---|---|---|
| [ADR-0001](../00-project/adr/0001-adopcion-estructura-ai-dlc.md) | Adopción de AI-DLC en variante polyrepo | accepted |
| [ADR-0002](../00-project/adr/0002-arquitectura-hexagonal-puertos-adaptadores.md) | Arquitectura limpia con puertos y adaptadores | accepted (retroactiva) |
| [ADR-0003](../00-project/adr/0003-consumo-amqp-hilos-ack-manual.md) | Consumo AMQP con un hilo por mensaje y confirmación manual | accepted (retroactiva) |
| [ADR-0004](../00-project/adr/0004-intencion-llm-local-salida-no-confiable.md) | LLM autoalojado con salida tratada como no confiable | accepted (retroactiva) |
| [ADR-0005](../00-project/adr/0005-guardrails-entrada-nemo-fail-closed.md) | Rail de entrada con NeMo Guardrails, fail-closed | accepted (retroactiva) |
| [ADR-0006](adr/ADR-0006-placement-worker.md) | Placement del worker | proposed |
| [ADR-0007](adr/ADR-0007-placement-serving-llm.md) | Placement del serving del LLM | proposed |

## Regenerar el contrato

Los esquemas de salida se derivan de los modelos pydantic con `model_json_schema()`. Si cambia
`src/domain/models`, hay que regenerar `contracts/asyncapi.yaml` y validarlo:

```bash
npx -y @asyncapi/cli validate docs/02-design/contracts/asyncapi.yaml
```

Cierre: `.ai-dlc/gates/gate-1-design.md`.
