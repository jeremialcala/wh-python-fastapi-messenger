# Contribuir

## Ramas (GitFlow)

- El trabajo sale de `develop` en ramas `feature/*` y vuelve a `develop` por pull request.
- `main` solo recibe pull requests desde `develop`, `release/*` o `hotfix/*`. Lo comprueba el workflow
  `GitFlow guard` y lo exige el ruleset que protege `main`.
- Un merge a `main` construye la imagen y la despliega: ver la sección Despliegue del [README](README.md).

## Flujo: Red-Green-Refactor-Secure

1. **Red** — escribe la prueba que falla (incluye los casos de abuso).
2. **Green** — implementa lo mínimo para pasar.
3. **Refactor** — limpia respetando SOLID / Clean Architecture.
4. **Secure** — revisa los controles OWASP aplicables (`.ai-dlc/owasp-mapping.md`).

Las pruebas se ejecutan con `pytest` desde la raíz y no necesitan servicios externos ni `config.env`.

## Dual review

Toda PR requiere revisión humana más análisis asistido por IA.

## Gates

Cada fase cierra su gate (`.ai-dlc/gates/`) antes de avanzar. Un criterio sin evidencia se deja sin marcar.

## Commits y changelog

- Commits: `tipo(scope): mensaje` (`feat`, `fix`, `docs`, `test`, `chore`, `refactor`, `sec`).
- Todo cambio notable añade su entrada en la sección `[Unreleased]` de [CHANGELOG.md](CHANGELOG.md).
- Las versiones siguen SemVer a partir de `v0.0.1`. Cada gate cerrado corta una versión menor: la `0.1.0` con el
  Gate 0 y la `0.2.0` con el Gate 1.

## Idioma

La documentación se escribe en español: `docs/`, `.ai-dlc/`, el changelog y el README. Los mensajes de commit
pueden ir en inglés. El código se escribe en inglés: identificadores, comentarios y mensajes de log.
