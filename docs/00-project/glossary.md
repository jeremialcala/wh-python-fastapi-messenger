# Glosario / Lenguaje ubicuo

* **Estado:** review
* **Fecha:** 2026-10-12
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 00-project
* **Versión:** 0.1.0
* **Contextos acotados:** Clientes y acceso · Gestión de bots · Mensajería entrante · Contactos · Intents y herramientas · Trazabilidad

Entre paréntesis, el nombre que el término tiene en el código cuando existe. "Sin construir" marca los conceptos
del modelo BaaS que todavía no tienen representación en el código.

| Término | Definición | Contexto acotado |
|---|---|---|
| **Cliente** | Empresa que contrata el servicio. Dueña de sus bots y responsable del tratamiento de los datos de sus usuarios finales. Sin construir: hoy los bots no tienen dueño. | Clientes y acceso |
| **Operador** | Quien opera la plataforma. Encargado del tratamiento frente a los clientes. Hoy es el único con credencial de gestión. | Clientes y acceso |
| **Clave del cliente** | Clave criptográfica propia de un cliente con la que se cifran sus datos sensibles, empezando por los números de teléfono. Sin construir. | Clientes y acceso |
| **Clave de gestión** (`ADMIN_API_KEY`) | Credencial única que hoy abre todos los endpoints de gestión, en la cabecera `X-API-Key`. | Clientes y acceso |
| **Bot** (`ChatBot`) | Un chatbot de un cliente. Tiene una persona (nombre, rol, descripción y tono), sus credenciales de Meta y su configuración. | Gestión de bots |
| **`bot_id`** (`uuid`) | El UUID de un bot. Forma parte de la URL de su webhook, viaja en cada mensaje de la cola y es la llave con la que el motor de respuestas pide la configuración del bot (ADR-0003). Identifica, pero no autoriza: no es un secreto. | Gestión de bots |
| **Persona** | Nombre, rol, descripción y tono con los que el bot se presenta. Encabeza su system prompt. | Gestión de bots |
| **Regla** (`Rule`) | Instrucción en lenguaje natural que se añade al system prompt de un bot. | Gestión de bots |
| **Número del bot** (`ChatbotPhone`) | Número de WhatsApp Business de un cliente asociado a un bot y a un entorno. Lleva el número (`phoneNumber`) y su identificador en Meta (`phoneId`). | Gestión de bots |
| **Token de verificación** (`verifyToken`) | Secreto por bot que Meta devuelve al verificar el webhook. | Gestión de bots |
| **Token de página** (`facebookToken`) y **token de WhatsApp** (`whatsappToken`) | Credenciales de Meta del cliente con las que el gateway consulta perfiles y envía mensajes en su nombre. | Gestión de bots |
| **App Secret** (`appSecret`, `FACEBOOK_APP_SECRET`) | Secreto de la app de Meta con el que se verifica la firma de cada notificación. | Mensajería entrante |
| **Webhook** | La URL `/chat/{bot_id}` de un bot, la única superficie que se publica en internet. | Mensajería entrante |
| **Verificación** | El `GET` con el que Meta comprueba que el webhook es de quien dice ser, usando el token de verificación. | Mensajería entrante |
| **Notificación** (`FacebookRequest`) | El `POST` firmado con el que Meta entrega uno o varios mensajes de un canal. | Mensajería entrante |
| **Canal** | Messenger (`object=page`) o WhatsApp Business (`object=whatsapp_business_account`). | Mensajería entrante |
| **Mensaje** (`MessageBody`) | El contenido normalizado que sale del gateway: bot, canal, contacto y mensaje original. | Mensajería entrante |
| **Cola `llm`** | Cola durable de RabbitMQ donde el gateway publica cada mensaje. Es la frontera con el motor de respuestas. | Mensajería entrante |
| **Hermod** | La instancia de RabbitMQ de la plataforma en `midgard`. | Mensajería entrante |
| **Motor de respuestas** (`ms-python-metamsghandler`) | Servicio aparte, con su propio repositorio, que consume la cola `llm`: normaliza el mensaje, lo filtra con guardrails y clasifica la intención del usuario. Es también quien genera la respuesta o ejecuta la acción que el usuario pide, y quien envía la respuesta al destinatario (ADR-0002); esa parte está en implementación. | Mensajería entrante |
| **Resultado clasificado** | Lo que el motor de respuestas publica en la cola `meta-classified` por cada mensaje: si se permite, su intención y el tipo de respuesta que requiere (texto, acción o adjunto). | Mensajería entrante |
| **Usuario final** | Persona que escribe a un bot. Es el interesado en términos del GDPR. | Contactos |
| **Contacto** (`Contact`) | El registro de un usuario final para un bot: nombre, foto de perfil e identificador en el canal. | Contactos |
| **Número del contacto** (`waId`) | El número de teléfono de WhatsApp de un usuario final. Dato personal que debe guardarse cifrado con la clave del cliente. | Contactos |
| **PSID** (`fbId`) | Identificador de un usuario de Messenger, propio de cada página. | Contactos |
| **Intent** (`Intent`) | Algo que el bot sabe hacer, con sus frases de ejemplo y sus acciones. | Intents y herramientas |
| **Acción** (`Action`) | Una operación concreta de un intent, con sus parámetros y su llamada a una API (`ApiCall`). | Intents y herramientas |
| **Herramienta** | Una acción expresada como definición de herramienta para el LLM. Las entrega `/chat/{bot_id}/tools`. | Intents y herramientas |
| **Evento** (`Event`) y **acción de evento** (`EventAction`) | Registro de una petición y de sus pasos. Implementado y hoy desactivado. | Trazabilidad |
| **Responsable del tratamiento** | Quien decide para qué y cómo se tratan los datos personales (GDPR, art. 4.7). Aquí, el cliente. | Clientes y acceso |
| **Encargado del tratamiento** | Quien trata datos por cuenta del responsable (GDPR, art. 4.8). Aquí, el operador. | Clientes y acceso |
| **Interesado** | La persona a la que se refieren los datos. Aquí, el usuario final. | Contactos |
