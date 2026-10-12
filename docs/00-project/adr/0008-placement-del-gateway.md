# ADR-0008: Placement de despliegue — el gateway corre en el servidor propio

* **Estado:** accepted
* **Fecha:** 2026-10-12
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 02-design
* **Versión:** 0.1.0
* **ID:** ADR-0008
* **Supersede:** —
* **Controles OWASP afectados:** A02 (configuración del host y del contenedor), A03 (imagen y pipeline)

## Contexto

El gateway es un componente de tipo C: una API contenedorizada, con runtime propio y conexiones salientes a
MongoDB Atlas y a RabbitMQ. El árbol de decisión del estándar lleva ese tipo a un servicio de contenedores
gestionado.

El punto de partida, sin embargo, es otro: ya existe un servidor propio, `midgard`, con el despliegue continuo
montado (receptor de webhooks de GitHub), un túnel de Cloudflare para la zona y el broker Hermod. El servicio está
en fase de un solo operador y no tiene clientes externos.

## Decisión

**El gateway se despliega en `midgard` con Docker Compose**, escuchando solo en loopback, con un tope de 512 MB de
RAM y 1 CPU, y publicado por el túnel de Cloudflare existente en el hostname del servicio.

**CD: GitHub Actions y el receptor de webhooks.** El workflow `build` ejecuta las pruebas y publica la imagen
`sha-<7>` en GHCR al llegar a `main`; el receptor la descarga, levanta el compose, comprueba `/health` y vuelve al
tag anterior si falla.

No se calcula la matriz de rendimiento por dólar. El estándar la exige con dos o más candidatos viables o con un
coste superior a 50 dólares al mes; aquí el candidato usa hardware y servicios que ya existen, con coste marginal
nulo, y aplica la regla de proporcionalidad.

## Alternativas consideradas

| Opción | Pros | Contras | Riesgo de seguridad |
|---|---|---|---|
| **Servidor propio con el receptor** | Coste marginal nulo; el pipeline, el túnel y el broker ya existen; los datos del broker no salen de casa | Un solo equipo, sin UPS, que además enruta la red; sin escalado | El host es compartido con otros servicios |
| Contenedores gestionados en la nube | Disponibilidad y escalado sin operar un host | Coste mensual fijo; habría que mover o exponer el broker; otro pipeline | Más superficie en la nube, menos en casa |
| Funciones sin servidor | Pago por uso | El gateway mantiene conexiones a MongoDB y a RabbitMQ y arranca lento | Sin ventaja para este componente |

## Consecuencias

- Positivas: se despliega con lo que ya hay y con el mismo flujo que el resto de aplicaciones del servidor.
- Negativas / deuda asumida:
  - **Disponibilidad sin garantía.** El servidor no tiene UPS: en septiembre de 2026 estuvo 29 horas apagado por
    un corte de luz. Por eso no se compromete ningún SLO (RNF07).
  - Docker no siempre relanza un contenedor tras un apagado brusco; falta una unidad de arranque para el gateway
    (RNF06).
  - El procesador es de dos núcleos y se comparte con el enrutamiento de la red.
- Impacto en threat model: el host compartido y el fichero `.env` del servidor entran en el modelo (T15).

## Condiciones de revisión

Esta decisión se revisa, con la matriz completa y precios verificados, cuando ocurra cualquiera de estas:

- Se admite al primer cliente externo.
- Se compromete un SLO de disponibilidad.
- Meta deshabilita el webhook de algún bot tras una caída del servidor.
- El gateway alcanza su tope de memoria o de CPU en operación normal.
