# 05 — Despliegue (Gate 4)

* **Estado:** draft
* **Fecha:** 2026-10-20
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 05-deployment
* **Versión:** 0.1.0

El esqueleto de Hive en midgard (E7 del [plan](../00-project/plan-de-los-workers.md)). Es la instancia de prueba: las
imágenes se construyen en midgard desde `develop`, sin pasar por `main` ni por el despliegue continuo (decisión de
Jeremi del 2026-10-20). El Gate 4, con el pipeline, sus gates y el SBOM, queda para cuando el motor llegue a `main`.

## Qué corre

| Proyecto compose | Dónde | Contenedores |
|---|---|---|
| `bots-gateway` | `/srv/apps/bots-gateway` (`deploy/docker-compose.yml` de la raíz) | `bots-webhook`, `bots-gateway`, `bots-ingest` y, con el perfil `tunel`, `hive-tunel` |
| `hive-engine` | `/srv/apps/hive-engine` (`engine/deploy/docker-compose.yml`) | `hive-classifier`, `hive-coordinator`, `hive-responder` y `hive-notifier` |

`hive-tunel` publica, desde Cloudflare (ADR-0024 del gateway):

- `https://hive-webhook.higerotech.com` hacia `http://bots-webhook:5002`;
- `https://hive-api.higerotech.com` hacia `http://bots-gateway:5002`.

Bifröst, Andvari y Saga los ponen sus repositorios. Los workers llegan a ellos y a la API del gateway por las redes
externas `bifrost`, `andvari` y `yggdrasil_saga`.

## Lo que necesita cada worker

| Worker | Bifröst | Andvari | Además |
|---|---|---|---|
| Clasificador | `credenciales/classifier.env` | Rol `motor-classifier`: su clave de Anthropic | — |
| Coordinador | `credenciales/coordinator.env` | Rol `motor-coordinator`: su clave para cada cliente | La API del gateway |
| De respuesta | `credenciales/responder.env` | Rol `motor-responder`: su clave de Anthropic | — |
| Notificador | `credenciales/notifier.env` y el bucket `enviados` | Rol `motor-notifier`: su clave para cada cliente | La API del gateway y `graph.facebook.com` |

Cada cliente con bots necesita las claves del motor (`ops.engine_keys` del gateway). La instancia de medición ya las
tiene para su cliente.

## Puesta en marcha

1. **Las imágenes**, en midgard, desde `develop`:

   ```bash
   git archive develop | ssh midgard 'rm -rf ~/hive-build && mkdir ~/hive-build && tar -x -C ~/hive-build'
   docker build -t ghcr.io/jeremialcala/wh-python-fastapi-messenger:e7-<sha> ~/hive-build
   docker build -f ~/hive-build/engine/Dockerfile -t ghcr.io/jeremialcala/chatbot-engine:e7-<sha> ~/hive-build
   ```
2. **Andvari**, con un token raíz temporal y en una terminal propia. Pide la clave de recuperación y después las dos
   claves de Anthropic, sin eco:

   ```bash
   sudo bash raiz-temporal.sh bash -c 'bash motor/instalar.sh /srv/apps/bots-gateway/keys/motor-claves-secret-id \
     && bash motor/emitir-trabajadores.sh /srv/apps/hive-engine/keys \
     && bash motor/clave-anthropic.sh classifier && bash motor/clave-anthropic.sh responder'
   ```

   `motor/instalar.sh` pone al día las políticas de los workers con la ruta de su clave de Anthropic. Los `role_id`
   que imprime `emitir-trabajadores.sh` van al `.env` del motor.
3. **El gateway**, con la imagen nueva y `GATEWAY_AUDIENCE=https://hive-api.higerotech.com` en su `.env`.
4. **El motor:** `/srv/apps/hive-engine` con su `docker-compose.yml`, su `.env` (`deploy/.env.example`) y `keys/`
   (root:10001, 750) con los cuatro `secret_id` y una copia de `gateway-public.json`. Después:

   ```bash
   sudo docker compose --project-directory /srv/apps/hive-engine up -d
   ```
5. **El túnel:** se crea en Cloudflare con sus dos nombres públicos, y su token va al `.env` del gateway sin pasar por
   la pantalla ni por un argumento. Después, `COMPOSE_PROFILES=tunel` y `docker compose up -d`.
6. **El bot de prueba:**
   - se da de alta en el gateway, con sus credenciales de Meta, su número y sus reglas;
   - en Meta, la URL del webhook es `https://hive-webhook.higerotech.com/chat/{bot_id}`, con su `verifyToken`, y se
     suscribe a `messages`.

## Comprobar

- Los cuatro workers `healthy`, sin reinicios.
- Un mensaje de WhatsApp al número de prueba vuelve con su respuesta. Su traza cruza el webhook, la ingesta y los
  cuatro workers en Saga.
- El log del clasificador y del de respuesta dice los tokens de cada llamada; con ellos se mide el coste.
- El historial del gateway guarda el mensaje y la respuesta.

## Volver atrás

- **El motor:** `docker compose --project-directory /srv/apps/hive-engine down`. Lo que quede en `MOTOR` caduca en 24
  horas.
- **El gateway:** su `docker-compose.yml` y su `.env` anteriores, con la imagen anterior.
- **El túnel:** quitar `COMPOSE_PROFILES=tunel` y `docker compose up -d --remove-orphans`, o revocar el túnel en
  Cloudflare.
