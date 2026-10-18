# 02 — Diseño (Gate 1)

| Documento | Contenido | Estado |
|---|---|---|
| [Arquitectura](architecture.md) | Contextos, C4 Container y Component, flujos críticos, ciclo de vida del mensaje, modelo de datos y patrones de seguridad | approved (Gate 1, 2026-10-12) |
| [Threat model](threat-model.md) | DFD, STRIDE, DREAD y hallazgos del diseño | approved (Gate 1, 2026-10-12) |
| [OpenAPI de la gestión](contracts/openapi.yaml) | Contrato de la API de gestión tal como está construida | Generado |
| [OpenAPI del webhook](contracts/openapi-webhook.yaml) | Contrato de lo que llama Meta, el otro servicio (ADR-0018) | Generado |
| [AsyncAPI](contracts/asyncapi.yaml) | Contrato del mensaje de la cola `llm` tal como se publica hoy | approved (Gate 1, 2026-10-12) |
| [AsyncAPI 2.0.0](contracts/asyncapi-v2.yaml) | Contrato objetivo del bus de eventos (Bifröst): cuatro streams, sujetos, clave de orden y `traceparent` | proposed (Gate 1 del refactor, 2026-10-18) |

Las decisiones se registran como ADR en [`docs/00-project/adr/`](../00-project/adr/), una decisión por ADR.

El OpenAPI no se edita a mano: se regenera con `python .ai-dlc/scripts/gen_openapi.py`. Las pruebas de
`tests/contract` fallan si cualquiera de los dos contratos deja de coincidir con el código.

Cierra con `.ai-dlc/gates/gate-1-design.md`.
