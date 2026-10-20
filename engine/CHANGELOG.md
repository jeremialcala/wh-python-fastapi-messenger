# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y este proyecto se adhiere a [Versionado Semántico](https://semver.org/lang/es/).

Las versiones se cortan al cerrar cada gate de AI-DLC: Gate 0 → 0.1.0, Gate 1 → 0.2.0,
Gate 2 → 0.3.0, Gate 3 → 0.4.0, Gate 4 → 0.5.0, Gate 5 → 1.0.0. Ningún gate está cerrado
todavía, así que todo lo documentado sigue en `[Unreleased]`. El historial de commits anterior
a este fichero está en `docs/03-implementation/repo-history.md`.

## [Unreleased]

### Añadido
- Estructura AI-DLC en variante polyrepo: `.ai-dlc/` (gates 0 a 5 con su estado, plantillas,
  mapeo OWASP con anexo del servicio) y `docs/00-project` a `docs/06-monitoring` (ADR-0001).
- Fase 00: charter con mapa mental del alcance, glosario del lenguaje ubicuo y clasificación
  de datos (GDPR y leyes LatAm).
- Fase 01: PRD MMH-F01 con C4 Context, journey, 12 escenarios de abuso, 8 requisitos
  funcionales, 14 requisitos de seguridad mapeados a ASVS, trazabilidad y threat assessment inicial.
- Fase 02: `architecture.md` (C4 Container y Component, secuencia, estados, ER, clases),
  `threat-model.md` (STRIDE y DREAD, T1 a T12) y contrato AsyncAPI 3.0 generado desde los
  modelos pydantic.
- ADR-0002 a ADR-0005: decisiones ya implementadas (puertos y adaptadores, consumo AMQP, LLM
  autoalojado con salida no confiable, guardrails fail-closed).
- ADR-0006 y ADR-0007 (`proposed`): placement del worker y del serving del LLM, con matriz de
  performance por dólar y precios consultados el 2026-10-12.
- Fase 03: `repo-history.md`, generado desde `git log`.
- `tests/README.md` y los niveles `integration`, `contract`, `e2e` y `security` de la pirámide, vacíos.
- `SECURITY.md`, `CONTRIBUTING.md`, `.github/CODEOWNERS` y un esqueleto de
  `.github/workflows/security-gates.yml` de ejecución manual.
- `.ai-dlc/scripts/`: generadores del contrato AsyncAPI y del historial del repo.

### Cambiado
- `test/` pasa a `tests/unit/`. `tox.ini`, `pyproject.toml` y el README apuntan a la ruta nueva.
- `pyproject.toml` configura pytest (`pythonpath`, `testpaths`) para que `from src...` resuelva
  también con el ejecutable `pytest`.
- README: mapa de la documentación AI-DLC y estructura actualizada.

### Seguridad
- Documentadas, sin corregir, las brechas halladas al reconstruir el threat model: datos
  personales en el log del publicador (T3), AMQP sin TLS (T5), pérdida silenciosa de mensajes
  por falta de DLQ y de confirmaciones (T6), llamada del rail sin timeout (T7) y ausencia de
  SCA, SBOM e imagen por digest (T8).

[Unreleased]: https://github.com/jeremialcala/ms-python-metamsghandler/compare/main...develop
