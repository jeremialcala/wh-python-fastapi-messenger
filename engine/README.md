# ms-python-template

Plantilla (template) de microservicio en Python orientado a **mensajería asíncrona**. El servicio se conecta a un broker **RabbitMQ (AMQP)**, consume mensajes de una cola, procesa operaciones sobre el ciclo de vida de un recurso (CRUD) y publica el resultado. Está pensado como base reutilizable para construir microservicios manejados por eventos.

Su diferencial es que **los modelos de datos (ORM y DTO) se generan dinámicamente a partir de JSON Schemas** definidos en variables de entorno, evitando tener que escribir clases para cada recurso.

---

## Características principales

- **Consumo de mensajes AMQP** con [`pika`](https://pika.readthedocs.io/) sobre RabbitMQ, con procesamiento concurrente mediante *threads* y ACK seguro por hilo.
- **Generación dinámica de modelos**:
  - Modelos ORM de **MongoDB** con [`mongoengine`](http://mongoengine.org/) a partir de un JSON Schema.
  - Modelos **DTO** con [`pydantic`](https://docs.pydantic.dev/) a partir de un JSON Schema.
- **Cifrado/descifrado JWE** (RSA-OAEP-256 + A256CBC-HS512) con [`jwcrypto`](https://jwcrypto.readthedocs.io/), incluyendo recuperación de llaves (JWK) almacenadas en base de datos.
- **Configuración por entorno** con `pydantic-settings` (archivo `config.env`).
- **Logging** configurable por ambiente (`development`, `staging`, `production`) vía YAML.
- **Enrutamiento de operaciones** CRUD (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`) mediante `match/case`.
- **Pruebas** con `pytest` + cobertura, *linting* con `pylint`/`flake8` y orquestación con `tox`.
- **Contenerización** con Docker y manifiesto de despliegue para **Kubernetes**.

---

## Arquitectura y flujo

```
RabbitMQ (cola)
      │
      ▼
process_messages()  ──►  on_message()  ──►  Thread ──►  execute_operation()
  (messages.py)            (amqp.py)                      (amqp.py)
                                                              │
                                                  @service_lifecycle
                                                   (service.py)
                                                              │
                            ┌─────────────────────────────────┤
                            ▼                                  ▼
                  DTO dinámico (pydantic)           match operation:
                  a partir de DTO_MESSAGE            GET/POST/PUT/PATCH/DELETE
                                                              │
                                                              ▼
                                                        ack_message()
```

1. `main.py` arranca el servicio e invoca `process_messages()`.
2. `process_messages()` abre la conexión, declara/enlaza la cola al *exchange* y comienza a consumir.
3. Cada mensaje dispara `on_message()`, que lanza un *thread* y ejecuta `execute_operation()`.
4. El decorador `@service_lifecycle` deserializa el mensaje a un DTO dinámico y enruta según la operación.
5. Al terminar, se confirma el mensaje con `ack_message()` (ACK *threadsafe*).

---

## Estructura del repositorio

```
ms-python-template/
├── main.py                    # Punto de entrada del servicio
├── requirements.txt           # Dependencias de Python
├── Dockerfile                 # Imagen del contenedor
├── deployment.yaml            # Manifiesto de despliegue para Kubernetes
├── logging_config.yaml        # Configuración de logging por ambiente
├── tox.ini                    # Entornos de test/lint/coverage + reglas pylint
├── .gitignore
│
├── classes/                   # Catálogo de clases (Tools / DTOs / Entities)
│   ├── __init__.py
│   └── tool_settings.py       # Settings (pydantic-settings) ← config.env
│
├── constants/                 # Constantes del proyecto
│   ├── __init__.py
│   ├── general.py             # Mensajes de log, claves generales
│   ├── fieldtypes.py          # Nombres de tipos de campo (mongoengine)
│   └── operations.py          # Operaciones CRUD (GET/POST/PUT/PATCH/DELETE)
│
├── controllers/               # Lógica de negocio / interfaces externas
│   ├── __init__.py
│   ├── amqp.py                # Interfaz RabbitMQ (conexión, consumo, ACK, envío)
│   ├── messages.py            # Apertura de cola y arranque del consumo
│   ├── service.py             # Decorador del ciclo de vida del servicio
│   └── security.py            # Operaciones JWE (cifrar/descifrar) y JWK
│
├── enums/                     # Enumeraciones
│   ├── __init__.py
│   ├── status.py              # Estados de un recurso (REG/ACT/LOK/…)
│   ├── response_codes.py      # Códigos de respuesta (AOK/CRD/UPD/…)
│   └── key_types.py           # Tipos de llave soportados (RSA)
│
├── utils/                     # Utilidades
│   ├── __init__.py
│   ├── general.py             # documenting_parameter (decorador de docstring)
│   ├── logging.py             # configure_logging (carga logging_config.yaml)
│   └── model.py               # Generación dinámica de modelos ORM/DTO
│
└── test/                      # Pruebas unitarias (pytest)
    ├── __init__.py
    ├── test_amqp.py
    ├── test_messages.py
    ├── test_response_codes.py
    └── test_status.py
```

---

## Descripción detallada por módulo

### `main.py`
Punto de entrada. Carga `Settings`, configura el logging, soporta `--help` (genera la ayuda desde el docstring con `documenting_parameter`) e inicia el consumo de mensajes con `process_messages(queue=...)`.

### `classes/`
Catálogo central de clases con una convención de nombres:
- `entity_*` → clases para **almacenar** datos.
- `dto_*` → clases para **transportar** datos.
- `tool_*` → clases de **utilidades/herramientas**.

[`tool_settings.py`](classes/tool_settings.py) define `Settings` (basado en `BaseSettings`), donde cada atributo corresponde a una variable del archivo `config.env` (credenciales de BD, parámetros de RabbitMQ, nombres de llaves, esquemas JSON, etc.).

### `controllers/`
- [`amqp.py`](controllers/amqp.py): interfaz con RabbitMQ. Construye parámetros de conexión, callback `on_message` (lanza *threads*), `execute_operation` (trabajo + ACK), `ack_message` (ACK *threadsafe*) y `send_message_to_queue` (publicación).
- [`messages.py`](controllers/messages.py): `process_messages` declara la cola, la enlaza al *exchange* con la *routing key*, fija `prefetch_count=1` y arranca el consumo.
- [`service.py`](controllers/service.py): decorador `@service_lifecycle` que deserializa el cuerpo a un DTO dinámico y enruta la operación CRUD mediante `match/case`.
- [`security.py`](controllers/security.py): operaciones JWE. `retrieve_key` reconstruye una `JWK` desde la BD (Mongo), `encrypt_data` cifra (RSA-OAEP-256 / A256CBC-HS512) y `decrypt_data` descifra.

### `utils/model.py`
Corazón de la generación dinámica:
- `generate_properties(json_schema)` → traduce un JSON Schema a campos de `mongoengine`, añadiendo `createdAt`, `status` y `statusDate`.
- `create_dynamic_orm_model(name, properties)` → crea un `Document` de Mongo en tiempo de ejecución.
- `create_dynamic_dto_model(name, properties)` → crea un modelo `pydantic` desde un JSON Schema.
- `resource_from_model` / `validate_criteria` → consulta y filtra recursos por criterios.

### `enums/`
- `Status`: `REG`, `ACT`, `LOK`, `DIS`, `OVR`, `ERR`, `COM`.
- `ResponseCodes`: `AOK=200`, `CRD=201`, `UPD=202`, `NOK=400`, `FOR=403`, `NOF=404`, `ERR=500`.
- `KeyTypes`: `RSA`.

### `constants/`
Mensajes de log (`STARTING_AT`, `ENDING_AT`, `OPERATION_DATA`), nombres de tipos de campo de mongoengine y las operaciones CRUD como constantes.

---

## Configuración

La configuración se carga desde un archivo `config.env` (ignorado por git). Usa la plantilla [`config.env.example`](config.env.example) como punto de partida:

```bash
cp config.env.example config.env   # En Windows: copy config.env.example config.env
```

Variables esperadas por [`Settings`](classes/tool_settings.py):

| Variable | Descripción |
|---|---|
| `national_id_url` | URL de servicio de identidad |
| `service_name` | Nombre del servicio |
| `db_name`, `db_host`, `db_username`, `db_password` | Conexión a MongoDB |
| `qms_server`, `qms_port` | Host/puerto de RabbitMQ |
| `qms_user`, `qms_password` | Credenciales de RabbitMQ |
| `queue_name` | Nombre de la cola a consumir |
| `amqp_exchange`, `amqp_routing_key` | Exchange y routing key AMQP |
| `key_size`, `private_key_filename`, `public_key_filename` | Parámetros de llaves criptográficas |
| `environment` | Ambiente (`development`/`staging`/`production`) |
| `version` | Versión del servicio |
| `entity_schema`, `entity_jwk` | JSON Schemas de entidad y de JWK |
| `dto_schema`, `dto_message` | JSON Schemas de DTO y del mensaje |

Ejemplo de `config.env`:

```env
service_name=my-service
db_name=mydb
db_host=mongodb://localhost:27017
db_username=user
db_password=secret

qms_server=localhost
qms_port=5672
qms_user=guest
qms_password=guest

queue_name=users
amqp_exchange=my_exchange
amqp_routing_key=users.#

key_size=2048
private_key_filename=certs/private.pem
public_key_filename=certs/public.pem

environment=development
version=1.0.0

entity_schema={...}
entity_jwk={...}
dto_schema={...}
dto_message={...}
```

> El logging se configura en [`logging_config.yaml`](logging_config.yaml), con *loggers* separados para `development` (consola, DEBUG), `staging` (consola + archivo, INFO) y `production` (archivo, WARNING).

---

## Instalación y ejecución (local)

Requisitos: **Python 3.12**, una instancia de **RabbitMQ** y una de **MongoDB** accesibles.

> ### ⚠️ Versión de Python: usa **3.12**
>
> El proyecto está fijado a **Python 3.12** (ver el entorno `py312` en [`tox.ini`](tox.ini)). Esto **no es arbitrario**: las dependencias en [`requirements.txt`](requirements.txt) están *pinneadas* a versiones que solo publican *wheels* precompilados para 3.12 (y anteriores). En particular:
>
> - `pillow==10.3.0` — no tiene *wheel* para Python 3.13/3.14, por lo que `pip` intentaría compilarlo desde fuente y falla.
> - `cryptography==42.0.8` y `pydantic_core==2.18.4` — sus *wheels* tampoco cubren las versiones más nuevas de Python.
>
> En Python 3.14 la instalación falla al construir `pillow` (`KeyError: '__version__'`). Verificado: con **Python 3.12.10** la instalación limpia funciona y todos los imports del proyecto se resuelven correctamente.
>
> Para soportar Python 3.13+ habría que **subir** las versiones de `pillow`, `cryptography` y `pydantic`/`pydantic_core` a releases con *wheels* para esa versión.

```bash
# 1. Crear y activar entorno virtual
python -m venv venv
source venv/bin/activate          # En Windows: venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Crear el archivo config.env a partir de la plantilla (ver sección Configuración)
cp config.env.example config.env

# 4. Ejecutar el servicio
python main.py

# Ver la ayuda
python main.py --help
```

---

## Pruebas y calidad

El proyecto usa **tox** con varios entornos definidos en [`tox.ini`](tox.ini):

```bash
# Ejecutar todo (pylint, py312, coverage, pycobertura)
tox

# Solo pruebas unitarias con cobertura
pytest --cov=. test/ -p no:warnings

# Solo linting
tox -e pylint
```

- `pylint` / `py312` (pytest + coverage) / `coverage` (umbral mínimo **60%**) / `pycobertura`.
- Pruebas incluidas: AMQP ([`test_amqp.py`](test/test_amqp.py)), mensajes ([`test_messages.py`](test/test_messages.py)), códigos de respuesta y estados.

---

## Docker

```bash
# Construir la imagen
docker build -t ms-python-template .

# Ejecutar (montando config.env)
docker run --rm --env-file config.env ms-python-template
```

El [`Dockerfile`](Dockerfile) parte de `python:latest`, instala dependencias de compilación (incluido Rust, requerido por `cryptography`), instala los requirements y ejecuta `python main.py`.

---

## Despliegue en Kubernetes

[`deployment.yaml`](deployment.yaml) define un `Deployment` (1 réplica) en el namespace `chatters-pro`, usando la imagen `rgx01.chatters.pro/ms-python-pooling:latest` y el secreto de registro `regcred`.

```bash
kubectl apply -f deployment.yaml
```

---

## Stack tecnológico

| Categoría | Tecnologías |
|---|---|
| Lenguaje | Python 3.12 |
| Mensajería | RabbitMQ / AMQP (`pika`) |
| Base de datos | MongoDB (`mongoengine`, `pymongo`) |
| Validación / Settings | `pydantic`, `pydantic-settings` |
| Criptografía | `jwcrypto`, `cryptography`, `pycryptodome`, `PyJWT` |
| Web (disponible) | `fastapi`, `uvicorn`, `starlette` |
| SQL (disponible) | `SQLAlchemy`, `PyMySQL` |
| Testing / Calidad | `pytest`, `pytest-cov`, `coverage`, `pylint`, `flake8`, `tox` |
| Contenerización | Docker, Kubernetes |

> Nota: `requirements.txt` incluye librerías adicionales (FastAPI, SQLAlchemy, Faker, etc.) que sirven como base para extender la plantilla según las necesidades de cada microservicio.

---

## Autor

**Jeremi Alcalá** — [github.com/jeremialcala](https://github.com/jeremialcala)
