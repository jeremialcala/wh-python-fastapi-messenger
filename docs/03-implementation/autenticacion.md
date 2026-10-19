# Autenticación: cómo se llama al servicio y cómo se opera

* **Estado:** review
* **Fecha:** 2026-10-12
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 03-implementation
* **Versión:** 0.1.0

Todo endpoint que no sea el webhook de Meta ni `/health` pide un token en la cabecera
`Authorization: Bearer <token>`. El token es un JWT firmado por el cliente, metido dentro de un JWE cifrado para el
gateway. Las decisiones están en [ADR-0004](../00-project/adr/0004-firma-en-el-webhook-jwe-en-el-resto.md),
[ADR-0005](../00-project/adr/0005-jwt-firmado-por-el-cliente-dentro-del-jwe.md) y
[ADR-0009](../00-project/adr/0009-parametros-del-token-de-autenticacion.md); esto es cómo se usan.

## Las claves que intervienen

| Clave | De quién | Dónde vive la parte privada | Para qué |
|---|---|---|---|
| Par P-256 de firma | De cada cliente, operador incluido | Solo en el cliente | Demuestra quién envía. El gateway guarda la parte pública |
| Par RSA de cifrado | Del gateway | En un fichero del servidor, fuera del repositorio y de la imagen | Que solo el gateway lea el token |

El gateway no guarda ningún secreto de un cliente: si alguien se lleva la base, no se lleva con qué hacerse pasar
por nadie.

## Para un cliente

### El token

1. **Firmar** un JWT con la clave privada, algoritmo `ES256`. La cabecera lleva el `kid` que devolvió el registro.
2. **Cifrar** ese JWT como JWE compacto para una clave pública del gateway: `RSA-OAEP-256` con `A256CBC-HS512`. La
   cabecera lleva `cty: JWT` y el `kid` de la clave del gateway.

| Campo del JWT | Valor |
|---|---|
| `iss` | El identificador del cliente (`uuid`) |
| `aud` | La audiencia del gateway, la que devolvió el registro |
| `iat`, `exp` | `exp` como máximo 60 segundos después de `iat` |
| `jti` | Un identificador nuevo en cada token |

Un token vale **una vez y 60 segundos**: hay que construir uno por petición. Cualquier otro algoritmo se rechaza.
Un token rechazado recibe siempre el mismo `401`, sin decir el motivo; el motivo queda en el log del gateway.

### Con el cliente de referencia

`src/ops/client.py` hace esos dos pasos y no necesita nada del servicio. Sirve tal cual o como ejemplo para
hacerlo con otra librería JOSE.

```bash
# Una vez: crea la clave. Escribe la privada en el fichero e imprime la pública, que es la que se registra.
python -m ops.client new-key mi-clave.json

# En cada petición: un token nuevo.
curl -H "Authorization: Bearer $(python -m ops.client token mi-clave.json <uuid del cliente> <audiencia> gateway-publicas.json)" \
     https://<gateway>/keys
```

`gateway-publicas.json` es lo que el registro devolvió en `gateway.keys`, guardado como `{"keys": [...]}`. Los
comandos se ejecutan desde `src/` de este repositorio con `jwcrypto` instalado, o con la imagen del servicio.

### Rotar la clave propia

Un cliente puede tener dos claves a la vez, para cambiar sin corte:

1. `POST /keys` con la clave pública nueva y la **prueba de que tiene su parte privada**: un JWT que firma la clave
   nueva (`typ: key-proof+jwt`, `ES256`), con el mismo `iss` y `aud` que el token y el `jti` del token de esa misma
   petición. Vale una vez y 60 segundos, como el token. Sin ella, o si no casa, la respuesta es `422`
   `INVALID_KEY_PROOF` y la clave no se añade.
2. Empezar a firmar con la nueva.
3. `DELETE /keys/{kid}` con el `kid` de la antigua.

Con el cliente de referencia, el paso 1 es:

```bash
python -m ops.client new-key clave-nueva.json
python -m ops.client add-key mi-clave.json clave-nueva.json <uuid del cliente> <audiencia> gateway-publicas.json > alta.json
curl -H "Authorization: Bearer $(jq -r .token alta.json)" -H "Content-Type: application/json" \
     -d "$(jq -c .body alta.json)" https://<gateway>/keys
```

La prueba impide registrar una clave con la que nadie puede firmar, pero **no frena a quien robó una clave**: se
hace una propia y prueba que la tiene. Contra eso está la revocación de la tabla de abajo.

No se puede borrar la última clave: el cliente se quedaría fuera. Si pierde su clave, es el operador quien le
registra otra.

## Para el operador

Los comandos se ejecutan con la imagen del servicio, en el servidor.

### Puesta en marcha

```bash
# 1. El par de claves del gateway. La privada se escribe en el fichero, solo para su dueño, y no se imprime.
docker run --rm -v /srv/apps/bots-gateway/keys:/keys <imagen> python -m ops.gateway_key generate /keys/gateway-keys.json

# 2. En el .env: la ruta del fichero dentro del contenedor y la audiencia que pondrán los clientes en sus tokens.
#    GATEWAY_KEYS_FILE=/run/gateway/gateway-keys.json
#    GATEWAY_AUDIENCE=https://bots.example.com

# 3. La primera clave del operador. Se crea en la máquina del operador, y al servidor solo va la parte pública.
python -m ops.client new-key operador.json > operador-publica.json
docker compose run --rm -v $PWD/operador-publica.json:/tmp/operador.json:ro gateway python -m ops.operator_key /tmp/operador.json
```

