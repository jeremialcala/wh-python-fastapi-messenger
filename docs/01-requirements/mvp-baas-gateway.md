# PRD — MVP del gateway BaaS de mensajería

* **Estado:** review
* **Fecha:** 2026-10-12
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 01-requirements
* **Versión:** 0.1.0
* **Gate:** 0
* **Feature ID:** BAAS-001
* **Nivel ASVS objetivo:** L2 (propuesto; ver [Decisiones abiertas](#decisiones-abiertas))

## Problema y contexto

Una empresa que quiere atender por WhatsApp o Messenger con un bot tiene que montar un webhook público, validar a
Meta, guardar credenciales, identificar a quien escribe y conectar todo eso con un modelo de lenguaje. El gateway
ofrece esa parte como servicio (BaaS, Bot as a Service): el cliente crea su bot, lo conecta a su cuenta de Meta y
administra sus datos; la plataforma opera el webhook y entrega cada mensaje a un motor de respuestas.

El servicio existe desde 2024 como un gateway de un solo operador. Este documento es **retroactivo**: recoge lo que
ya está construido y lo que el modelo BaaS y el GDPR exigen y todavía falta. Cada requisito lleva su estado:

- **Construido** — implementado y cubierto por pruebas.
- **Parcial** — existe, pero no cumple el requisito completo.
- **Pendiente** — no existe.

"Construido" no significa probado en producción: hoy todas las pruebas son unitarias y contra dobles.

## Objetivos / No-objetivos

Objetivos:

1. Un cliente administra sus bots y los datos de sus bots, y nadie más puede hacerlo.
2. Los números de teléfono se guardan cifrados con una clave propia de cada cliente.
3. Ningún mensaje aceptado se pierde, y ninguna notificación falsa se procesa.
4. El tratamiento de datos personales se puede defender frente al GDPR: minimización, retención, y derechos de
   acceso, supresión y portabilidad.
5. El servicio se despliega de forma reproducible, con rollback.

No-objetivos: los del no-scope del [charter](../00-project/charter.md). En particular, generar las respuestas no
es parte del gateway.

## Contexto del sistema (C4 Context)

```mermaid
C4Context
    title Contexto - Gateway BaaS de mensajeria

    Person(cliente, "Cliente", "Empresa duena de sus bots. Responsable del tratamiento")
    Person(operador, "Operador", "Opera la plataforma. Encargado del tratamiento")
    Person_Ext(usuario, "Usuario final", "Escribe al bot por WhatsApp o Messenger. Interesado")
    Person_Ext(atacante, "Atacante en internet", "Envia notificaciones falsas y prueba credenciales")

    Enterprise_Boundary(plataforma, "Plataforma (trust boundary: red privada del servidor)") {
        System(gateway, "Gateway BaaS", "Verifica a Meta, identifica contactos y encola mensajes")
        SystemQueue(hermod, "Hermod", "RabbitMQ: cola llm")
    }

    System_Ext(meta, "Meta", "WhatsApp Business y Messenger: Graph API y webhooks")
    System_Ext(motor, "Motor de respuestas", "Consume la cola y genera la respuesta. Sin definir")
    SystemDb_Ext(atlas, "MongoDB Atlas", "Bots, contactos, reglas e intents")
    System_Ext(cf, "Cloudflare", "Tunel y TLS del hostname publico")
    System_Ext(cd, "GitHub y receptor", "Build de la imagen y despliegue continuo")

    Rel(usuario, meta, "Escribe al bot", "WhatsApp / Messenger")
    Rel(meta, cf, "Entrega notificaciones firmadas", "HTTPS")
    Rel(atacante, cf, "Ataca el webhook", "HTTPS")
    Rel(cf, gateway, "Entrega solo /chat/uuid", "Tunel saliente")
    Rel(cliente, gateway, "Administra sus bots", "API con credencial propia")
    Rel(operador, gateway, "Opera y despliega", "Red privada")
    Rel(gateway, atlas, "Lee y escribe", "TLS")
    Rel(gateway, meta, "Consulta perfiles y envia mensajes", "HTTPS, token del cliente")
    Rel(gateway, hermod, "Publica cada mensaje", "AMQP con confirmacion")
    Rel(motor, hermod, "Consume", "AMQP")
    Rel(motor, gateway, "Lee reglas y herramientas del bot", "API")
    Rel(cd, gateway, "Despliega", "Webhook firmado")

    UpdateElementStyle(gateway, $bgColor="#1168bd", $fontColor="#ffffff")
    UpdateElementStyle(motor, $borderColor="#b30000", $fontColor="#b30000")
    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```
*Eje estructura · fase 01 · Gate 0. En rojo, lo que está sin definir. La relación del cliente con el gateway es el
objetivo: hoy la gestión solo es alcanzable desde la red privada y con la clave única del operador.*

## Usuarios y escenarios

### Journey del usuario

```mermaid
journey
    title Un cliente conecta su bot de WhatsApp
    section Alta
      Recibe su credencial de cliente: 2: Cliente, Operador
      Crea el bot con su persona: 4: Cliente
      Anade reglas e intents: 4: Cliente
    section Conexion con Meta
      Registra su numero de WhatsApp: 3: Cliente
      Carga el token y el app secret: 1: Cliente, Operador
      Meta verifica el webhook: 5: Cliente
    section Operacion
      Un usuario escribe al bot: 5: Usuario final
      El mensaje llega a la cola: 5: Gateway
      El usuario recibe respuesta: 1: Usuario final
    section Datos
      Pide borrar los datos de un contacto: 1: Cliente
```
*Eje trazabilidad · fase 01 · Gate 0. Las puntuaciones bajas son los huecos de hoy: no hay credencial por cliente,
los tokens se cargan a mano en la base, no hay motor que responda y no existe el borrado de un contacto.*

### Escenarios positivos

| ID | Escenario |
|---|---|
| ES01 | Un cliente crea un bot, le añade reglas e intents y obtiene la URL del webhook y su token de verificación. |
| ES02 | El cliente pega esa URL y ese token en su app de Meta, y Meta verifica el webhook a la primera. |
| ES03 | Un usuario final escribe por WhatsApp; el gateway valida la firma, identifica o crea el contacto, publica el mensaje y responde `200` a Meta. |
| ES04 | El motor de respuestas pide las reglas y las herramientas del bot y las usa para responder. |
| ES05 | El cliente exporta o borra los datos de un contacto que ha ejercido sus derechos. |
| ES06 | RabbitMQ no está disponible; el gateway responde `503`, Meta reintenta y el mensaje llega cuando vuelve. |

### Escenarios negativos / abuso (requerido por Gate 0)

| ID | Escenario | Control | Estado |
|---|---|---|---|
| AB01 | Un tercero envía al webhook una notificación sin firma, o firmada con otro secreto, para inyectar mensajes en la cola | RS03 | Construido |
| AB02 | El cliente A lee o modifica los bots, contactos o tokens del cliente B usando un UUID que conoce o adivina | RS01 | Pendiente |
| AB03 | Una copia de la base (volcado, respaldo, acceso indebido a Atlas) expone números de teléfono y tokens de Meta | RS05, RS06 | Pendiente |
| AB04 | Un tercero recorre el hostname público y encuentra `/docs`, `/openapi.json` o los endpoints de gestión | RS09 | Pendiente |
| AB05 | Un bot en internet prueba claves de gestión o tokens de verificación | RS02, RS04, RS10 | Parcial |
| AB06 | Alguien reenvía una notificación legítima capturada: la firma de Meta no caduca | RNF04 | Pendiente |
| AB07 | Una ráfaga de notificaciones agota el worker o llena la cola | RS10, RNF03 | Pendiente |
| AB08 | Un usuario final escribe instrucciones para que el LLM invoque herramientas del cliente en su contra (prompt injection) | RS16 | Pendiente |
| AB09 | Un cliente define un intent cuya llamada a API apunta a la red interna de la plataforma (SSRF a través del ejecutor de herramientas) | RS16 | Pendiente |
| AB10 | Quien tiene acceso a los logs lee conversaciones, nombres y números | RS07 | Parcial |
| AB11 | El broker cae y el gateway responde `200` a un mensaje que nunca se encoló | RNF02 | Construido |
| AB12 | Un cuerpo malformado o enorme provoca un error que revela detalles internos | RS11, RS15 | Parcial |
| AB13 | Una dependencia vulnerable o una imagen manipulada llegan a producción | RS12 | Parcial |
| AB14 | Un interesado pide la supresión y sus datos siguen en la cola, los logs o los respaldos | RF09, RNF05 | Pendiente |

## Requisitos funcionales

| ID | Requisito | Estado | Verificación |
|---|---|---|---|
| RF01 | El operador da de alta a un cliente y le entrega una credencial propia | Pendiente | — |
| RF02 | Un cliente crea y administra sus bots: persona, reglas, intents y números | Parcial: existe para bots sin dueño, con la clave única | Pruebas unitarias de autenticación |
| RF03 | Meta verifica el webhook de cada bot con su token de verificación | Construido | `tests/unit/test_webhook_security.py` |
| RF04 | El gateway recibe notificaciones de Messenger y de WhatsApp, identifica o crea el contacto y publica el mensaje en la cola `llm` | Construido | Pruebas unitarias del camino de WhatsApp; Messenger sin prueba; falta integración con MongoDB y RabbitMQ reales |
| RF05 | El motor de respuestas obtiene de un bot su system prompt y sus herramientas | Construido | `tests/unit/test_intent_tool_schema.py` para las herramientas; el system prompt no tiene prueba |
| RF06 | El cliente carga y rota las credenciales de Meta de su bot (tokens y App Secret) por API | Pendiente: hoy se escriben a mano en la base | — |
| RF07 | La respuesta generada llega al usuario final por el canal en el que escribió | Pendiente: `/answers` no existe y el envío por WhatsApp está sin conectar | — |
| RF08 | El cliente consulta los contactos de sus bots | Pendiente | — |
| RF09 | El cliente exporta y borra los datos de un contacto (GDPR, arts. 15, 17 y 20) | Pendiente | — |
| RF10 | La baja de un bot o de un cliente borra todos sus datos (GDPR, art. 28.3.g) | Pendiente | — |
| RF11 | Fusionar a `main` construye la imagen y la despliega, con rollback si la sonda de vida falla | Parcial: construido, sin ejercitar en el servidor | Prueba de despliegue con la sonda rota a propósito |

## Requisitos no funcionales

| ID | Requisito | Estado |
|---|---|---|
| RNF01 | El webhook responde a Meta dentro del plazo que evita reintentos: `<TODO: fijar SLO>` | Sin medir |
| RNF02 | Una notificación recibe `200` solo cuando RabbitMQ ha confirmado el mensaje; si no, `503` | Construido |
| RNF03 | El gateway no pasa de 512 MB de RAM ni de 1 CPU en el servidor | Construido (tope del compose) |
| RNF04 | Un mensaje entregado dos veces por Meta, o reenviado por un tercero, no se procesa dos veces | Pendiente; depende del motor de respuestas |
| RNF05 | Cada dato personal tiene un plazo de retención y se borra al vencer, también en cola, logs y respaldos | Pendiente; plazos sin definir |
| RNF06 | El servicio arranca solo tras un apagón del servidor | Pendiente: no hay unidad de arranque para el gateway |
| RNF07 | Disponibilidad mensual del webhook: `<TODO: fijar SLO>` | Sin medir |

## Trazabilidad de requisitos

```mermaid
requirementDiagram
    requirement RS01 {
      id: RS01
      text: Aislamiento entre clientes
      risk: high
      verifymethod: test
    }
    requirement RS03 {
      id: RS03
      text: Notificaciones autenticadas por firma
      risk: high
      verifymethod: test
    }
    requirement RS05 {
      id: RS05
      text: Numeros cifrados con la clave del cliente
      risk: high
      verifymethod: test
    }
    requirement RS06 {
      id: RS06
      text: Tokens de Meta cifrados y no devueltos
      risk: high
      verifymethod: test
    }
    requirement RNF02 {
      id: RNF02
      text: Sin perdida silenciosa de mensajes
      risk: high
      verifymethod: test
    }
    requirement RF09 {
      id: RF09
      text: Exportar y borrar datos de un contacto
      risk: medium
      verifymethod: test
    }
    element FirmaWebhook {
      type: "dependencia get_signed_webhook_bot"
    }
    element PublicacionConfirmada {
      type: "modulo amqp_broker"
    }
    element PruebasSeguridadWebhook {
      type: "prueba unitaria"
    }
    element AutorizacionPorCliente {
      type: "sin construir"
    }
    element CifradoPorCliente {
      type: "sin construir"
    }
    element DerechosDelInteresado {
      type: "sin construir"
    }
    FirmaWebhook - satisfies -> RS03
    PublicacionConfirmada - satisfies -> RNF02
    PruebasSeguridadWebhook - verifies -> RS03
    PruebasSeguridadWebhook - verifies -> RNF02
    AutorizacionPorCliente - satisfies -> RS01
    CifradoPorCliente - satisfies -> RS05
    CifradoPorCliente - satisfies -> RS06
    DerechosDelInteresado - satisfies -> RF09
```
*Eje trazabilidad · fase 01 · Gate 0. Solo los requisitos de riesgo alto y RF09. Los tres elementos "sin construir"
no tienen todavía ni componente ni prueba que los verifique.*

## Requisitos de seguridad (mapeados a OWASP ASVS)

Numeración de ASVS 4.0.3, a nivel de sección; los ítems concretos se fijan en el plan de pruebas del Gate 3.
OWASP Top 10 en su edición 2025.

| ID | Requisito | Estado | ASVS | OWASP Top 10 |
|---|---|---|---|---|
| RS01 | Un cliente solo accede a sus propios bots, contactos y credenciales; todo lo demás se deniega por defecto | Pendiente | V4.1, V4.2 | A01 |
| RS02 | La gestión se autentica con una credencial por cliente, de alta entropía, rotable y comparada en tiempo constante | Parcial: una única clave de operador, de 32 caracteres o más y comparada en tiempo constante | V2.10 | A07 |
| RS03 | Solo se procesan notificaciones con `X-Hub-Signature-256` válida sobre el cuerpo crudo | Construido | V2.10, V9.2 | A08 |
| RS04 | El token de verificación se compara en tiempo constante, y un bot sin token no se puede verificar | Construido | V2.10 | A07 |
| RS05 | El número de teléfono de un contacto se guarda cifrado con una clave propia del cliente dueño del bot, y el contacto se puede localizar sin guardar el número en claro | Pendiente | V6.2, V8.3 | A04 |
| RS06 | Los tokens de Meta y el App Secret de un bot se guardan cifrados y ningún endpoint los devuelve | Pendiente: en claro, y `/info` devuelve los tokens | V6.4, V8.3 | A04 |
| RS07 | Ningún log contiene números, nombres, contenido de mensajes ni credenciales, en ningún nivel | Parcial: el interceptor no registra query strings ni cabeceras; `messages.py` y `facebook.py` sí registran contenido y números por debajo de `production` | V7.1 | A09 |
| RS08 | El mensaje viaja y reposa protegido entre el gateway y el motor: broker en red privada, con usuario propio, y contenido cifrado | Parcial: red privada y usuario propio previstos con Hermod; el cifrado JWE existe y está desactivado | V6.2, V9.2 | A04 |
| RS09 | En internet solo se publica `/chat/<uuid>`; la gestión y la documentación de la API no | Pendiente: sin desplegar | V14.3 | A02 |
| RS10 | El borde limita la tasa de peticiones por origen y por bot | Pendiente | V11.1 | A06 |
| RS11 | Toda entrada se valida contra un esquema estricto y con límite de tamaño | Parcial: Pydantic valida, pero `FacebookRequest` acepta listas sin tipar y no hay límite de tamaño | V5.1, V13.2 | A05 |
| RS12 | Imagen base por digest, dependencias fijadas y analizadas en cada build, y SBOM publicado | Parcial: imagen por digest; sin lockfile, SCA ni SBOM | V14.2 | A03 |
| RS13 | Ningún secreto vive en el repo ni en la imagen, y el servicio no arranca sin su clave de gestión | Construido | V2.10, V14.1 | A02 |
| RS14 | Queda registro de los eventos de seguridad (rechazos, altas, bajas y accesos de gestión), atribuibles a un cliente | Parcial: se registran los rechazos; no hay auditoría por cliente | V7.2 | A09 |
| RS15 | Un error no revela detalles internos y falla cerrado | Parcial: dos funciones de `controller/chatbot.py` devuelven el texto de la excepción en la respuesta | V7.4 | A10 |
| RS16 | El texto del usuario final se trata como entrada no confiable para el LLM, y las llamadas a API de los intents solo pueden ir a destinos permitidos | Pendiente; lo ejecuta el motor de respuestas | V5.2, V12.6 | A05, A06 |
| RS17 | El contenedor corre sin privilegios y solo puede escribir donde necesita | Construido | V14.1 | A02 |

## Threat assessment inicial

```mermaid
flowchart LR
    U([Usuario final]) -->|mensaje| META([Meta])
    ATK([Atacante]) -->|HTTPS| CF
    META -->|"notificacion firmada, HTTPS"| CF([Cloudflare edge])
    CF -->|"tunel saliente, solo /chat/uuid"| GW
    CLI([Cliente]) -.->|"gestion: hoy sin ruta publica"| GW
    subgraph SRV [Trust boundary: servidor midgard]
      subgraph NET [Red Docker hermod]
        GW[Gateway] -->|"AMQP con confirmacion"| Q[(Hermod: cola llm)]
      end
    end
    GW -->|"TLS: bots, contactos, tokens"| DB[(MongoDB Atlas)]
    GW -->|"HTTPS con el token del cliente"| META
    Q -->|AMQP| MOTOR([Motor de respuestas: sin definir])
    MOTOR -.->|"reglas y herramientas"| GW
```
*Eje comportamiento · DFD inicial · Gate 0. Cuatro fronteras: internet ↔ Cloudflare, Cloudflare ↔ servidor (túnel
saliente), servidor ↔ Atlas (los datos personales salen del servidor), y gateway ↔ motor de respuestas, cuya
ubicación no se conoce.*

```mermaid
quadrantChart
    title DREAD inicial - Gateway BaaS
    x-axis Baja probabilidad --> Alta probabilidad
    y-axis Bajo impacto --> Alto impacto
    quadrant-1 Atender ya
    quadrant-2 Monitorear
    quadrant-3 Aceptar
    quadrant-4 Planear
    Acceso cruzado entre clientes: [0.7, 0.95]
    Fuga de numeros y tokens: [0.45, 0.9]
    Gestion expuesta en internet: [0.6, 0.85]
    Datos personales en logs: [0.65, 0.6]
    Prompt injection y SSRF: [0.55, 0.75]
    Notificacion falsa: [0.15, 0.8]
    Reenvio de notificaciones: [0.4, 0.4]
    Inundacion del webhook: [0.55, 0.5]
    Supresion incompleta: [0.5, 0.65]
    Dependencia vulnerable: [0.5, 0.7]
    Mensaje perdido sin aviso: [0.1, 0.6]
```
*Eje trazabilidad · DREAD inicial · Gate 0. "Acceso cruzado" es probable porque el control no existe: basta un
segundo cliente. "Notificación falsa" y "Mensaje perdido" quedan a la izquierda porque sus controles ya están
construidos. El análisis completo, con STRIDE, es entregable del Gate 1.*

## Métricas de éxito

Las del [charter](../00-project/charter.md). Para este MVP, además: los catorce escenarios de abuso tienen un
control construido y una prueba que lo verifica.

## Dependencias y riesgos

- **Motor de respuestas.** RF05, RF07, RNF04 y RS16 dependen de un sistema que no está definido.
- **Meta.** El protocolo del webhook y los términos de uso de WhatsApp Business los fija Meta.
- **MongoDB Atlas.** Los datos personales viven fuera del servidor; su región y sus respaldos están sin confirmar.
- **Servidor sin UPS.** Limita la disponibilidad que se puede prometer (RNF07).

## Decisiones abiertas

Requieren respuesta humana antes de aprobar el Gate 0. Ninguna está decidida en este documento.

1. **Motor de respuestas.** Qué sistema consume la cola `llm`, dónde corre y quién envía la respuesta al usuario
   final (el motor directamente o el gateway, RF07).
2. **Acceso de los clientes a la gestión.** El objetivo "el cliente administra sus bots" exige que la API de
   gestión sea alcanzable por los clientes, y RS09 exige que no esté en internet. Hay que elegir: API pública con
   credencial por cliente, acceso por red privada, o que el operador administre en nombre del cliente.
3. **Alcance de "los números".** Si el cifrado con la clave del cliente cubre solo el número del contacto o también
   el número del bot.
4. **Custodia de la clave del cliente.** Si la genera y guarda la plataforma, o la aporta el cliente. Es decisión
   del Gate 1, pero cambia lo que se le promete al cliente.
5. **Nivel ASVS.** Se propone L2 por tratar datos personales de terceros en un servicio multi-cliente.
6. **Retención.** Plazo de cada dato personal (RNF05).
7. **SLO.** Tiempo de respuesta y disponibilidad del webhook (RNF01, RNF07).
8. **Protección de datos.** Delegado de protección de datos, región de Atlas, contrato de encargo y procedimiento
   de aviso de brechas, detallados en la [clasificación de datos](../00-project/data-classification.md).
