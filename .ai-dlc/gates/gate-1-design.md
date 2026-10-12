# Gate 1 — Diseño (cierre de Fase 02)

- [x] Arquitectura C4 validada (`docs/02-design/`)
- [x] Threat model STRIDE de sistema + servicios con superficie relevante
- [x] ADRs registrados para decisiones clave
- [x] Contratos de API definidos
- [x] Patrones de seguridad seleccionados por amenaza priorizada (DREAD)

**Aprobado el 2026-10-12 por Jeremi Alcala.** Cortada la versión `0.2.0`; arquitectura y threat model en `approved`,
y ADR-0002 a ADR-0012 en `accepted`.

| Criterio | Evidencia |
|---|---|
| Arquitectura C4 | [`architecture.md`](../../docs/02-design/architecture.md): Container, Component, dos secuencias, ciclo de vida del mensaje, ER y puertos |
| Threat model | [`threat-model.md`](../../docs/02-design/threat-model.md): DFD con seis fronteras, 21 amenazas con STRIDE y DREAD, y seis hallazgos |
| ADRs | ADR-0002 a ADR-0012, en `docs/00-project/adr/` |
| Contratos | [`openapi.yaml`](../../docs/02-design/contracts/openapi.yaml), generado de la aplicación, y [`asyncapi.yaml`](../../docs/02-design/contracts/asyncapi.yaml); ocho pruebas en `tests/contract` |
| Patrones por amenaza | Tabla de patrones en `architecture.md`, ordenada por DREAD |

## Qué significa este cierre

El gate aprueba el **diseño**, no su construcción. La sección "Brecha entre lo construido y el diseño" de
`architecture.md` lista siete trabajos por hacer; ninguno está hecho. El gateway sigue siendo de un solo operador,
con la clave de gestión única y los datos en claro.

## HITL

Decisiones del 2026-10-12:

| ADR | Decisión | Resuelve del Gate 0 |
|---|---|---|
| [ADR-0009](../../docs/00-project/adr/0009-parametros-del-token-de-autenticacion.md) | Firma `ES256`, cifrado con los algoritmos que ya usa el código, 60 segundos de vida y un solo uso por token | Parámetros del token |
| [ADR-0010](../../docs/00-project/adr/0010-clave-de-cifrado-de-datos-por-cliente.md) | Una clave de datos por cliente, generada y custodiada por la plataforma, con índice ciego para los números | Custodia de la clave de cifrado de datos |
| [ADR-0011](../../docs/00-project/adr/0011-contrato-de-la-cola.md) | El sobre del gateway como contrato para los dos canales, versión 1, con deduplicación en el motor | Contrato de la cola |
| [ADR-0012](../../docs/00-project/adr/0012-aislamiento-por-cliente-en-la-capa-de-datos.md) | `clientId` en cada documento y capa de repositorio obligatoria | — |

## Queda abierto sin bloquear el gate

- **Clave maestra** (ADR-0010): dónde vive y cómo se rota. Propuesto después del cierre en
  [ADR-0013](../../docs/00-project/adr/0013-openbao-como-gestor-de-secretos.md): un OpenBao propio.
- **PSID de Messenger** (ADR-0010): si se cifra también. El requisito habla de números.
- **Amenaza T10**: lo que el threat model dice de los guardrails del motor sale de su documentación; no se ha
  verificado desde este repositorio.
- **Contrato de la cola**: `asyncapi.yaml` describe el mensaje de hoy. La versión 1 de ADR-0011 es código por
  escribir en los dos repositorios.
- Siguen sin aportar los dos datos del Gate 0: delegado de protección de datos y región del clúster de Atlas.
