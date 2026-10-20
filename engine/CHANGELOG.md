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
- **El diseño del motor en seis workers** (E0 del [plan](docs/00-project/plan-de-los-workers.md)), en propuesta:
  - [ADR-0008](docs/02-design/adr/ADR-0008-seis-workers-sobre-bifrost.md): clasificador, coordinador, enlace,
    respuesta, evaluador y notificador, en una imagen y un contenedor por worker. Se pasan el mensaje por Bifröst en
    un stream propio, `MOTOR`, de 24 h, deduplicado por paso y en orden por conversación. Supera la ADR-0003;
  - [ADR-0009](docs/02-design/adr/ADR-0009-claude-como-llm.md): Claude por la API de Anthropic, con Haiku 5.5 para
    clasificar y Opus 5.5 para responder y evaluar. El clasificador hace en una llamada lo que hacían NeMo y Ollama,
    con salida estructurada y fail-closed. Una clave por worker en Andvari. Supera las ADR-0004, 0005 y 0007;
  - el plan del esqueleto, E0 a E10: primero un mensaje de WhatsApp con respuesta real, después el evaluador, el
    enlace y los demás canales;
  - la clasificación de datos con Anthropic como encargado del tratamiento: qué sale, qué no, dónde y cuánto se
    guarda.
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
- **El motor vive ahora en `engine/` del monorepo `wh-python-fastapi-messenger`**, junto al gateway (ADR-0023 del
  gateway, que supera la ADR-0001 de aquí en lo que decía de un repositorio por servicio). Se importó con toda su
  historia; `ms-python-metamsghandler` queda archivado. Sus ADRs siguen aquí con sus números. El `.github/` propio
  se retira: manda el de la raíz.
- `test/` pasa a `tests/unit/`. `tox.ini`, `pyproject.toml` y el README apuntan a la ruta nueva.
- `pyproject.toml` configura pytest (`pythonpath`, `testpaths`) para que `from src...` resuelva
  también con el ejecutable `pytest`.
- README: mapa de la documentación AI-DLC y estructura actualizada.
- **CI propio dentro del monorepo:** pylint y pruebas con cobertura de ramas mínima del 60 % en cada PR que toca
  `engine/` (workflow `engine`). La imagen `ghcr.io/jeremialcala/chatbot-engine` se publica desde `main`
  (`build-engine`).
- **Dependencias:** las de ejecución en `requirements.txt` y las de desarrollo en `requirements-dev.txt`, cada una
  fijada con hashes en su `.lock`. flake8, tox y pycobertura dejan de instalarse.
- **Dockerfile en dos etapas**, con las bases por digest: las dependencias se compilan desde el lock con hashes y la
  imagen final es `python:3.12-slim`, sin compiladores y solo con el código. Ya no instala rustup.

### Seguridad
- **Siete dependencias con vulnerabilidades conocidas pasan a versiones corregidas**, todas con más de dos semanas:
  - `cryptography` 42.0.8 → 50.0.2, con `cffi` 1.16.0 → 2.0.0;
  - `pillow` 10.3.0 → 12.3.0;
  - `pymongo` 4.7.3 → 4.18.2, con `dnspython` 2.6.1 → 2.8.0;
  - `jwcrypto` 1.5.6 → 1.5.7;
  - `python-dotenv` 1.0.1 → 1.2.2;
  - `pytest` 8.2.2 → 9.0.3.

  pip-audit no encuentra ninguna en los locks nuevos, y los gates del repositorio los auditan en cada PR. Es el SCA
  que pedía T8; siguen pendientes el SBOM y la firma de la imagen.
- Documentadas, sin corregir, las brechas halladas al reconstruir el threat model: datos
  personales en el log del publicador (T3), AMQP sin TLS (T5), pérdida silenciosa de mensajes
  por falta de DLQ y de confirmaciones (T6), llamada del rail sin timeout (T7) y ausencia de
  SCA, SBOM e imagen por digest (T8).

[Unreleased]: https://github.com/jeremialcala/ms-python-metamsghandler/compare/main...develop
