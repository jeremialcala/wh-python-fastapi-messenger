# Gate 2 — Implementación (cierre de Fase 03)

- [ ] SAST sin findings críticos/altos
- [ ] Dependencias verificadas (SCA) — sin deps alucinadas ni vulnerables (A03)
- [ ] Cobertura ≥ 80% branch
- [ ] Dual review completado (humano + IA)
- [ ] Sin secretos en el código

## Estado (2026-10-12): en curso

| Criterio | Estado | Evidencia |
|---|---|---|
| SAST sin hallazgos críticos o altos | Gate activo | Workflow `Seguridad`, trabajo `sast`: CodeQL sobre todo el código, también en los pull requests, y el build se rompe con cualquier hallazgo de seguridad alto o crítico (`security-severity` ≥ 7,0) fuera del código de pruebas; los de `tests/` se informan como aviso y no bloquean (decisión del 2026-10-12). Primer análisis completo: 92 resultados; uno alto, que era un falso positivo por el nombre de una constante y ya no aparece; 28 medios de `py/log-injection`, abiertos; y 63 de calidad |
| Dependencias verificadas (SCA) | Gate activo | `requirements.lock` y `requirements-dev.lock` con hashes; trabajo `dependencias` con `pip-audit` sobre el lock. Al añadirlo: 14 vulnerabilidades conocidas con las dependencias anteriores, todas de Starlette 0.36.3, y ninguna con las nuevas |
| Cobertura ≥ 80 % por ramas | Gate activo: 86 % | El CI rompe el build por debajo del 80 %. Era del 61 % antes de las pruebas de aislamiento, que pasan por los controladores y el repositorio de verdad, contra una base en memoria |
| Dual review | Pendiente | — |
| Sin secretos en el código | Gate activo | Trabajo `secretos`: gitleaks sobre la historia completa. Al añadirlo: 56 commits, ningún hallazgo |

"Gate activo" significa que el control existe y rompe el build; la casilla se marca al cerrar el gate, con el
resto de criterios cumplidos.

### Hecho en la base

- Dependencias actualizadas: FastAPI 0.110 → 0.143 y Starlette 0.36 → 1.7. Se retiran once paquetes que el código
  no importaba.
- La imagen instala solo las dependencias de ejecución, desde el lock y verificando hashes.
- Corregido el hallazgo H1: los valores por defecto de las entidades se calculan por objeto.

### Hecho: aislamiento por cliente (ADR-0012)

- Entidad cliente, `clientId` obligatorio en chatbots, números, reglas, intents y contactos, y capa de
  repositorio (`src/repository`) por la que pasa todo acceso a esos datos.
- Lo ajeno responde `404`, igual que lo inexistente. Las pruebas recorren todas las rutas de gestión con otro
  cliente; si se quita el filtro por cliente del repositorio, fallan 31.
- Una prueba lee el código y falla si algo consulta la base fuera del repositorio.
- De paso se cierran dos accesos cruzados que ya existían entre chatbots: un intent se podía leer, cambiar o
  desactivar a través de cualquier chatbot, y se podían añadir reglas a un chatbot inexistente.
- Los datos anteriores a la existencia de clientes hay que asignárselos al del operador con
  `python -m migrations.assign_operator_client --apply`; hasta entonces esos chatbots responden `404`.

### Hecho: autenticación por cliente (ADR-0005, ADR-0009)

- Todo lo que no es el webhook ni `/health` pide un JWT firmado por el cliente dentro de un JWE cifrado para el
  gateway: un algoritmo por capa, 60 segundos como máximo y un solo uso. La clave de administración ya no
  existe.
- Registro de clientes: el operador los da de alta con su clave pública, y cada cliente rota la suya sin corte.
- El gateway no guarda secretos de los clientes, y no arranca sin su propio par de claves.
- Las pruebas usan tokens reales: cada forma de falsificar, alterar o reenviar uno acaba en el mismo `401`, y
  otra prueba comprueba qué verificación lo rechaza. Desactivando cada verificación por separado, fallan.
- Cómo se usa y cómo se opera: [`autenticacion.md`](../../docs/03-implementation/autenticacion.md).

### Hecho: cifrado por cliente (ADR-0010, ADR-0013)

- Los números de contactos y bots, los tokens de Meta, el App Secret y el token de verificación se guardan
  cifrados con una clave propia de cada cliente, que solo existe envuelta por la clave maestra de Andvari. El
  contacto se busca por un índice ciego.
- Las credenciales de Meta se cargan por la API y ya no salen por ella: `/info` deja de devolver los tokens.
- Sin Andvari, lo cifrado responde `503` y el webhook también: ni se pierde un mensaje ni se da por buena una
  firma sin comprobar.
- Las pruebas vuelcan la base y comprueban que nada de eso aparece en claro; rompiendo el cifrado de seis
  maneras distintas, fallan. El cliente del servicio de claves se prueba contra un OpenBao real, también en
  el pipeline.
- Los datos anteriores se cifran con `python -m migrations.encrypt_client_data --apply`.
- Cómo funciona y cómo se opera: [`cifrado-de-datos.md`](../../docs/03-implementation/cifrado-de-datos.md).

### Hecho: sobre versión 1 de la cola (ADR-0011)

