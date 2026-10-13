# Cifrado de los datos de cada cliente: cómo funciona y cómo se opera

* **Estado:** review
* **Fecha:** 2026-10-12
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 03-implementation
* **Versión:** 0.1.0

Los números de teléfono y las credenciales de Meta se guardan cifrados con una clave propia de cada cliente. Las
decisiones están en [ADR-0010](../00-project/adr/0010-clave-de-cifrado-de-datos-por-cliente.md) y
[ADR-0013](../00-project/adr/0013-openbao-como-gestor-de-secretos.md); esto es cómo quedó construido.

## Qué se cifra

| Dato | Campo | Cómo se busca |
|---|---|---|
| Número del contacto | `Contact.waId` | Por su índice ciego, `Contact.waIdIndex` |
| Número del bot y su identificador en Meta | `ChatbotPhone.phoneNumber`, `phoneId` | No se busca por él |
| Tokens de Meta y App Secret | `ChatBot.facebookToken`, `whatsappToken`, `appSecret` | No se buscan |
| Token de verificación del webhook | `ChatBot.verifyToken` | No se busca |

**No se cifran** el nombre del contacto ni su identificador de Messenger (`fbId`): la
[clasificación de datos](../00-project/data-classification.md) les pide control de acceso, no cifrado. Si se cifra
también el identificador de Messenger sigue abierto en ADR-0010.

**El mensaje que va a la cola sí lleva el número**, porque el motor de respuestas lo necesita para contestar. Lo
que no está en claro es lo guardado, no lo que está en tránsito.

## Las claves

| Clave | Dónde vive | Quién la ve |
|---|---|---|
| Clave maestra | En Andvari (OpenBao), motor Transit. No se puede exportar | Nadie. El gateway le pide a Andvari que la use |
| Clave de datos de un cliente | En el registro del cliente, **envuelta** por la clave maestra | El gateway, abierta y en memoria, cinco minutos como máximo |

- La clave de datos de un cliente se crea la primera vez que hace falta.
- La clave maestra se deriva por cliente: una clave envuelta copiada al registro de otro cliente no se abre.
- Cada valor cifrado va atado a su cliente y a su campo. Copiado a otro campo, o al bot de otro cliente, no se
  abre: quien pueda escribir en la base no puede darle a un bot el App Secret de otro.
- Un valor que no es un cifrado válido **nunca se devuelve tal cual**: ni lo que quedó en claro, ni lo escrito a
  mano, ni lo manipulado.

## Lo que cambia en la API

- **Las credenciales de Meta entran y no salen.** Se cargan y se rotan con `PUT /chat/{bot_id}/credentials`
  (`facebookToken`, `whatsappToken`, `appSecret`; solo cambian las que se envían). La respuesta dice cuáles están
  cargadas, nunca su valor. Ya no se pueden escribir a mano en la base.
- `GET /chat/{bot_id}/info` deja de devolver los tokens de Meta. Devuelve el token de verificación, que el cliente
  necesita para pegarlo en Meta, y qué credenciales están cargadas.

## Cuando Andvari no responde

El servicio arranca aunque no lo alcance, y `/health` no depende de él. Mientras no responda, y pasados los cinco
minutos que una clave ya abierta sigue en memoria:

| Qué | Respuesta |
|---|---|
| Webhook de Meta | `503`. Meta reintenta: no se pierde el mensaje ni se da por buena una firma sin comprobar |
| Leer o escribir algo cifrado (crear un bot, `/info`, números, credenciales, contactos) | `503` |
| Lo que no toca nada cifrado (reglas, intents, registro de clientes, borrar contactos, bots y clientes) | Funciona |

## Puesta en marcha

En el servidor, además de lo de [autenticacion.md](autenticacion.md):

1. **Red y certificado.** El contenedor entra en la red Docker `andvari` y monta la autoridad de certificación de
   Andvari. Ya está en [`deploy/docker-compose.yml`](../../deploy/docker-compose.yml).
2. **Credencial del gateway.** El rol AppRole `gateway` existe en Andvari, sin credencial emitida. Se emite una y se
   guarda en `keys/andvari-secret-id`, legible solo por el usuario `10001`. El `role_id` va en el `.env` como
   `ANDVARI_ROLE_ID`. La credencial se lee del fichero cada vez que el gateway entra, así que se rota
   sustituyendo el fichero, sin reiniciar.
3. **Datos anteriores.** En este orden, y cada una informa antes de escribir:

   ```bash
   python -m migrations.assign_operator_client --apply   # da dueño a lo que no lo tiene
   python -m migrations.encrypt_client_data --apply      # cifra lo que estaba en claro
   ```

   Hasta que se ejecutan, un bot con secretos en claro responde `404` en el webhook.

Fuera de desarrollo, `ANDVARI_ADDR` tiene que ser `https`: el servicio no arranca con otra cosa.

## Antes de cifrar datos reales

Perder la clave maestra es perder todo lo cifrado con ella. Antes de ejecutar la migración contra datos reales
tiene que existir, fuera del servidor, una copia del almacenamiento de Andvari y de su clave de sello, y la clave
de recuperación tiene que estar a buen recaudo.

## Lo que no hace todavía

- **Dejar ilegible en los respaldos lo de un cliente dado de baja.** La baja borra su clave de datos envuelta junto con
  sus datos, pero un respaldo anterior la contiene y Andvari la sigue abriendo: ver
  [exportar-y-borrar.md](exportar-y-borrar.md).
- **Rotar la clave de datos de un cliente.** Rotar la clave maestra en Andvari sí es posible: lo ya envuelto se
  sigue abriendo.
- **El motor de respuestas no obtiene los tokens.** Están cifrados y fuera de la API, pero el cliente de servicio
  que se los entregaría no está construido.
- **El cuerpo del mensaje en la cola va en claro**, número incluido. Su cifrado es una segunda fase de ADR-0011.
