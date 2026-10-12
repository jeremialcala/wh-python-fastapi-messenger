# Gate 1 — Diseño (cierre de Fase 02)

- [ ] Arquitectura C4 validada (`docs/02-design/`)
- [ ] Threat model STRIDE de sistema + servicios con superficie relevante
- [ ] ADRs registrados para decisiones clave
- [ ] Contratos de API definidos
- [ ] Patrones de seguridad seleccionados por amenaza priorizada (DREAD)

## Estado (2026-10-12): en revisión, sin aprobar

Los documentos existen en estado `review` y cuatro ADR están en `proposed`. Ninguna casilla se marca hasta que el
decisor los apruebe.

| Criterio | Evidencia | Qué falta |
|---|---|---|
| Arquitectura C4 | [`architecture.md`](../../docs/02-design/architecture.md): Container, Component, dos secuencias, ciclo de vida del mensaje, ER y puertos | Aprobación |
| Threat model | [`threat-model.md`](../../docs/02-design/threat-model.md): DFD con seis fronteras, 21 amenazas con STRIDE y DREAD, y seis hallazgos | Aprobación. T10 se apoya en la documentación del motor, sin verificar aquí |
| ADRs | ADR-0002 a ADR-0008 aceptados; ADR-0009 a ADR-0012 propuestos, en `docs/00-project/adr/` | Aceptar o corregir los cuatro propuestos |
| Contratos | [`openapi.yaml`](../../docs/02-design/contracts/openapi.yaml), generado de la aplicación, y [`asyncapi.yaml`](../../docs/02-design/contracts/asyncapi.yaml); ocho pruebas en `tests/contract` | Describen lo construido; la versión objetivo de la cola depende de ADR-0011 |
| Patrones por amenaza | Tabla de patrones en `architecture.md`, ordenada por DREAD | Aprobación |

## ADR pendientes de decisión

| ADR | Propone | Resuelve del Gate 0 |
|---|---|---|
| [ADR-0009](../../docs/00-project/adr/0009-parametros-del-token-de-autenticacion.md) | `ES256` para la firma, 60 segundos de vida y un solo uso por token | Parámetros del token |
| [ADR-0010](../../docs/00-project/adr/0010-clave-de-cifrado-de-datos-por-cliente.md) | Una clave de datos por cliente, generada y custodiada por la plataforma, con índice ciego para los números | Custodia de la clave de cifrado de datos |
| [ADR-0011](../../docs/00-project/adr/0011-contrato-de-la-cola.md) | El sobre del gateway como contrato para los dos canales, versión 1, con deduplicación en el motor | Contrato de la cola |
| [ADR-0012](../../docs/00-project/adr/0012-aislamiento-por-cliente-en-la-capa-de-datos.md) | `clientId` en cada documento y capa de repositorio obligatoria | — |

## Qué significa cerrar este gate

Aprueba el **diseño**. La sección "Brecha entre lo construido y el diseño" de `architecture.md` lista lo que queda
por construir; nada de eso está hecho.
