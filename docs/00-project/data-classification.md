# Clasificación de datos

* **Estado:** approved (Gate 0, 2026-10-12)
* **Fecha:** 2026-10-12
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 00-project
* **Versión:** 0.1.0
* **Owner de datos (DPO):** `<TODO: designar o confirmar que no aplica>`
* **Regulación aplicable:** GDPR (Reglamento (UE) 2016/679), adoptado como modelo de diseño

Niveles: Público < Interno < Confidencial < Restringido.

## Roles

| Rol GDPR | Quién | Consecuencia para el diseño |
|---|---|---|
| Responsable del tratamiento (art. 4.7) | Cada cliente, para los datos de los usuarios finales de sus bots | Decide finalidad y base jurídica; el gateway no las decide por él |
| Encargado del tratamiento (art. 4.8) | El operador de la plataforma | Trata solo por instrucción del cliente y con las garantías del art. 28 |
| Interesado | El usuario final que escribe a un bot | Titular de los derechos de los arts. 15 a 22 |
| Subencargados | MongoDB Atlas (base de datos), Cloudflare (túnel y TLS) y, si el motor de respuestas usa inferencia gestionada, el proveedor del LLM | Deben constar en el contrato de encargo con cada cliente |
| Tercero necesario | Meta | Es el canal: recibe y entrega los mensajes bajo sus propios términos con el cliente |

## Inventario

"Protección hoy" describe lo que hace el código el 2026-10-12, no el objetivo.

| Dato | Clasificación | Dónde vive | Protección hoy | Protección requerida | Retención |
|---|---|---|---|---|---|
| Número de teléfono del contacto (`Contact.waId`) | **Restringido** (personal) | MongoDB; mensaje de la cola; logs por debajo de `production` | Cifrado en MongoDB con la clave de datos del cliente, y localizable por un índice ciego. En claro en el mensaje de la cola y en los logs por debajo de `production` | Cifrado con la clave del cliente; localizable sin guardarlo en claro (RS05) | 12 meses sin actividad como máximo; antes si el cliente lo fija o borra el contacto |
| Nombre y foto de perfil del contacto (`firstName`, `lastName`, `profilePic`) | **Confidencial** (personal) | MongoDB; el nombre viaja también en el mensaje de la cola | En claro | Acceso solo del cliente dueño (RS01) | 12 meses sin actividad como máximo; antes si el cliente lo fija o borra el contacto |
| Identificador de Messenger del contacto (`fbId`, PSID) | **Confidencial** (personal) | MongoDB; mensaje de la cola | En claro | Acceso solo del cliente dueño (RS01) | 12 meses sin actividad como máximo; antes si el cliente lo fija o borra el contacto |
| Contenido de los mensajes | **Restringido** (personal; puede incluir categorías especiales del art. 9) | Cola `llm` hasta que se consume; logs por debajo de `production`; después, el motor de respuestas y su LLM. El gateway no lo guarda en MongoDB | En claro en la cola y en esos logs | Fuera de los logs (RS07); protegido en la cola (RS08) | 24 horas en la cola como máximo |
| Tokens de Meta del cliente (`facebookToken`, `whatsappToken`) y `appSecret` | **Restringido** (credencial) | MongoDB; el motor de respuestas necesita los tokens para enviar | Cifrados con la clave de datos del cliente; se cargan por la API y ningún endpoint los devuelve | Cifrados en reposo, fuera de la API de gestión y accesibles solo para el motor con credencial de servicio (RS06) | Hasta la baja del bot |
| Token de verificación del bot (`verifyToken`) | **Confidencial** (credencial) | MongoDB | Cifrado con la clave de datos del cliente; comparado en tiempo constante; solo lo lee su cliente | Igual que los tokens (RS06) | Hasta la baja del bot |
| Número del bot (`ChatbotPhone.phoneNumber`, `phoneId`) | **Confidencial** | MongoDB | Cifrados con la clave de datos del cliente | Cifrado con la clave de cifrado de datos del cliente (RS05) | Hasta la baja del bot |
| Persona, reglas e intents del bot | **Confidencial** (del cliente) | MongoDB; el motor de respuestas los pide por `bot_id` | En claro | Acceso solo del cliente dueño y del motor (RS01, RS06) | Hasta la baja del bot |
| Identificador del bot (`bot_id`) | **Interno** | URL del webhook, configuración de Meta del cliente, mensajes de la cola y logs | No es un secreto | No debe bastar para acceder a nada (RS18) | Hasta la baja del bot |
| Clave privada de firma del cliente | **Restringido** | En poder del cliente; nunca llega a la plataforma | No existe todavía | El gateway solo registra la parte pública (ADR-0005) | La decide el cliente |
| Clave de cifrado de datos del cliente | **Restringido** | Registro del cliente, en MongoDB, envuelta por la clave maestra de Andvari | Solo se guarda envuelta; abierta, en la memoria del gateway cinco minutos como máximo | Cifra los números de teléfono y las credenciales del cliente (ADR-0010, ADR-0013) | Mientras existan datos cifrados con ella |
| Clave privada de cifrado del gateway | **Restringido** | Fichero en el servidor (`GATEWAY_KEYS_FILE`) | Fuera del repo y de la imagen; legible solo por la cuenta del contenedor | Abre los tokens de autenticación; fuera del repo y de la imagen | Hasta rotación |
| Clave pública de firma de un cliente | **Interno** | Registro del cliente, en MongoDB | En claro: es pública | Con ella se verifica quién envía; su parte privada no sale del cliente | Hasta que el cliente la revoca |
| Credenciales de MongoDB y RabbitMQ | **Restringido** | `config.env` o `.env` del servidor | Fuera del repo y de la imagen | Igual | Hasta rotación |
| Claves privadas por evento (`certs/*.pem`) | **Restringido** | Disco del contenedor | Ignoradas por git y fuera de la imagen. Función desactivada | Decidir en el Gate 1 si se mantienen | Se decide en el Gate 1, junto con la función |
| Registro de eventos (`Event`, `EventAction`) con IP de origen | **Interno** (la IP es dato personal) | MongoDB. Función desactivada | — | Definir antes de reactivarlo | Se decide en el Gate 1, junto con la función |
| Logs de la aplicación | **Confidencial** | Salida del contenedor; Docker conserva 3 ficheros de 10 MB | En `production` solo avisos y errores; por debajo, incluyen nombres, números y contenido | Sin datos personales en ningún nivel (RS07) | La rotación de Docker |
| Respaldos de la base | **Restringido** | Los gestiona Atlas; `<TODO: confirmar plan y región>` | Sin comprobar | Cifrados y con la misma retención que el dato | La del dato respaldado; sin comprobar en Atlas |
| Código, documentación e imagen | **Público** | GitHub y GHCR | Sin secretos | Igual | Indefinida |

