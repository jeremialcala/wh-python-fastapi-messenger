# Gate 2 — Implementación (cierre de Fase 03)

- [ ] SAST sin findings críticos/altos
- [ ] Dependencias verificadas (SCA) — sin deps alucinadas ni vulnerables (A03)
- [ ] Cobertura ≥ 80% branch
- [ ] Dual review completado (humano + IA)
- [ ] Sin secretos en el código

## Estado (2026-10-12): en curso

| Criterio | Estado | Evidencia |
|---|---|---|
| SAST sin hallazgos críticos o altos | Gate activo | Workflow `Seguridad`, trabajo `sast`: CodeQL sobre todo el código, también en los pull requests, y el build se rompe con cualquier hallazgo de seguridad alto o crítico (`security-severity` ≥ 7,0). Primer análisis completo: 92 resultados; uno alto, que era un falso positivo por el nombre de una constante y ya no aparece; 28 medios de `py/log-injection`, abiertos; y 63 de calidad |
| Dependencias verificadas (SCA) | Gate activo | `requirements.lock` y `requirements-dev.lock` con hashes; trabajo `dependencias` con `pip-audit` sobre el lock. Al añadirlo: 14 vulnerabilidades conocidas con las dependencias anteriores, todas de Starlette 0.36.3, y ninguna con las nuevas |
| Cobertura ≥ 80 % por ramas | **No cumple: 61 %** | El CI exige un suelo del 60 % para que no baje. `controller/chatbot.py`, `intents.py` y `facebook.py` están entre el 10 y el 14 % |
| Dual review | Pendiente | — |
| Sin secretos en el código | Gate activo | Trabajo `secretos`: gitleaks sobre la historia completa. Al añadirlo: 56 commits, ningún hallazgo |

"Gate activo" significa que el control existe y rompe el build; la casilla se marca al cerrar el gate, con el
resto de criterios cumplidos.

### Hecho en la base

- Dependencias actualizadas: FastAPI 0.110 → 0.143 y Starlette 0.36 → 1.7. Se retiran once paquetes que el código
  no importaba.
- La imagen instala solo las dependencias de ejecución, desde el lock y verificando hashes.
- Corregido el hallazgo H1: los valores por defecto de las entidades se calculan por objeto.

### Pendiente que deja el primer análisis estático

- 28 hallazgos medios de `py/log-injection` en `app.py` y los controladores: valores de la petición escritos en el
  log tal cual. No rompen el build porque están por debajo del umbral, pero se cierran con el trabajo de logs sin
  datos personales.

## Heredado del Gate 1

- Los siete trabajos de la sección "Brecha entre lo construido y el diseño" de
  [`architecture.md`](../../docs/02-design/architecture.md), en el orden que marca el threat model.
- Los hallazgos H2 a H6 de [`threat-model.md`](../../docs/02-design/threat-model.md). H1, los valores por defecto
  que se calculaban al importar, está corregido.
- Si cambia la API o el mensaje de la cola, los contratos de `docs/02-design/contracts/` cambian con ellos: las
  pruebas de `tests/contract` lo exigen.
