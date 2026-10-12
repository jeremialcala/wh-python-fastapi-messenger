# ADR-0007: El App Secret que verifica la firma es el del bot, con uno global de respaldo

* **Estado:** accepted
* **Fecha:** 2026-10-12
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 02-design
* **Versión:** 0.1.0
* **ID:** ADR-0007
* **Supersede:** —
* **Controles OWASP afectados:** A08 (integridad de las notificaciones), A04 (custodia del secreto)

Decisión ya construida (PR #3, versión 0.1.0). Se registra aquí para que conste con sus alternativas.

## Contexto

Meta firma cada notificación con el App Secret de la app de Meta que la envía. En un servicio con varios clientes,
cada cliente tiene su propia app de Meta y, por tanto, su propio App Secret.

## Decisión

La firma de una notificación se verifica con el `appSecret` guardado en el documento del bot. Si el bot no lo
tiene, se usa `FACEBOOK_APP_SECRET`, de la configuración del servicio. Sin ninguno de los dos, la notificación se
rechaza.

## Alternativas consideradas

| Opción | Pros | Contras | Riesgo de seguridad |
|---|---|---|---|
| **Secreto por bot, con uno global de respaldo** | Sirve para un solo operador y para varios clientes sin cambiar código | Dos sitios donde puede estar el secreto | Bajo si falla cerrado |
| Un único secreto global | Lo más simple | Obliga a que todos los bots sean de la misma app de Meta | No sirve al modelo BaaS |
| Solo secreto por bot | Un único sitio | Obliga a cargar el secreto en cada bot incluso con un solo operador | Bajo |

## Consecuencias

- Positivas: cada cliente puede usar su propia app de Meta.
- Negativas / deuda asumida: el `appSecret` se guarda en claro y se carga a mano en la base. Debe cifrarse con la
  clave de cifrado de datos del cliente (RS06, ADR-0010) y cargarse por API (RF06).
- Impacto en threat model: una fuga de la base expone los App Secret, y con ellos la capacidad de firmar
  notificaciones falsas (T3, T1).