- El gateway publica el sobre versión 1: `schemaVersion`, `messageId` con el identificador de Meta, `metadata`
  como objeto, la fecha real de creación y una caducidad de 24 horas en cada mensaje.
- Un sobre por cada mensaje de la notificación. Antes no salían todos, y el eco de Messenger no se filtraba
  (H7 y H8 del threat model).
- El contrato es [`asyncapi.yaml`](../../docs/02-design/contracts/asyncapi.yaml), y las pruebas validan contra
  él lo que el código publica. Rompiendo el cambio de dieciséis maneras, fallan en las dieciséis.
- La publicación se prueba contra un RabbitMQ real de la misma versión que Hermod, también en el pipeline: el
  broker conserva el sobre, lo descarta al caducar, y la cola la pueden declarar los dos servicios.
- Pasados al parser del motor tal como está hoy, los sobres de WhatsApp se leen; los de Messenger se rechazan y
  el bot no se conserva, que es la parte de ADR-0011 que toca en su repositorio.

### Hecho: exportar y borrar (RF08, RF09, RF10)

- Un cliente lista los contactos de un bot, encuentra a una persona en todos sus bots por número o por
  identificador de Messenger, exporta lo guardado de un contacto y lo borra.
- `DELETE /bot/{bot_id}` borra un bot con todo lo guardado para él, y `DELETE /clients/{client_id}`, solo para
  el operador, da de baja a un cliente: primero deja de entrar, después se borran sus datos y al final su
  registro, con su clave de datos envuelta. Una baja interrumpida se termina repitiendo la llamada.
- Un mensaje en camino hacia un bot que se está borrando no deja un contacto huérfano, y guardar un documento
  ya borrado no lo devuelve a la base.
- Las pruebas pasan por la aplicación con tokens reales y después leen la base entera: tras una baja, ningún
  documento nombra al cliente. Rompiendo el cambio de 43 maneras, fallan en 42; la restante no
  cambia el comportamiento.
- En local, contra un MongoDB 8.0 real y desechable, pasa la batería entera; y con tres hilos guardando contactos
  mientras otro borra el bot no queda ninguno huérfano en 150 rondas, cuando sin la comprobación quedan en 21. No
  está en el pipeline, que usa una base en memoria.
- **No alcanza a los respaldos**: un respaldo anterior a la baja contiene la clave envuelta, y Andvari la sigue
  abriendo (H11 del threat model). Una prueba lo deja escrito para que no se dé por cubierto. Aceptado el
  2026-10-13 con ADR-0014: en los respaldos la supresión se cumple por caducidad, a los 365 días como mucho.
- De paso se corrige H12: la respuesta a una petición mal formada repetía lo enviado, credenciales incluidas.
- Cómo funciona y hasta dónde llega: [`exportar-y-borrar.md`](../../docs/03-implementation/exportar-y-borrar.md).

### Hecho: logs sin datos personales, errores sin detalles y registro de supresiones (RS07, RS15, ADR-0014)

- Nada de lo que envía quien llama, ni de lo que Meta envía sobre una persona, se escribe en el log, en
  ningún nivel. Cada petición deja una línea con la ruta tal como está declarada; de un fallo se escribe su
  tipo y su línea, nunca su texto.
- Se corrige H13: el log de accesos del servidor escribía cada petición con su query string, y con ella el
  token de verificación del webhook, también en `production`. Se vio ejecutando el servicio como lo hace la
  imagen.
- Un fallo inesperado responde `500` sin su texto: las pruebas lo fuerzan en cada ruta de gestión.
- Cada borrado se apunta antes de hacerse en un registro de supresiones que vive fuera de la base, y
  `python -m migrations.replay_erasures` lo repite después de restaurar un respaldo. Si el registro no se
  puede escribir, no se borra nada.
- Las pruebas borran por la API, devuelven la base a una copia anterior y repiten los borrados.
  Rompiendo el cambio de 40 maneras, fallan en las 40.
- Queda del sexto trabajo de la brecha el esquema estricto de la notificación y el límite de tamaño (RS11).

### Pendiente que deja el primer análisis estático

- Los 28 hallazgos medios de `py/log-injection` en `app.py` y los controladores, valores de la petición escritos
  en el log tal cual, están cerrados con el trabajo de logs sin datos personales: el análisis de ese cambio no
  encuentra ninguno, y no queda ningún hallazgo de seguridad abierto. Quedan 59 de calidad.

## Heredado del Gate 1

- Los siete trabajos de la sección "Brecha entre lo construido y el diseño" de
  [`architecture.md`](../../docs/02-design/architecture.md), en el orden que marca el threat model.
- Los hallazgos abiertos de [`threat-model.md`](../../docs/02-design/threat-model.md): H3, H5 y H6; los que salieron
  al construir el sobre, H9 y H10; y lo que deja pendiente H11, aceptado con ADR-0014: configurar y comprobar en Atlas la retención de 365 días, y el
  registro de supresiones. H1, H2, H4, H7, H8 y H12 están corregidos.
- Si cambia la API o el mensaje de la cola, los contratos de `docs/02-design/contracts/` cambian con ellos: las
  pruebas de `tests/contract` lo exigen.
