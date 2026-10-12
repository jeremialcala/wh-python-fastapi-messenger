# Gate 0 — Requisitos (cierre de Fase 01)

No avanzar a diseño hasta cumplir TODO:

- [x] Requisitos funcionales documentados en `docs/01-requirements/`
- [x] Requisitos de seguridad mapeados a OWASP ASVS
- [x] Escenarios **negativos / de abuso** definidos
- [x] Threat assessment inicial realizado
- [x] Datos clasificados (`docs/00-project/data-classification.md`)
- [x] Charter y glosario aprobados

**Aprobado el 2026-10-12 por Jeremi Alcala.** Cortada la versión `0.1.0`; charter, glosario, clasificación de
datos y PRD en `approved`.

| Criterio | Evidencia |
|---|---|
| Requisitos funcionales | [PRD BAAS-001](../../docs/01-requirements/mvp-baas-gateway.md): RF01–RF12 y RNF01–RNF07, cada uno con su estado |
| Seguridad mapeada a ASVS | PRD: RS01–RS18 con sección de ASVS 4.0.3, nivel L2, y OWASP Top 10:2025; `requirementDiagram` |
| Escenarios de abuso | PRD: AB01–AB16; `journey` |
| Threat assessment inicial | PRD: DFD con cinco fronteras y `quadrantChart` DREAD |
| Datos clasificados | [Clasificación de datos](../../docs/00-project/data-classification.md), con roles GDPR, inventario y retención |
| Charter y glosario | [Charter](../../docs/00-project/charter.md) con `mindmap`; [glosario](../../docs/00-project/glossary.md) |

## Qué significa este cierre

El gate aprueba los **requisitos**, no su cumplimiento. El gateway de hoy sigue siendo de un solo operador: de los
37 requisitos, 9 están construidos, 12 parciales, 14 pendientes y 2 sin medir. Lo que falta por construir está
identificado y priorizado; no está hecho.

## HITL

Decisiones del 2026-10-12, recogidas en la sección "Decisiones" del PRD:

- El motor de respuestas entrega la respuesta al usuario (ADR-0002) y pide la configuración del bot al gateway con
  el `bot_id` (ADR-0003).
- Solo el webhook se autentica con la firma de Meta; el resto, con un JWT firmado por el cliente dentro de un JWE
  (ADR-0004, ADR-0005).
- La gestión se queda en red privada hasta que existan el registro de clientes y el JWE.
- El cifrado con la clave del cliente cubre el número del contacto y el número del bot.
- Nivel ASVS L2.
- Retención: 24 horas en la cola y 12 meses sin actividad para un contacto, como máximos que el cliente puede
  acortar.
- Sin SLO comprometido hasta medir en producción.

## Queda abierto sin bloquear el gate

- Dos datos por aportar: si se designa delegado de protección de datos, y la región del clúster de Atlas.
- Tres decisiones de diseño que pasan al Gate 1: parámetros del token, contrato de la cola y custodia de la clave
  de cifrado de datos.
- Dos entregables anteriores al primer cliente externo: contrato de encargo y procedimiento de aviso de brechas.
