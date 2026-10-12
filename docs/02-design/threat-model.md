# Threat model — Gateway BaaS de mensajería

* **Estado:** approved (Gate 1, 2026-10-12)
* **Fecha:** 2026-10-12
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 02-design
* **Versión:** 0.2.0
* **Gate:** 1
* **Alcance:** el gateway, su cola en Hermod, su base en MongoDB Atlas, el túnel y el despliegue; el motor de respuestas solo en su frontera con el gateway
* **Metodología:** STRIDE por elemento del DFD + DREAD para priorizar
* **Clasificación de datos (ref):** [`docs/00-project/data-classification.md`](../00-project/data-classification.md)

Parte del threat assessment inicial del [PRD](../01-requirements/mvp-baas-gateway.md). Cada amenaza indica si su
control está **construido**, **parcial** o **pendiente**: este documento describe el diseño, no afirma que todo
esté hecho.

## Diagrama de flujo de datos (DFD)

```mermaid
flowchart LR
    U([Usuario final]) -->|"1 mensaje"| META([Meta])
    ATK([Atacante]) -->|"2 HTTPS"| CF
    META -->|"2 notificacion firmada"| CF([Cloudflare edge])
    CLI([Cliente]) -.->|"9 gestion con token: hoy sin ruta publica"| CF
    CF -->|"3 tunel saliente, solo /chat/uuid"| TUN
    subgraph SRV [TB2: servidor midgard]
      TUN[cloudflared] -->|"4 HTTP loopback"| GW
      OP([Operador]) -->|"10 gestion, red privada"| GW
      RCV[Receptor de despliegue] -->|"12 compose up"| GW
      subgraph NET [TB3: red Docker hermod]
        GW[Gateway] -->|"6 AMQP confirmado"| Q[(Hermod: cola llm)]
      end
      ENV[(Secretos: .env del servidor)] -.-> GW
    end
    GW -->|"5 TLS"| DB[(MongoDB Atlas)]
    GW -->|"7 perfil del contacto, HTTPS"| META
    Q -->|"8 AMQP"| MOTOR([Motor de respuestas])
    MOTOR -.->|"9 configuracion por bot_id, con token"| GW
    MOTOR -.->|"13 respuesta al usuario"| META
    MOTOR -->|"14 texto del mensaje"| LLM([LLM])
    GH([GitHub: main, GHCR]) -->|"11 webhook firmado e imagen"| RCV
```
*Eje comportamiento · DFD STRIDE · Gate 1. TB1 = internet ↔ Cloudflare; TB2 = el túnel entra en el servidor; TB3 =
red Docker privada del broker; TB4 = servidor ↔ Atlas; TB5 = gateway ↔ motor de respuestas; TB6 = motor ↔ LLM. Las
líneas discontinuas son flujos del diseño que hoy no existen.*

## Análisis STRIDE

