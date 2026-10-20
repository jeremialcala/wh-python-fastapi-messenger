# 05 — Despliegue (Gate 4)

Fase sin documentar todavía. El servicio no está desplegado en ningún entorno.

Punto de partida:

- Dónde se despliega: [ADR-0006](../02-design/adr/ADR-0006-placement-worker.md) (worker) y
  [ADR-0007](../02-design/adr/ADR-0007-placement-serving-llm.md) (modelo), las dos en `proposed`.
- `deployment.yaml` en la raíz es un borrador heredado de un template: nombre e imagen de otro
  servicio. No sirve para desplegar.
- `.github/workflows/security-gates.yml` es un esqueleto de ejecución manual.

Lo que esta fase tiene que producir: `C4Deployment`, el flujo del pipeline con sus siete gates
de seguridad y el rollback, el plan de puesta en marcha, el runbook y el SBOM.

Cierre: `.ai-dlc/gates/gate-4-deployment.md`.