## Reglas

1. Nada clasificado como Restringido o Confidencial entra en el repositorio ni en la imagen.
2. Un dato personal solo se guarda si hace falta para entregar el mensaje o para que el cliente administre su bot
   (minimización, art. 5.1.c).
3. Ningún dato personal se escribe en los logs, en ningún nivel.
4. Los datos de un cliente son accesibles solo con la credencial de ese cliente. El operador accede por necesidad
   operativa y deja rastro.
5. La baja de un bot o de un cliente borra sus datos, incluidos los de sus contactos (art. 28.3.g).

## Decidido al aprobar el Gate 0 (2026-10-12)

- **Retención.** Máximos de la plataforma que cada cliente puede acortar: 24 horas para un mensaje en la cola y
  12 meses sin actividad para un contacto. Ninguno está implementado todavía (RNF05).
- **Alcance de "los números".** El cifrado con la clave del cliente cubre el número del contacto y el número del
  bot (RS05).

## Datos por aportar

- **Delegado de protección de datos.** Sin designar, y sin confirmar que no aplique.
- **Región de la base.** No consta en qué región está el clúster de Atlas; determina si hay transferencia
  internacional (arts. 44 y siguientes). Comprobado el 2026-10-12: los nodos del clúster configurado no están en
  los rangos de direcciones que publican AWS y Google Cloud, lo que apunta a Azure. La región exacta hay que
  leerla en la consola de Atlas.
- **Dónde corre el LLM.** El motor de respuestas envía el texto de los mensajes a un LLM. Si es un servicio
  gestionado fuera de la UE hay otra transferencia internacional. Se decide en el repositorio del motor, pero
  afecta a lo que este servicio le promete al cliente.

## Entregables anteriores al primer cliente externo

- **Contrato de encargo.** Un modelo de contrato del art. 28 con los clientes y un registro de actividades del
  art. 30.
- **Brechas.** Un procedimiento para avisar a los clientes de una violación de seguridad (art. 33.2).