| ID | Elemento | STRIDE | Amenaza | Control | Estado | Traza |
|---|---|---|---|---|---|---|
| T1 | Flujo 2/3 | S | Un tercero envía una notificación falsa para inyectar mensajes en la cola | Firma `X-Hub-Signature-256` sobre el cuerpo crudo, con el App Secret del bot; sin secreto se rechaza | Construido | RS03, ADR-0004, ADR-0007 |
| T2 | Gateway, flujo 9 | E, I | Un cliente lee o modifica bots, contactos o credenciales de otro usando su UUID | `clientId` en cada documento y capa de repositorio que lo exige; lo ajeno responde `404` | Construido | RS01, ADR-0012 |
| T3 | Base, flujo 5 | I | Una copia de la base expone números, tokens de Meta y App Secret | Cifrado de esos campos con la clave de datos del cliente e índice ciego para buscar por número | Pendiente | RS05, RS06, ADR-0010 |
| T4 | Flujo 3 | I, E | La gestión o la documentación de la API quedan alcanzables desde internet | El túnel publica solo `/chat/<uuid>`; el contenedor escucha en loopback | Pendiente: sin desplegar | RS09, ADR-0008 |
| T5 | Flujo 2/3, 9 | S | Fuerza bruta contra el token de verificación o las credenciales de gestión | Comparación en tiempo constante del token de verificación; para la gestión no hay secreto que adivinar, sino una firma `ES256`; límite de tasa en el borde | Parcial: falta el límite de tasa | RS02, RS04, RS10 |
| T6 | Gateway | I | Los logs contienen números, nombres y contenido de mensajes | Sin datos personales en ningún nivel de log | Parcial: el interceptor ya no registra query strings ni cabeceras; `messages.py` y `facebook.py` sí registran datos por debajo de `production` | RS07 |
| T7 | Flujo 2/3, 6 | T | Una notificación legítima se entrega o se reenvía dos veces y se procesa dos veces | Identificador de Meta en el sobre y deduplicación en el motor durante 24 horas | Pendiente | RNF04, ADR-0011 |
| T8 | Flujo 9 | S | Alguien fabrica un token de gestión, o captura uno válido y lo reenvía | JWT firmado por el cliente dentro de un JWE; caducidad de 60 segundos y un solo uso | Construido | RS02, ADR-0005, ADR-0009 |
| T9 | Flujo 2/3 | D | Una ráfaga de notificaciones agota el worker o llena la cola | Límite de tasa en el borde; tope de memoria y CPU del contenedor; caducidad de los mensajes | Parcial: solo el tope del contenedor | RS10, RNF03, RNF05 |
| T10 | Flujo 14 | E, T | Un usuario final escribe instrucciones para que el LLM invoque herramientas del cliente | Guardrails de entrada y salida del LLM tratada como no confiable, en el motor | Parcial: según la documentación del motor; no verificado aquí | RS16 |
| T11 | Gateway, motor | E, I | Un cliente define un intent cuya llamada a API apunta a la red interna | Validar el destino de `ApiCall` al guardarlo y al ejecutarlo: solo HTTPS y sin direcciones internas | Pendiente | RS16 |
| T12 | Flujo 9 | I, E | El motor, o quien robe su credencial, obtiene los tokens de Meta de todos los clientes | Cliente de servicio con alcance de solo lectura, cada acceso registrado, credencial rotable | Pendiente | RS06, ADR-0003, ADR-0009 |
| T13 | Cola, flujo 6/8 | I, T | Quien entre en la red del broker lee o altera los mensajes | Red Docker privada y un usuario del broker por servicio; cifrado del cuerpo en una segunda fase | Parcial: la red y el broker existen; el usuario del gateway y el cifrado, no | RS08, ADR-0011 |
| T14 | Flujo 11 | T | Una dependencia vulnerable o una imagen manipulada llegan a producción | Imagen base por digest; dependencias fijadas con hashes; análisis de dependencias, de secretos y estático en el pipeline; SBOM | Parcial: falta el SBOM | RS12 |
| T15 | Secretos | I | Se filtran el `.env` del servidor, la clave privada del gateway o la clave maestra | Fuera del repo y de la imagen, permisos restringidos, y nunca impresos al diagnosticar | Parcial: la clave privada del gateway es un fichero del servidor, fuera del repo y de la imagen; la clave maestra vive en Andvari y el gateway aún no la usa | RS13, ADR-0008, ADR-0010 |
| T16 | Flujo 6 | D | El broker no está disponible y el mensaje se pierde con un `200` a Meta | Publicación confirmada; `503` si falla | Construido | RNF02, ADR-0006 |
| T17 | Base, cola, logs | I | Un interesado pide la supresión y sus datos siguen en la cola, los logs o los respaldos | Borrado por contacto, caducidad en la cola, logs sin datos personales y destrucción de la clave de datos | Pendiente | RF09, RF10, RNF05, ADR-0010 |
| T18 | Gateway | I | Un error devuelve detalles internos en la respuesta | Respuesta de error genérica y fallo cerrado | Parcial: dos funciones devuelven el texto de la excepción | RS15 |
| T19 | Flujo 11/12 | T, E | Un commit malicioso en `main` se construye y se despliega solo | `main` solo admite pull requests, desde ramas permitidas; las pruebas condicionan la imagen; rollback si falla la sonda de vida | Construido; el despliegue en el servidor está sin ejercitar | RF11, ADR-0008 |
| T20 | Gateway | R | No se puede saber qué cliente hizo qué | Registro de eventos de seguridad atribuido al cliente autenticado | Parcial: solo se registran los rechazos | RS14 |
| T21 | Flujo 2/3 | D, T | Un cuerpo malformado o enorme provoca errores o consume memoria | Esquema estricto de la notificación y límite de tamaño en el borde | Parcial: el esquema admite listas sin tipar | RS11 |

