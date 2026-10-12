# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y este proyecto se adhiere a [Versionado Semántico](https://semver.org/lang/es/).

## [Unreleased]

### Añadido
- Estructura AI-DLC: `.ai-dlc/` con los checklists de los gates 0–5, las plantillas y el mapeo OWASP; `docs/` por
  fase; `SECURITY.md`, `CONTRIBUTING.md`, `CODEOWNERS` y este changelog (ADR-0001).
- Guardia de GitFlow: los pull requests hacia `main` solo pueden venir de `develop`, `release/*` o `hotfix/*`.
- Imagen de contenedor sobre `python:3.12-slim` fijada por digest, con usuario sin privilegios y `HEALTHCHECK`.
- Workflows `ci` (pruebas y build en cada pull request) y `build` (imagen `sha-<7>` en GHCR al llegar a `main`).
- `deploy/docker-compose.yml` para el servidor y `GET /health` como sonda de vida.
- Suite de pruebas que corre sin MongoDB, RabbitMQ ni `config.env`.
- `config.env.example` como plantilla de configuración.
- Gestión de intents por chatbot (`/chat/{bot_id}/intents`) y su esquema de herramientas (`/chat/{bot_id}/tools`).

### Cambiado
- El código pasa a `src/` y las pruebas a `tests/unit/`; `pytest` se ejecuta desde la raíz sin argumentos.
- El README pasa a español, documenta los endpoints de intents y `/health`, y deja de afirmar que el mensaje se
  cifra como JWE y que cada petición se registra como evento: ambas cosas están implementadas pero desactivadas.
- La configuración de logging se localiza junto al código, no en el directorio de trabajo.
- El webhook espera a que RabbitMQ confirme el mensaje antes de responder `200`, y responde `503` si el broker no
  está disponible. El consumidor de la cola `llm` debe tolerar duplicados.
- La verificación del webhook devuelve el challenge como texto plano y un `403` real ante un token equivocado.
- Los logs de producción van a la consola en vez de a `application.log`.

### Seguridad
- Los endpoints de gestión exigen la cabecera `X-API-Key` (`ADMIN_API_KEY`, 32 caracteres como mínimo).
- `POST /chat/{bot_id}` verifica `X-Hub-Signature-256` sobre el cuerpo crudo, con `appSecret` por chatbot o
  `FACEBOOK_APP_SECRET`.
- Los logs dejan de incluir query strings, cabeceras y la clave que firma el `verifyToken`.
- `.dockerignore` impide que `config.env` y `certs/` entren en la imagen.

## [0.0.1] - 2024-04-26

Primera versión etiquetada. Los cambios entre esta versión y la adopción de este changelog (2026-10-12) no se
registraron aquí; están en el historial de git.

[Unreleased]: https://github.com/jeremialcala/wh-python-fastapi-messenger/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/jeremialcala/wh-python-fastapi-messenger/releases/tag/v0.0.1
