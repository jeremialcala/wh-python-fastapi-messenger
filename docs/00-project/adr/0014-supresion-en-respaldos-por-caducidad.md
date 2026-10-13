# ADR-0014: En los respaldos, la supresión se cumple por caducidad, con 365 días de retención

* **Estado:** accepted
* **Fecha:** 2026-10-13
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 02-design
* **Versión:** 0.1.0
* **ID:** ADR-0014
* **Supersede:** — (corrige el apartado "Borrado" de [ADR-0010](0010-clave-de-cifrado-de-datos-por-cliente.md))
* **Controles OWASP afectados:** A04 (retención y supresión de datos cifrados), A09 (constancia de lo suprimido)

Aceptada el 2026-10-13.

## Contexto

[ADR-0010](0010-clave-de-cifrado-de-datos-por-cliente.md) contaba con que destruir la clave de datos de un cliente
dejara ilegibles sus datos también en los respaldos, y con eso daba por cumplida la baja de un cliente (RF10).

Al construir la baja se comprobó que no es así (hallazgo H11 del
[threat model](../../02-design/threat-model.md)):

- La clave de datos envuelta se guarda en el registro del cliente, en la misma base que sus datos. Un respaldo
  anterior a la baja contiene las dos cosas.
- La clave maestra de Andvari es una sola, derivada por cliente
  ([ADR-0013](0013-openbao-como-gestor-de-secretos.md)). No se puede destruir la de un cliente, así que la clave
  envuelta de un respaldo se sigue abriendo.
- Nombres, identificador de Messenger, reglas e intents no están cifrados: en un respaldo se leen sin clave.

Quedaban dos caminos: una clave por cliente en Andvari que se pueda destruir, o aceptar que lo borrado desaparezca
de los respaldos cuando estos caducan.

Sobre los respaldos de Atlas, consultado el 2026-10-13 en su documentación:

- La retención no la fija el proveedor: se define en la política de respaldo, elemento a elemento, con una unidad
  y un valor ([`AtlasBackupPolicy`](https://www.mongodb.com/es/docs/atlas/operator/current/atlasbackuppolicy-custom-resource/)).
- Una política propia solo existe en clústeres `M10` o superiores. Un clúster Flex guarda las 8 últimas copias
  diarias, sin configuración posible, y un clúster gratuito no tiene respaldos
  ([Flex](https://www.mongodb.com/docs/atlas/backup/cloud-backup/flex-cluster-backup/),
  [visión general](https://www.mongodb.com/docs/atlas/backup/cloud-backup/overview/)).

## Decisión

**La supresión en los respaldos se cumple por caducidad, y la retención estándar de los respaldos de la base es de
365 días.**

1. Borrar un contacto, un bot o un cliente lo quita de la base en uso en el momento (RF09, RF10). De los respaldos
   desaparece cuando caduca el último que lo contiene: **365 días después del borrado, como mucho**.
2. Ningún respaldo de la base se conserva más de 365 días. Es un máximo de la plataforma, igual para todos los
   clientes: los respaldos son del clúster entero, así que un cliente no puede acortarlo para sí.
3. La clave maestra de Andvari sigue siendo una, derivada por cliente. No se añade una clave por cliente que se
   pueda destruir: ADR-0013 queda como está.
4. Mientras un respaldo exista, lo que contiene de un cliente dado de baja se trata como fuera de uso: no se
   consulta ni se restaura para ese cliente.
5. Si se restaura un respaldo, hay que repetir los borrados hechos después de la fecha de ese respaldo.

## Alternativas consideradas

| Opción | Pros | Contras | Riesgo de seguridad |
|---|---|---|---|
| **Caducidad de los respaldos, 365 días** | No cambia ADR-0013 ni la política del gateway en Andvari; nada nuevo que construir para la clave; el gateway no puede destruir claves | La supresión tarda hasta 365 días en completarse; depende de configurar bien la retención y de repetir los borrados tras una restauración | Un respaldo anterior a la baja sigue siendo legible, con acceso al respaldo y a Andvari, hasta que caduca |
| Una clave por cliente en Andvari que se pueda destruir | Los datos cifrados de un cliente quedan ilegibles en todos los respaldos en el momento de la baja | Cambia ADR-0013 y da a alguien el poder de borrar claves; no cubre lo que no está cifrado, que seguiría legible en los respaldos; los respaldos del propio Andvari conservarían la clave | Quien pueda borrar claves puede dejar ilegibles los datos de un cliente activo |
| Guardar la clave envuelta fuera de la base | Un respaldo de la base ya no la contiene | Otro almacén que respaldar y mantener consistente con la base; mismo límite con lo no cifrado | El de la opción anterior, si ese almacén permite borrar |
| Respaldos de retención corta (días) | La supresión se completa pronto | Menos margen para recuperarse de un borrado o una corrupción que se detecte tarde | El menor para la supresión, el mayor para la disponibilidad |

## Consecuencias

- Positivas:
  - La supresión tiene un plazo definido también en los respaldos, que antes estaba sin fijar.
  - El diseño de claves no cambia, y el gateway sigue sin poder destruir ninguna.
- Negativas / deuda asumida:
  - **Una supresión no es completa hasta 365 días después.** Hay que decírselo así a cada cliente en el contrato
    de encargo, porque es él quien responde ante el interesado.
  - **Sumado a los 12 meses sin actividad de un contacto, sus datos pueden existir hasta 24 meses** después de
    su último mensaje: 12 en la base y 12 más en respaldos.
  - **Restaurar un respaldo devuelve lo borrado.** Para repetir los borrados hace falta un registro de qué se
    borró y cuándo, que dure al menos 365 días. Hoy solo queda una línea en el log del contenedor, que Docker
    rota. Ese registro no está construido.
  - **La retención hay que configurarla y comprobarla en Atlas.** No consta el plan del clúster. Si no es `M10`
    o superior, los 365 días no se pueden configurar: en un clúster Flex la retención real serían 8 días, y en
    uno gratuito no habría respaldo alguno.
  - Quien tenga acceso a los respaldos y a Andvari puede leer durante ese plazo los datos de un cliente dado de
    baja. El acceso a los respaldos en Atlas tiene que estar restringido.
- Impacto en threat model: la amenaza T17 pasa a controlarse con la caducidad de los respaldos, no con la
  destrucción de la clave. El hallazgo H11 queda aceptado con esta decisión.

## Condiciones de revisión

- Un cliente, o la normativa que le aplique, exige un plazo de supresión menor.
- Cambia el plan del clúster o el proveedor de la base.
- Se designa un delegado de protección de datos: el plazo debe pasar por su revisión.

## Abierto

- **Configurar y comprobar la política de respaldo en Atlas**, y con ella el plan y la región del clúster, que
  siguen sin constar en la [clasificación de datos](../data-classification.md).
- **El registro de supresiones**, para repetirlas tras una restauración.
- **El procedimiento de restauración**, que debe incluir ese paso.