## Amenazas priorizadas (DREAD)

Puntuación de 1 a 10 por criterio, con los controles tal como están **hoy**. La puntuación es la media.

| ID | Amenaza | Daño | Reproducible | Explotable | Afectados | Descubrible | Score |
|---|---|---|---|---|---|---|---|
| T2 | Acceso cruzado entre clientes | 9 | 9 | 7 | 9 | 6 | 8,0 |
| T4 | Gestión expuesta en internet | 9 | 9 | 6 | 9 | 7 | 8,0 |
| T3 | Fuga de la base | 9 | 8 | 4 | 10 | 5 | 7,2 |
| T8 | Token fabricado o reenviado | 8 | 8 | 5 | 8 | 5 | 6,8 |
| T12 | Tokens al alcance del motor | 9 | 7 | 4 | 10 | 4 | 6,8 |
| T6 | Datos personales en logs | 6 | 9 | 5 | 8 | 5 | 6,6 |
| T14 | Cadena de suministro | 8 | 6 | 5 | 9 | 5 | 6,6 |
| T9 | Inundación del webhook | 5 | 8 | 6 | 7 | 6 | 6,4 |
| T10 | Prompt injection | 7 | 7 | 6 | 5 | 6 | 6,2 |
| T11 | SSRF por intents | 8 | 7 | 5 | 6 | 5 | 6,2 |
| T15 | Secretos del servidor | 9 | 5 | 3 | 10 | 3 | 6,0 |
| T17 | Supresión incompleta | 6 | 9 | 3 | 7 | 5 | 6,0 |
| T21 | Entrada malformada | 4 | 8 | 6 | 5 | 6 | 5,8 |
| T13 | Lectura de la cola | 7 | 6 | 3 | 8 | 4 | 5,6 |
| T7 | Duplicados | 4 | 8 | 5 | 5 | 5 | 5,4 |
| T19 | Despliegue malicioso | 9 | 3 | 2 | 10 | 3 | 5,4 |
| T18 | Errores con detalles | 3 | 8 | 6 | 3 | 6 | 5,2 |
| T5 | Fuerza bruta | 6 | 5 | 3 | 6 | 5 | 5,0 |
| T20 | Sin auditoría por cliente | 5 | 9 | 2 | 6 | 3 | 5,0 |
| T1 | Notificación falsa | 7 | 2 | 2 | 6 | 5 | 4,4 |
| T16 | Mensaje perdido | 5 | 2 | 2 | 5 | 3 | 3,4 |

T2 y T4 puntúan tan alto porque dependen de algo que todavía no existe: con un solo operador y la gestión en red
privada ninguna de las dos se puede explotar, pero bastan un segundo cliente o una regla de túnel mal puesta. T1 y
T16 quedan al final porque sus controles están construidos y probados.

```mermaid
quadrantChart
    title DREAD - Gateway BaaS, con los controles de hoy
    x-axis Baja probabilidad --> Alta probabilidad
    y-axis Bajo impacto --> Alto impacto
    quadrant-1 Atender ya
    quadrant-2 Monitorear
    quadrant-3 Aceptar
    quadrant-4 Planear
    T2 acceso cruzado: [0.72, 0.92]
    T4 gestion expuesta: [0.68, 0.88]
    T3 fuga de la base: [0.45, 0.95]
    T12 tokens y motor: [0.42, 0.86]
    T8 token reenviado: [0.55, 0.78]
    T6 datos en logs: [0.62, 0.6]
    T14 suministro: [0.5, 0.82]
    T11 SSRF: [0.52, 0.72]
    T9 inundacion: [0.6, 0.5]
    T17 supresion: [0.48, 0.62]
    T7 duplicados: [0.55, 0.38]
    T19 despliegue: [0.15, 0.9]
    T1 notificacion falsa: [0.12, 0.66]
    T16 mensaje perdido: [0.1, 0.45]
```
*Eje trazabilidad · DREAD · Gate 1.*

## Hallazgos del diseño

