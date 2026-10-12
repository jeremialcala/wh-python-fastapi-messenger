# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y este proyecto se adhiere a [Versionado Semántico](https://semver.org/lang/es/).

## [Unreleased]

### Añadido
- ADR-0013, aceptado: OpenBao como gestor de secretos y controlador central de claves, desplegado en el servidor
  con el nombre de Andvari. La clave maestra de ADR-0010 vive en su motor Transit, derivada por cliente.
- Workflow `Seguridad`, con tres gates que rompen el build: fuga de secretos (gitleaks sobre la historia
  completa), dependencias vulnerables (`pip-audit` sobre el lock) y análisis estático (CodeQL sobre todo el código,
  con umbral en los hallazgos de seguridad altos y críticos).
- `requirements.lock` y `requirements-dev.lock`: dependencias fijadas con hashes. La imagen y el CI instalan
  desde ellos.
- Suelo de cobertura por ramas en el CI: 60 %.

### Cambiado
- La imagen instala solo las dependencias de ejecución; las de pruebas pasan a `requirements-dev.txt`.
- Se retiran once dependencias que el código no importaba: `fastapi-sessions`, `asgi-correlation-id`,
  `python-multipart`, `pytz`, `pyjwt`, `pycryptodome`, `keyboard`, `segno`, `pillow`, `phonenumbers` y
  `pydantic-extra-types`.

### Corregido
- Los valores por defecto de las entidades se calculaban una sola vez, al importar. Todos los documentos
  guardaban como fecha de creación la hora de arranque del proceso, todos los mensajes de la cola compartían
  `_uuid`, y todas las credenciales compartían la clave con la que se firma el token de verificación.
- La marca de tiempo de las respuestas de la API era también la hora de arranque.
- Las respuestas de los endpoints de gestión llegaban rotas al cliente desde la actualización de Starlette: los
  controladores enviaban el cuerpo como texto, y la versión nueva ya no lo convierte. Ahora lo envían en bytes, y
  `Content-Length` cuenta bytes y no caracteres, que no coincidían en cuanto había una tilde.

### Seguridad
- FastAPI pasa de 0.110.0 a 0.143.0 y Starlette de 0.36.3 a 1.7.0. La versión anterior de Starlette tenía 14
  vulnerabilidades conocidas; con las dependencias nuevas, `pip-audit` no encuentra ninguna.
- Los valores de ejemplo de los modelos del webhook llevaban números de teléfono reales, uno de ellos también
  codificado dentro de un identificador de mensaje de WhatsApp. Se sustituyen por números del rango reservado
  para ficción. Siguen en la historia de git y en las imágenes ya publicadas.

## [0.2.0] - 2026-10-12

Cierre del Gate 1 (diseño).

### Añadido
- Documentos del Gate 1, aprobados: arquitectura (C4, flujos, ciclo de vida del mensaje, modelo de datos) y
  threat model (21 amenazas con STRIDE y DREAD, y seis hallazgos del diseño).
- Contratos: OpenAPI generado de la aplicación y AsyncAPI de la cola `llm`, con pruebas de contrato que los
  verifican contra el código (`tests/contract`).
- ADR-0006 a ADR-0008, que registran decisiones ya construidas o tomadas: publicación confirmada, App Secret por
  bot y despliegue en el servidor propio.
- ADR-0009 a ADR-0012, aceptados: parámetros del token, clave de cifrado de datos por cliente, contrato de la
  cola y aislamiento por cliente en la capa de datos.

## [0.1.0] - 2026-10-12

Cierre del Gate 0 (requisitos). Primera versión con la estructura AI-DLC.

### Añadido
- Documentos del Gate 0, aprobados: charter, glosario, clasificación de datos (GDPR, con el cliente como
  responsable y la plataforma como encargada) y el PRD BAAS-001 del gateway como servicio BaaS, con el estado
  construido, parcial o pendiente de cada requisito.
- El Gate 0 identifica el motor de respuestas, `ms-python-metamsghandler`, y registra lo que falta entre los dos
  servicios: el motor rechaza los mensajes de Messenger que publica el gateway, descarta el bot de destino y
  nadie entrega todavía la respuesta al usuario (RF07, RF12).
- ADR-0002: el motor de respuestas, y no el gateway, envía la respuesta al usuario final.
- ADR-0003: el `bot_id` identifica cada mensaje y es la llave con la que el motor pide al gateway la configuración
  del bot; el identificador no autoriza por sí solo (RS18).
- ADR-0004: el webhook es lo único que se autentica solo con la firma de Meta; el resto de endpoints, con JWE y
  material de clave propio de cada cliente registrado. La clave `ADMIN_API_KEY` queda como mecanismo provisional.
- ADR-0005: el token de autenticación es un JWT firmado por el cliente y metido dentro de un JWE cifrado para el
  gateway, que solo registra la clave pública de cada cliente.
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

[Unreleased]: https://github.com/jeremialcala/wh-python-fastapi-messenger/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/jeremialcala/wh-python-fastapi-messenger/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jeremialcala/wh-python-fastapi-messenger/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/jeremialcala/wh-python-fastapi-messenger/releases/tag/v0.0.1
