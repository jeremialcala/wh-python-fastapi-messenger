# ADR-0022: Cada worker del motor tiene su propia credencial, con sus rutas

* **Estado:** proposed
* **Fecha:** 2026-10-18
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 02-design
* **Versión:** 0.1.0
* **ID:** ADR-0022
* **Supersede:** — (amplía [ADR-0016](0016-credencial-del-motor-por-cliente.md): la clave sigue siendo por cliente, y
  ahora también por worker)
* **Controles OWASP afectados:** A01 (mínimo privilegio entre servicios), A07 (credenciales de servicio)

Propuesta para el Gate 1 del refactor ([plan](../plan-topologia-de-workers.md), R5). Decisión D3 del 2026-10-18.

## Contexto

[ADR-0016](0016-credencial-del-motor-por-cliente.md) le dio al motor una clave por cliente, que alcanza cuatro
rutas: las reglas, las herramientas y los tokens de Meta de un bot, y las claves públicas del gateway. Con el motor
partido en workers, esa clave estaría en todos ellos, y la de cualquiera alcanzaría los tokens de Meta, que solo
necesita el notificador. Es el escenario AB21 del PRD.

## Decisión

**Una clave de servicio por cliente y por worker.** El registro dice de qué worker es cada clave, y eso decide qué
rutas alcanza:

| Worker | Rutas |
|---|---|
| Clasificador | Reglas del bot |
| Coordinador | Reglas, herramientas y las 10 últimas vueltas de una conversación (RF15) |
| Enlace | Herramientas |
| Respuesta | Reglas |
| Evaluador | Reglas |
| Notificador | Tokens de Meta del bot |
| Todos | Claves públicas del gateway |

1. **Al registrar la clave**, el operador dice de qué worker es (`POST /clients/{client_id}/service-keys` con el
   campo `worker`). Admite dos por worker y cliente, para rotar sin corte.
2. **Quién firma lo dice el registro, no el token.** Igual que en ADR-0016: el `kid` dice qué clave es, y la clave,
   de qué worker.
3. **Una ruta nueva nace cerrada para todos los workers**, hasta que se apunte en esa tabla.
4. **Las claves de ADR-0016, sin worker**, siguen alcanzando sus cuatro rutas hasta que el motor pase a una por
   worker. Cada uso deja un aviso en el log, y se retiran al terminar el refactor.
5. **En el bus pasa lo mismo:** cada worker tiene su usuario en Bifröst, con sus sujetos (RS20,
   [ADR-0019](0019-nats-jetstream-como-bus.md)).

## Alternativas consideradas

| Opción | Pros | Contras | Riesgo de seguridad |
|---|---|---|---|
| **Una clave por cliente y por worker** | La clave robada de un worker solo alcanza lo que ese worker usa, y de un cliente | Más claves que registrar y rotar: seis por cliente | El menor de los razonables |
| Una clave por cliente para todo el motor (lo de ADR-0016) | Nada que cambiar | La clave de cualquier worker alcanza los tokens de Meta | AB21 tal cual |
| Una clave por worker para todos los clientes | Seis claves en total | Una clave robada alcanza a todos los clientes | Lo que ADR-0016 descartó (T12) |

## Consecuencias

- **El motor custodia seis claves por cliente**, en vez de una. Generarlas y registrarlas tiene que ser un comando,
  no un procedimiento a mano.
- **El registro de clientes cambia:** la clave de servicio lleva su worker, y `GET /keys` lo muestra.
- **Una ruta nueva para el coordinador:** las 10 últimas vueltas de una conversación. Se fija con el historial.
- **El log dice qué worker pidió los tokens**, además del cliente y la clave.

## Condiciones de revisión

- El motor cambia su partición en workers.
- El número de clientes hace inmanejable registrar seis claves por cada uno.
