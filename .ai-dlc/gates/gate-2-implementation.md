# Gate 2 — Implementación (cierre de Fase 03)

- [ ] SAST sin findings críticos/altos
- [ ] Dependencias verificadas (SCA) — sin deps alucinadas ni vulnerables (A03)
- [ ] Cobertura ≥ 80% branch
- [ ] Dual review completado (humano + IA)
- [ ] Sin secretos en el código

## Estado (2026-10-12): en curso

| Criterio | Estado | Evidencia |
|---|---|---|
| SAST sin hallazgos críticos o altos | Gate activo | Workflow `Seguridad`, trabajo `sast`: CodeQL sobre todo el código, también en los pull requests, y el build se rompe con cualquier hallazgo de seguridad alto o crítico (`security-severity` ≥ 7,0). Primer análisis completo: 92 resultados; uno alto, que era un falso positivo por el nombre de una constante y ya no aparece; 28 medios de `py/log-injection`, abiertos; y 63 de calidad |
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

### Pendiente que deja el primer análisis estático

- 28 hallazgos medios de `py/log-injection` en `app.py` y los controladores: valores de la petición escritos en el
  log tal cual. No rompen el build porque están por debajo del umbral, pero se cierran con el trabajo de logs sin
  datos personales.

## Heredado del Gate 1

- Los siete trabajos de la sección "Brecha entre lo construido y el diseño" de
  [`architecture.md`](../../docs/02-design/architecture.md), en el orden que marca el threat model.
- Los hallazgos H2 a H6 de [`threat-model.md`](../../docs/02-design/threat-model.md). H1, los valores por defecto
  que se calculaban al importar, está corregido.
- Si cambia la API o el mensaje de la cola, los contratos de `docs/02-design/contracts/` cambian con ellos: las
  pruebas de `tests/contract` lo exigen.