Defectos que salieron al contrastar el código con el diseño. Los cuatro primeros se comprobaron ejecutándolo.

| ID | Hallazgo | Impacto | Estado |
|---|---|---|---|
| H1 | **Los valores por defecto se calculan una vez, al importar.** Los campos de las entidades usan `default=uuid4()` y `default=datetime.now()`, con paréntesis: el valor queda fijado al arrancar. Hay 28 campos así | `createdAt` y `statusDate` de todos los documentos guardan la hora de arranque del proceso, no la de creación. El `_uuid` de los mensajes de la cola es el mismo en todos. Los demás identificadores se salvan porque el código los asigna de forma explícita | **Corregido** en la base del Gate 2: los valores por defecto se calculan por objeto, con pruebas que lo exigen |
| H2 | **`metadata` de WhatsApp sale mal serializado** hacia la cola: una lista de pares en vez de un objeto | El motor no puede leer `phone_number_id`, que necesita para responder | Abierto; ADR-0011 |
| H3 | **El motor rechaza los mensajes de Messenger** que publica el gateway y **descarta el `botId`** | Messenger no funciona de extremo a extremo; el motor no puede pedir la configuración del bot | Abierto; ADR-0011, en el repositorio del motor |
| H4 | **`GET /chat/{bot_id}/info` devuelve los tokens de Meta** | Quien se autentique como dueño del bot los lee; el aislamiento impide que los lea otro cliente | Abierto; RS06 |
| H5 | **El contrato OpenAPI no declara ningún esquema de seguridad**: la autenticación se hace en dependencias que OpenAPI no ve | Quien lea el contrato no sabe que hace falta credencial; las herramientas de análisis tampoco | Abierto |
| H6 | **Los valores por defecto y los ejemplos de los DTO son aleatorios**, generados con Faker al importar | La documentación de la API cambia en cada arranque. El contrato versionado los omite por eso | Abierto |

## Controles y trazabilidad

Cada amenaza tiene su control en un requisito del PRD y, donde hubo que elegir, en una ADR: son las columnas
"Control" y "Traza" de la tabla STRIDE. El mapeo general a OWASP Top 10:2025 está en
[`.ai-dlc/owasp-mapping.md`](../../.ai-dlc/owasp-mapping.md), todavía sin adaptar a este servicio.

Orden de construcción que se desprende de la prioridad:

1. **Registro de clientes y aislamiento** (T2): ADR-0012. Sin él no puede haber un segundo cliente.
2. **Autenticación con token** (T8, T12, T5): ADR-0005 y ADR-0009. Habilita publicar la gestión (T4).
3. **Cifrado de datos por cliente** (T3, T17, T15): ADR-0010.
4. **Contrato de la cola, versión 1** (T7, T13, H1, H2, H3): ADR-0011.
5. **Higiene**: logs sin datos personales (T6), errores sin detalles (T18), esquema estricto (T21), cadena de
   suministro (T14), validación de destinos de los intents (T11).

## Verificación prevista (Gate 3)

| Amenaza | Prueba |
|---|---|
| T1, T16 | Ya cubiertas por `tests/unit/test_webhook_security.py` |
| T2 | Ya cubierta por `tests/unit/test_client_isolation.py` (todas las rutas con otro cliente: `404`), `test_tenant_repository.py` y `test_data_access_boundary.py` (nada consulta la base fuera del repositorio). Las rutas se recorren con tokens reales de dos clientes |
| T3 | Volcar la base de pruebas y comprobar que ningún número ni token aparece en claro |
| T4 | Desde fuera de la red, cualquier ruta que no sea `/chat/<uuid>` no responde |
| T7 | Publicar dos veces el mismo mensaje y comprobar que el motor lo procesa una |
| T8 | Ya cubierta por `tests/unit/test_authentication.py`: caducado, con `aud` ajeno, con `jti` repetido, con algoritmo no permitido, firmado con otra clave o en nombre de otro cliente; todos rechazados, y cada uno por la comprobación que le toca |
| T6 | Procesar un mensaje en nivel `DEBUG` y comprobar que el log no contiene el número ni el texto |
| Contratos | `tests/contract`: el OpenAPI versionado coincide con la aplicación, y el mensaje real de la cola cumple el AsyncAPI |
