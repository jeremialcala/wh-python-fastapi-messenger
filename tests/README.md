# Tests — pirámide AI-DLC

`unit/` · `integration/` · `contract/` · `e2e/` · `security/`

- **unit/**: lo que existe hoy. Autenticación de los endpoints de gestión, firma y verificación del webhook,
  publicación confirmada en RabbitMQ y el esquema de herramientas de los intents. Todo contra dobles.
- **integration/**: contra MongoDB y RabbitMQ reales. Vacía.
- **contract/**: OpenAPI de la API y AsyncAPI del mensaje de la cola `llm`. Vacía.
- **e2e/**: de la notificación de Meta al mensaje en la cola. Vacía.
- **security/**: las amenazas priorizadas del threat model. Vacía hasta que exista el threat model.

`conftest.py` fija toda la configuración por variables de entorno antes de importar la aplicación, así que las
pruebas nunca leen `config.env` ni alcanzan un servicio real. `pytest.ini` añade `src/` al path: ejecuta `pytest`
desde la raíz.
