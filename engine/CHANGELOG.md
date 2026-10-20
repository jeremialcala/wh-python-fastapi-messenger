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
- **El notificador, el cuarto worker** (E6 del [plan](docs/00-project/plan-de-los-workers.md)):
  `python -m src.workers.notifier`. Con él el esqueleto está completo de punta a punta, a falta de desplegarlo
  (E7).
  - Lee cada respuesta de `MOTOR`, la envía por la Cloud API de WhatsApp (v26.0, solo texto, sin citar) y publica lo
    enviado en `engine.reply.sent.{botId}`, el `RespuestaEnviada` del contrato v2 del gateway, para el historial.
  - **No envía dos veces la misma respuesta:** lo apunta en el bucket `enviados` de Bifröst y lo mira antes de
    enviar (decisión de Jeremi del 2026-10-20; el bucket, en higerotech/bifrost#2).
  - El token de WhatsApp lo pide al gateway con su clave, lo recuerda 10 minutos y lo vuelve a pedir si Meta lo
    rechaza.
  - Cada error de Meta, por su código: lo que se arregla esperando se reintenta con las entregas de Bifröst; lo que
    no irá nunca (fuera de la ventana de 24 horas, un número que no puede recibir) se descarta.
  - Messenger e Instagram, en el E10.
- **El sobre lleva `cuentaDelBot`**, el `phone_number_id` desde el que se responde, que pone el clasificador. El
  contrato del sobre pasa a la 1.3.0.
- **El de respuesta, el tercer worker** (E5 del [plan](docs/00-project/plan-de-los-workers.md)):
  `python -m src.workers.responder`.
  - Lee cada pedido de `MOTOR` y publica la contestación en `motor.respuesta.…`, y solo entonces confirma.
  - **Con Claude**, Opus 5.5 (esfuerzo `medium`) escribe con la persona del bot y sus reglas en un `system` estable
    por bot y cacheado, y con las vueltas y el mensaje como turnos de la conversación. Lleva los fallbacks del
    servidor (`fallbacks: "default"`): si Opus rechaza, la API lo intenta con otro modelo en la misma llamada.
  - **Si no**, contesta el texto fijo que pidió el coordinador (`no_puedo`, `solo_texto` o `no_disponible`), o el
    de «no puedo» si Claude y sus sustitutos rechazan.
  - Si Claude no contesta, o su respuesta se corta o viene vacía, reintenta con las entregas de Bifröst y, en la
    última, contesta «no disponible».
  - El sobre que publica no lleva la persona ni las vueltas.
  - `max_tokens` es 4096 por el pensamiento de Opus 5.5, que no se puede apagar (ADR-0009, «Construido»).
- **El contrato del sobre pasa a la 1.2.0**, con el canal `respuesta` y su esquema (`Contestacion`).
- **El coordinador, el segundo worker** (E4 del [plan](docs/00-project/plan-de-los-workers.md)):
  `python -m src.workers.coordinator`.
  - Lee lo clasificado de `MOTOR` y publica el pedido en `motor.pedido.…`, y solo entonces confirma.
  - **Si el mensaje sigue**, pide al gateway la persona del bot con sus reglas y las últimas vueltas, con la clave
    del coordinador para el cliente dueño del bot, y pide la respuesta con Claude.
  - **Si no sigue**, pide un texto fijo según el motivo, sin preguntar al gateway: la persona siempre recibe algo.
  - Si el gateway no responde, reintenta con las entregas de Bifröst y, en la última, pide el texto de «no
    disponible». Si el bot o el contacto ya no existen, descarta el mensaje.
  - La API del gateway (`src/infrastructure/gateway/`) se prueba contra un servidor local que abre y verifica cada
    token como el gateway; el worker, contra un NATS con el usuario de Bifröst del coordinador.
- **El contrato del sobre pasa a la 1.1.0**, con el canal `pedido` y sus esquemas (`Persona`, `Vuelta`, `Pedido`).
- **El clasificador, el primer worker** (E3a del [plan](docs/00-project/plan-de-los-workers.md)):
  `python -m src.workers.classifier`.
  - Lee cada mensaje identificado de `MENSAJES` y lo clasifica con Claude Haiku 5.5, en una sola llamada con salida
    estructurada: si se atiende y cuál es su intención. Publica el sobre en `motor.clasificado.…` y solo entonces
    confirma.
  - **Fail-closed:** solo sigue lo que Claude permite sin motivo para pararlo. Un rechazo no sigue. Sin veredicto, el
    mensaje se reintenta con las entregas de Bifröst y, en la última, sale sin seguir con el motivo `error`.
  - A Claude solo le llega el texto. El sobre no lleva el nombre del contacto, y el log no lleva ni el texto ni el
    número.
  - La clave de la API, del worker, la lee de Andvari al arrancar.
  - Lo construido y lo que cambió respecto a las ADR está en
    [ADR-0008](docs/02-design/adr/ADR-0008-seis-workers-sobre-bifrost.md) y
    [ADR-0009](docs/02-design/adr/ADR-0009-claude-como-llm.md): `max_tokens` 1024 por el pensamiento de Haiku 5.5,
    y un puerto en vez de dos.
- **El sobre interno, versión 1**, y su contrato,
  [`asyncapi-motor.yaml`](docs/02-design/contracts/asyncapi-motor.yaml), con pruebas de contrato.
- **El bucle común de los workers** (`src/workers/runtime.py`), probado contra un NATS con los permisos de Bifröst,
  también en el CI.
- Dependencias: `anthropic` 1.11.0, con `httpx2` y `truststore` fijados porque sus versiones más nuevas tienen días;
  `typing_extensions` sube a 4.16.0; y `jsonschema` para las pruebas de contrato.
- **El motor usa `shared/`**, el código que comparte con el gateway (E1 del [plan](docs/00-project/plan-de-los-workers.md)):
  - lo que necesita está en sus `requirements` (`nats-py`, OpenTelemetry, `requests`), con las versiones del gateway,
    y `jwcrypto` sube a 1.6.1, la del gateway;
  - las pruebas lo importan desde la raíz del monorepo;
  - la imagen se construye desde la raíz (`docker build -f engine/Dockerfile .`), con `Dockerfile.dockerignore`.
- ADR-0008 y ADR-0009 aceptadas. Las ADR-0003, 0004, 0005 y 0007 quedan superadas.
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
- El bucle común pasa a cada worker su conexión con Bifröst al arrancar.
- La lectura del sobre de un paso del motor (`leer_del_motor`) pasa al bucle común: la usan el coordinador y el de
  respuesta.
- **La imagen, en una sola etapa** sobre `python:3.12-slim`, con solo ruedas (`--only-binary=:all:`): sin NeMo ni
  `annoy` no hay nada que compilar. Por defecto arranca el clasificador; cada contenedor dice su worker.
- **La cobertura mínima del CI sube del 60 % al 80 %**, la del gateway. `build-engine` levanta también el NATS, así
  que las pruebas de integración corren en `main` en vez de saltarse.
- El README describe el motor en workers.
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

### Eliminado
- **El servicio de antes** (E3b del [plan](docs/00-project/plan-de-los-workers.md); ADR-0009, «Construido»):
  - NeMo Guardrails y Ollama, con sus adaptadores, sus prompts y los rails, y con ellos `annoy` y su compilación de
    C++. El motor ya se puede desarrollar fuera de Linux;
  - el consumidor y el publicador AMQP (`pika`), el caso de uso que los unía y `main.py`;
  - los parsers de webhooks de Meta: el clasificador lee el texto con `shared.contract.what_was_said`;
  - el código muerto de MongoDB y JWE (`mongoengine`, `pymongo`, `dnspython`, `pillow`);
  - `config.env.example`, `logging_config.yaml`, `deployment.yaml` (un borrador de otro servicio) y el contrato AMQP
    `asyncapi.yaml` con su generador. El contrato de ahora es `asyncapi-motor.yaml`.

  `jwcrypto` y `cryptography` se quedan: los usa `shared.auth`. `PyYAML` pasa a las dependencias de desarrollo.

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
