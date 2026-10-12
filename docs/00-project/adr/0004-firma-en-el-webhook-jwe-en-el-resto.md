# ADR-0004: El webhook se autentica con la firma de Meta; el resto de endpoints, con JWE por cliente

* **Estado:** accepted
* **Fecha:** 2026-10-12
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 00-project
* **Versión:** 0.1.0
* **ID:** ADR-0004
* **Supersede:** —
* **Controles OWASP afectados:** A01 (aislamiento entre clientes), A07 (autenticación de la gestión), A04 (material de clave por cliente), A08 (integridad de las notificaciones)

## Contexto

El gateway tiene dos superficies distintas. El webhook lo llama Meta, que no puede presentar otra credencial que
su firma sobre el cuerpo. Todo lo demás (alta y configuración de bots, reglas, intents, y la configuración que el
motor de respuestas pide por `bot_id`, [ADR-0003](0003-el-bot-id-es-la-llave-de-la-configuracion.md)) lo llaman los
clientes, el operador y el motor.

Hoy esa segunda superficie se protege con una única clave compartida, `ADMIN_API_KEY`, en la cabecera `X-API-Key`.
Una sola clave no distingue a un cliente de otro, así que no sirve para el modelo BaaS: no hay forma de que cada
cliente administre solo lo suyo (RS01 del [PRD](../../01-requirements/mvp-baas-gateway.md)).

## Decisión

1. **Las rutas del webhook (`GET` y `POST /chat/{bot_id}`) son las únicas que se autentican solo con la firma**: el
   token de verificación en el `GET` y `X-Hub-Signature-256` en el `POST`. La firma no viaja más allá del gateway.
2. **Todos los demás endpoints se autentican con JWE.**
3. **El registro de cada cliente es lo que permite controlar sus elementos por separado**: sus claves, sus bots y
   los datos de sus bots. Cada cliente se registra y obtiene material de clave propio; con él se autentica y con él
   se delimita lo que puede ver.

La clave única `ADMIN_API_KEY` queda como mecanismo provisional hasta que exista la autenticación con JWE.

## Alternativas consideradas

| Opción | Pros | Contras | Riesgo de seguridad |
|---|---|---|---|
| **JWE con material de clave por cliente** | Identifica al cliente en cada petición; el mismo registro sirve para autenticar y para cifrar sus datos; el código ya tiene las piezas (`jwcrypto`, entidad `Jwk`, cabecera protegida) | Hay que construir el registro de clientes y la gestión de claves; más complejo de usar para el cliente que una clave | Depende del formato del token: ver "Abierto" |
| Seguir con una clave compartida | Ya está construido y probado | No distingue clientes: no hay aislamiento posible | Alto en un servicio con más de un cliente |
| Una clave de API por cliente | Sencillo; distingue clientes | Secreto estático que viaja en cada petición; no aporta nada al cifrado de los datos del cliente | Medio: una clave filtrada vale hasta que se rota |

## Consecuencias

- Positivas: autenticación y aislamiento descansan en lo mismo, el registro del cliente. El motor de respuestas se
  registra como un cliente de servicio más, con su propio material de clave y alcance de solo lectura.
- Negativas / deuda asumida:
  - No existe la entidad cliente ni su registro. Es el primer trabajo de construcción que abre esta decisión (RF01).
  - El material de clave que hay hoy en el código es por evento, no por cliente, y esa función está desactivada.
  - Los requisitos RS02 y RS06 se reescriben; la clave de gestión y sus pruebas actuales se sustituirán.
- Impacto en threat model: el registro de clientes pasa a ser el activo más sensible del sistema, porque de él
  cuelgan la autenticación y el cifrado de los datos de cada cliente.

## Abierto

Decisiones de diseño del Gate 1:

- **Cómo demuestra el JWE quién lo envía.** Resuelto en
  [ADR-0005](0005-jwt-firmado-por-el-cliente-dentro-del-jwe.md): lleva dentro un JWT firmado por el cliente. El
  problema de partida: JWE cifra; por sí solo no siempre autentica. Con el algoritmo que usa
  hoy el código (`RSA-OAEP-256`), cualquiera que tenga la clave pública del destinatario puede fabricar un JWE
  válido. Para que autentique hace falta que el token demuestre la posesión de un secreto del cliente: una clave
  simétrica por cliente, o un JWT firmado por el cliente dentro del JWE.
- **Caducidad y reenvío.** Un token capturado no debe poder reutilizarse: fecha de expiración corta e identificador
  de un solo uso.
- **Custodia.** Dónde vive la clave privada o simétrica de cada cliente, quién la genera y cómo se rota.
- **Exposición.** Si los endpoints autenticados con JWE se publican en internet o siguen en red privada (RS09).
