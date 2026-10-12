# Gate 0 — Requisitos (cierre de Fase 01)

No avanzar a diseño hasta cumplir TODO:

- [ ] Requisitos funcionales documentados en `docs/01-requirements/`
- [ ] Requisitos de seguridad mapeados a OWASP ASVS
- [ ] Escenarios **negativos / de abuso** definidos
- [ ] Threat assessment inicial realizado
- [ ] Datos clasificados (`docs/00-project/data-classification.md`)
- [ ] Charter y glosario aprobados

## Estado (2026-10-12): en revisión, sin aprobar

Los cuatro documentos existen como borradores en estado `review`. Ninguna casilla se marca hasta que el decisor
los apruebe.

| Criterio | Evidencia | Qué falta |
|---|---|---|
| Requisitos funcionales | [PRD BAAS-001](../../docs/01-requirements/mvp-baas-gateway.md): RF01–RF11 y RNF01–RNF07, cada uno con su estado | Aprobación |
| Seguridad mapeada a ASVS | PRD: RS01–RS17 con sección de ASVS 4.0.3 y OWASP Top 10:2025; `requirementDiagram` | Confirmar el nivel ASVS (se propone L2) |
| Escenarios de abuso | PRD: AB01–AB14; `journey` | Aprobación |
| Threat assessment inicial | PRD: DFD con cuatro fronteras y `quadrantChart` DREAD | La frontera con el motor de respuestas está sin definir |
| Datos clasificados | [Clasificación de datos](../../docs/00-project/data-classification.md) | Retención, región de la base y alcance de "los números" |
| Charter y glosario | [Charter](../../docs/00-project/charter.md) con `mindmap`; [glosario](../../docs/00-project/glossary.md) | Aprobación; dos SLO sin fijar |

Las ocho decisiones que bloquean la aprobación están en la sección "Decisiones abiertas" del PRD.

Al aprobar: marcar las casillas, pasar los cuatro documentos a `approved` y cortar la versión `0.1.0` en el
`CHANGELOG.md`.