Sin el fichero de claves, o con uno que no puede usar, **el servicio no arranca**. El contenedor corre con el
usuario `10001`, que tiene que poder leer el fichero: `chown 10001` y `chmod 400`.

El paso 3 existe porque todos los endpoints piden un token y nadie puede firmar uno antes de tener una clave
registrada. Devuelve el `uuid` del cliente del operador y el `kid` de su clave.

### Alta de un cliente

El cliente crea su clave y envía la parte pública. El operador la registra:

```
POST /clients
{"name": "acme", "signingKey": {"kty": "EC", "crv": "P-256", "x": "...", "y": "..."}}
```

La respuesta lleva lo que el cliente necesita: su `uuid`, el `kid` de su clave, la audiencia y las claves públicas
del gateway. Solo se acepta una clave pública P-256; una privada se rechaza y no se guarda.

### Revocar y recuperar

| Situación | Qué hacer |
|---|---|
| Una clave de un cliente está comprometida | Quitar **todas** las claves que el cliente no reconozca, no solo esa: `GET /clients` las lista en `keys` de cada cliente, y cada una se quita con `DELETE /clients/{client_id}/keys/{kid}`, que deja de valer en el acto. Quien tenía la clave pudo añadir otra suya con ella, con su prueba, y quitar la legítima; cada alta de una clave deja una línea de aviso en el log con su `kid`, y cada baja otra. Si el cliente se queda sin ninguna, se le registra la nueva como en la fila siguiente |
| Un cliente perdió su clave | `POST /clients/{client_id}/keys` con la pública nueva |
| El operador perdió la suya | Repetir el paso 3 de la puesta en marcha |

El operador registra clientes, pero no entra en sus datos: en las rutas de los chatbots es un cliente más y solo
alcanza los suyos.

### Dar paso al motor de respuestas

El motor no tiene una credencial para todo: tiene una clave por cliente, y con ella solo alcanza los bots de ese
cliente ([ADR-0016](../00-project/adr/0016-credencial-del-motor-por-cliente.md)). Para cada cliente al que vaya a
servir:

1. El motor crea una clave para ese cliente, igual que un cliente crea la suya, y se queda la parte privada.
2. El operador registra la parte pública bajo el cliente:

   ```
   POST /clients/{client_id}/service-keys
   {"signingKey": {"kty": "EC", "crv": "P-256", "x": "...", "y": "..."}}
   ```

3. El motor firma sus tokens con esa clave y pone como emisor el identificador del cliente. El formato es el
   mismo de cualquier cliente. Qué cliente es lo dice cada mensaje de la cola, en `clientId`.

Con esa clave el motor alcanza cinco rutas, y cualquier otra le responde `403`:

| Ruta | Qué obtiene |
|---|---|
| `GET /chat/{bot_id}/rules` | El system prompt del bot |
| `GET /chat/{bot_id}/tools` | Sus herramientas |
| `GET /chat/{bot_id}/tokens` | Los tokens de Meta con los que envía la respuesta |
| `GET /chat/{bot_id}/contacts/{contact_id}/turns` | Las 10 últimas vueltas de una conversación, para que el coordinador rehaga su contexto cuando no lo tiene (RF15) |
| `GET /gateway/keys` | Las claves públicas del gateway, para seguir su rotación |

- **Los tokens solo los recibe el motor.** El cliente no los recupera con su propia clave, ni el operador con la
  suya. No incluyen el App Secret ni el token de verificación.
- **Cada entrega de tokens deja una línea en el log**, también en `production`: el bot, el cliente y la clave.
- **Las vueltas, igual.** Las recibe solo el motor; el cliente tiene para eso la exportación del contacto. Cada
  entrega deja en el log el contacto, el bot, el cliente, la clave y cuántos mensajes fueron, nunca su texto. Una
  vuelta empieza en un mensaje del contacto, y llegan desde el décimo por el final hasta el último, en los dos
  sentidos y en orden.
  - Hasta I6, las vueltas las alcanza cualquier clave del motor.
  - Con I6 ([ADR-0022](../00-project/adr/0022-una-credencial-por-worker.md)) quedan solo para la del coordinador.
- **Admite dos claves por cliente**, para rotar sin corte: se registra la nueva, el motor pasa a usarla y se borra
  la antigua con `DELETE /clients/{client_id}/service-keys/{kid}`. Borrarla le quita el acceso en el acto.
- **El cliente ve qué claves del motor alcanzan sus bots**: `GET /keys` las lista en `serviceKeys`.
- **Una clave es del cliente o del motor, nunca de los dos.** Registrar la misma en las dos listas responde `409`.

### Rotar el par del gateway

1. `python -m ops.gateway_key generate <fichero>` añade un par nuevo; el anterior sigue valiendo.
2. Reiniciar el servicio, que lee el fichero al arrancar.
3. Los clientes piden las claves con `GET /gateway/keys` y pasan a cifrar con la nueva, la última de la lista.
4. Cuando ya nadie cifra con la antigua: `python -m ops.gateway_key drop <fichero> <kid>` y otro reinicio.

## Lo que no hace todavía

- **El motor de respuestas no lo usa todavía.** El gateway ya le da paso con una clave por cliente; pedir la
  configuración y los tokens es trabajo de su repositorio.
- **No hay límite de tasa.** Los intentos fallidos se registran, pero nada los frena; es RS10, en el borde.
- **Un cliente no se puede desactivar por la API.** Revocar sus claves lo deja fuera; el estado del cliente solo se
  cambia en la base.
- **La clave privada del gateway es un fichero.** Pasará a Andvari cuando el gateway se integre con él para el
  cifrado de datos (ADR-0013).
