# 02 — Diseño (Gate 1)

| Documento | Contenido | Estado |
|---|---|---|
| [Arquitectura](architecture.md) | Contextos, C4 Container y Component, flujos críticos, ciclo de vida del mensaje, modelo de datos y patrones de seguridad | approved (Gate 1, 2026-10-12) |
| [Threat model](threat-model.md) | DFD, STRIDE, DREAD y hallazgos del diseño | approved (Gate 1, 2026-10-12) |
| [OpenAPI](contracts/openapi.yaml) | Contrato de la API HTTP tal como está construida | Generado |
| [AsyncAPI](contracts/asyncapi.yaml) | Contrato del mensaje de la cola `llm` tal como se publica hoy | approved (Gate 1, 2026-10-12) |

Las decisiones se registran como ADR en [`docs/00-project/adr/`](../00-project/adr/), una decisión por ADR.

El OpenAPI no se edita a mano: se regenera con `python .ai-dlc/scripts/gen_openapi.py`. Las pruebas de
`tests/contract` fallan si cualquiera de los dos contratos deja de coincidir con el código.

Cierra con `.ai-dlc/gates/gate-1-design.md`.
