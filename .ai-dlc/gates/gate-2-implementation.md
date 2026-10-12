# Gate 2 — Implementación (cierre de Fase 03)

- [ ] SAST sin findings críticos/altos
- [ ] Dependencias verificadas (SCA) — sin deps alucinadas ni vulnerables (A03)
- [ ] Cobertura ≥ 80% branch
- [ ] Dual review completado (humano + IA)
- [ ] Sin secretos en el código

## Estado (2026-10-12): sin empezar

Punto de partida medido: cobertura por ramas del 60 %, FastAPI 0.110.0 y Starlette 0.36.3 fijados por
`starlette~=0.36.3`, sin SAST, sin SCA y sin escaneo de secretos en el pipeline.

## Heredado del Gate 1

- Los siete trabajos de la sección "Brecha entre lo construido y el diseño" de
  [`architecture.md`](../../docs/02-design/architecture.md), en el orden que marca el threat model.
- Los hallazgos H1 a H6 de [`threat-model.md`](../../docs/02-design/threat-model.md), empezando por los valores
  por defecto que se calculan al importar (H1).
- Si cambia la API o el mensaje de la cola, los contratos de `docs/02-design/contracts/` cambian con ellos: las
  pruebas de `tests/contract` lo exigen.
