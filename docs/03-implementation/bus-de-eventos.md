# Bus de eventos: cómo publica el gateway en Bifröst

* **Estado:** review
* **Fecha:** 2026-10-19
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 03-implementation
* **Versión:** 0.1.0
* **ADR:** [ADR-0019](../00-project/adr/0019-nats-jetstream-como-bus.md), [ADR-0021](../00-project/adr/0021-el-webhook-solo-publica.md)
* **Incremento:** I2 del [plan de la topología de workers](../00-project/plan-topologia-de-workers.md) (R2)

El gateway publica eventos con un puerto, `EventPublisher` (`src/bus`), que no dice qué bus hay detrás. Su adaptador
es `NatsPublisher`, sobre NATS JetStream, es decir Bifröst.

**Todavía no publica nadie.** El webhook sigue mandando un sobre por mensaje a la cola `llm` de Hermod. En I3 pasa a
publicar en `webhook.meta.<canal>` un evento por notificación. Hermod se retira cuando el motor lea de Bifröst.

## Qué garantiza

- **Una conexión por proceso.** Se abre la primera vez que hace falta y la mantiene el cliente: si se cae, reconecta
  solo, sin límite de intentos. Con RabbitMQ había una conexión por mensaje.
- **El evento lleva `Nats-Msg-Id`.** Si el mismo identificador se publica otra vez dentro de la ventana del stream (2
  minutos en `WEBHOOK`), el stream no lo guarda dos veces y la respuesta dice que era un duplicado.
- **Se espera el acuse del stream** (`PubAck`), con 3 segundos de plazo. Bifröst hace `fsync` antes de darlo
  (`sync_interval: always`).
- **Un fallo es siempre `BusUnavailable`.** Lo provocan: no llegar al bus, una contraseña que no vale, un sujeto que
  el usuario no puede publicar, un sujeto sin stream, el búfer lleno mientras reconecta o un acuse que no llega a
  tiempo. Quien llama responde `503`, y el mensaje de la excepción es solo el tipo de fallo: el texto de NATS puede
  llevar la dirección.
- **Un bus caído no hace esperar.** Tras un intento fallido de conectar, durante 1 segundo no se vuelve a intentar.
  Cada petición recibe `BusUnavailable` al momento.

## Configuración

Las variables se llaman igual que en el fichero que Bifröst escribe para cada servicio,
`/srv/infra/bifrost/credenciales/<servicio>.env`. Ese fichero se le puede dar al contenedor tal cual:

| Variable | Qué es |
|---|---|
| `NATS_URL` | `tls://bifrost:4222`. Sin ella no hay publicador. Fuera de desarrollo tiene que ser `tls://`: con otra cosa el servicio no arranca |
| `NATS_USER`, `NATS_PASSWORD` | El usuario del servicio. El del webhook solo puede publicar en `webhook.meta.>` |
| `NATS_CA` | La CA de Bifröst, montada en `/run/bifrost/ca.crt` (en el servidor, `/srv/infra/bifrost/tls/ca.crt`) |
| `NATS_INBOX_PREFIX` | `_INBOX_<servicio>`. Bifröst solo deja a cada servicio leer sus propias respuestas: con el prefijo por defecto, el acuse no llega nunca |

El contenedor tiene que estar en la red Docker externa `bifrost`. Eso entra en `deploy/docker-compose.yml` con I3,
cuando el webhook empiece a publicar.

## Medido contra Bifröst (2026-10-19)

En midgard, con la imagen de esta rama (`i2-fcc3764`), el usuario `webhook` y TLS. Fueron 300 eventos de 1 KB
seguidos por la misma conexión, al stream `WEBHOOK`, en el SSD:

| Medida | Valor |
|---|---|
| Primera publicación, abriendo la conexión con TLS | 139 ms |
| Cada evento después | 2,1 ms de mediana; p95 2,9 ms; p99 3,8 ms; máximo 13,8 ms |
| El mismo identificador otra vez | No se guarda; la respuesta lo marca como duplicado |
| Un sujeto que el webhook no puede publicar (`gateway.message.…`) | `BusUnavailable` al vencer el plazo |

Con Hermod y una conexión por mensaje, publicar costaba 8,3 ms de mediana ([I1](../04-testing/medicion-webhook-i1.md)).
La primera publicación de cada proceso paga la conexión. Los 301 eventos de la prueba se purgaron del stream al
terminar.

## Trampas encontradas

- **Con reconexión infinita, `nats-py` también reintenta para siempre la primera conexión**, y eso incluye una
  contraseña equivocada: la petición se queda colgada. Por eso la primera conexión tiene un plazo propio
  (`CONNECT_TIMEOUT` + 1 s), y el intento fallido se cierra para que no siga reintentando por detrás.
- **Vaciar un stream no borra su ventana de duplicados.** Un identificador publicado antes de la purga se sigue
  descartando hasta que pasa la ventana. Hay una prueba que lo fija. Si se purga `WEBHOOK` para reprocesar algo,
  ese algo no puede volver a entrar con el mismo `Nats-Msg-Id` hasta pasados 2 minutos.
- **Una conexión y su cerrojo pertenecen al bucle de eventos que los creó.** Si cambia el bucle (en las pruebas,
  cada `asyncio.run`), el publicador abre otra conexión en vez de usar la anterior.

## Pruebas

- `tests/unit/test_event_bus.py`: cuándo conecta, cuándo no reintenta y en qué acaba cada fallo, con un cliente falso.
- `tests/integration/test_nats_publisher.py`: contra un NATS 2.14.8 real configurado como Bifröst
  (`tests/integration/nats-test.conf`), con el usuario del webhook. Comprueba qué guarda el stream, los duplicados,
  el mensaje de 3 MB, los permisos, el prefijo de buzón y que hay una sola conexión, contada en `/connz`. En el CI
  corren siempre (`NATS_TEST_REQUIRED`).

  Para correrlas en local:

  ```bash
  docker run --rm -p 127.0.0.1:24222:4222 -p 127.0.0.1:28222:8222 \
      -v "$PWD/tests/integration/nats-test.conf:/etc/nats/test.conf:ro" nats:2.14.8-alpine -c /etc/nats/test.conf
  NATS_TEST_ADDR=127.0.0.1:24222 NATS_TEST_MONITOR=127.0.0.1:28222 pytest tests/integration/test_nats_publisher.py
  ```
