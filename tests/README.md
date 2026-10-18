# Tests — pirámide AI-DLC

`unit/` · `integration/` · `contract/` · `e2e/` · `security/`

- **unit/**: lo que existe hoy. Autenticación de los endpoints de gestión, firma y verificación del webhook,
  publicación confirmada en RabbitMQ y el esquema de herramientas de los intents. Todo contra dobles.
- **integration/**: el cliente del servicio de claves contra un OpenBao real y la publicación contra un RabbitMQ
  real. Sin `OPENBAO_TEST_ADDR` y `OPENBAO_TEST_TOKEN`, o sin `RABBITMQ_TEST_ADDR`, se saltan; el pipeline los
  exige con `OPENBAO_TEST_REQUIRED` y `RABBITMQ_TEST_REQUIRED`. Cada fichero explica cómo levantar el suyo.
- **contract/**: el OpenAPI versionado coincide con la aplicación, y el mensaje que el código publica en la cola
  `llm` cumple el AsyncAPI. Regenerar el OpenAPI con `python .ai-dlc/scripts/gen_openapi.py`.
- **e2e/**: de la notificación de Meta al mensaje en la cola. Vacía.
- **security/**: las amenazas priorizadas del threat model. Vacía; las pruebas previstas están en su sección
  "Verificación prevista".

`conftest.py` fija toda la configuración por variables de entorno antes de importar la aplicación, así que las
pruebas nunca leen `config.env` ni alcanzan un servicio real, salvo las de `integration/` cuando se les indica uno. `pytest.ini` añade `src/` al path: ejecuta `pytest`
desde la raíz.
