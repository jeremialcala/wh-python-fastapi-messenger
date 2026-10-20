# -*- coding: utf-8 -*-
"""
    El notificador (E6 de engine/docs/00-project/plan-de-los-workers.md). Lee cada respuesta del stream `MOTOR` con el
    consumidor `notifier`, se la envía a la persona por WhatsApp y publica lo enviado en `engine.reply.sent.{botId}`
    (stream `RESPUESTAS`), que la ingesta del gateway guarda en el historial (contrato v2, `RespuestaEnviada`).

        python -m src.workers.notifier

    - **Antes de enviar, mira si ya lo envió**, en el bucket `enviados` de Bifröst. Si Meta aceptó una respuesta y
      algo falló antes de confirmar (publicar en RESPUESTAS, un reinicio), Bifröst lo entrega otra vez: entonces no se
      envía de nuevo, se publica lo que ya salió (ADR-0008, punto 4).
    - **El token de WhatsApp del bot lo pide al gateway**, con su clave para el cliente dueño del bot: es el único
      worker que lo recibe. Si Meta lo rechaza, lo pide otra vez.
    - **Lo que puede ir más tarde** (Meta saturado, un límite de envíos, el gateway o Bifröst caídos) queda en espera, y
      Bifröst lo entrega otra vez. En la última entrega, no hay nada más que hacer: se descarta y queda en el log.
    - **Lo que no irá nunca** (el destinatario no está en WhatsApp, pasaron las 24 horas de la ventana de atención, el
      bot ya no existe) se descarta, con el código de Meta en el log.
    - **Messenger e Instagram llegan en el E10**: hasta entonces su respuesta se descarta.

    El log no lleva el texto, el número, el token ni los ids de los mensajes.
"""
import asyncio
import logging
from datetime import datetime, timezone

from shared import bus, tracing
from shared.contract import SCHEMA_VERSION, SentReply, reply_subject
from shared.engine_key_store import EngineKeyStore
from shared.workers import Worker
from src.domain.models.sobre import MensajeRespondido
from src.domain.ports.envio import (
    CanalDeMeta, Envio, Enviados, EnvioFallido, EnvioRechazado, RegistroNoDisponible, TokenRechazado, TokensDelBot,
)
from src.domain.ports.fuente_del_bot import FuenteNoDisponible, NoEncontrado
from src.infrastructure.bifrost import EnviadosEnBifrost
from src.infrastructure.gateway import ApiDelGateway
from src.infrastructure.gateway.api import clave_publica_del_gateway
from src.infrastructure.meta import WhatsAppCloud
from src.workers.runtime import Descartado, Resultado, ejecutar, entregas, leer_del_motor, publicador
from src.workers.settings import NotifierSettings

log = logging.getLogger(__name__)

NOMBRE = Worker.NOTIFIER.value
STREAM, CONSUMIDOR = "MOTOR", NOMBRE


class _Esperar(Exception):
    """Algo que hace falta no está: el mensaje queda en espera. Lleva el motivo, para el log."""


class Notificar:
    """Lo que hace el worker con cada respuesta."""

    def __init__(self, tokens: TokensDelBot, canal: CanalDeMeta, enviados: Enviados, publisher: bus.EventPublisher,
                 max_deliver: int):
        self._tokens = tokens
        self._canal = canal
        self._enviados = enviados
        self._publisher = publisher
        # Sin límite (-1), nunca es la última entrega: se espera siempre.
        self._max_deliver = max_deliver

    def _ultima(self, mensaje) -> bool:
        return 0 < self._max_deliver <= entregas(mensaje)

    async def __call__(self, mensaje) -> Resultado:
        try:
            sobre, _ = leer_del_motor(mensaje, MensajeRespondido, "respuesta")
        except Descartado as e:
            log.warning("Un mensaje de %s se descarta: %s", STREAM, e)
            return Resultado.DESCARTADO
        traza = (mensaje.headers or {}).get("traceparent")
        with tracing.span("engine.notifier", parent=traza, kind=tracing.SpanKind.CONSUMER, **{
                "gateway.bot_id": str(sobre.botId), "gateway.client_id": str(sobre.clientId),
                "gateway.channel": sobre.channel, "messaging.system": "nats"}) as current:
            try:
                resultado = await self._notificar(sobre)
            except _Esperar as e:
                if self._ultima(mensaje):
                    log.error("La respuesta a un mensaje del bot %s no se pudo enviar en la última entrega: %s",
                              sobre.botId, e)
                    resultado = Resultado.DESCARTADO
                else:
                    log.warning("La respuesta a un mensaje del bot %s se intentará otra vez: %s", sobre.botId, e)
                    resultado = Resultado.EN_ESPERA
            current.set(**{"gateway.outcome": resultado.value})
            return resultado

    async def _notificar(self, sobre: MensajeRespondido) -> Resultado:
        if sobre.channel != "whatsapp":
            log.warning("La respuesta a un mensaje de %s del bot %s se descarta: ese canal llega en el E10",
                        sobre.channel, sobre.botId)
            return Resultado.DESCARTADO
        if not sobre.cuentaDelBot or not sobre.contact.waId:
            log.warning("La respuesta a un mensaje del bot %s se descarta: no se sabe desde qué número ni a quién",
                        sobre.botId)
            return Resultado.DESCARTADO
        try:
            envio = await self._enviados.enviado(sobre.botId, sobre.messageId)
        except RegistroNoDisponible as e:
            # Sin saberlo, enviar podría duplicarlo.
            raise _Esperar(f"enviados: {e}") from None
        if envio is None:
            envio = await self._enviar(sobre)
            if isinstance(envio, Resultado):
                return envio
        else:
            log.info("La respuesta a un mensaje del bot %s ya había salido: se publica sin enviarla otra vez",
                     sobre.botId)
        return await self._publicar(sobre, envio)

    async def _enviar(self, sobre: MensajeRespondido) -> Envio | Resultado:
        try:
            token = await self._tokens.token_de_whatsapp(sobre.clientId, sobre.botId)
            try:
                enviado = await self._canal.enviar_texto(token, sobre.cuentaDelBot, sobre.contact.waId,
                                                         sobre.respuesta.texto)
            except TokenRechazado:
                # Puede haber cambiado en el gateway: una vez más con el que tenga ahora.
                self._tokens.olvidar(sobre.botId)
                token = await self._tokens.token_de_whatsapp(sobre.clientId, sobre.botId)
                enviado = await self._canal.enviar_texto(token, sobre.cuentaDelBot, sobre.contact.waId,
                                                         sobre.respuesta.texto)
        except NoEncontrado as e:
            log.warning("La respuesta a un mensaje del bot %s se descarta: sin %s", sobre.botId, e)
            return Resultado.DESCARTADO
        except EnvioRechazado as e:
            log.warning("Meta no acepta la respuesta a un mensaje del bot %s: %s", sobre.botId, e)
            return Resultado.DESCARTADO
        except (FuenteNoDisponible, EnvioFallido) as e:
            raise _Esperar(str(e)) from None
        envio = Envio(message_id=enviado, sent_at=datetime.now(timezone.utc))
        try:
            await self._enviados.apuntar(sobre.botId, sobre.messageId, envio)
        except RegistroNoDisponible as e:
            # Ya salió: no se deja de publicar por esto. Solo si además falla publicar y se entrega otra vez, puede
            # llegar dos veces.
            log.error("La respuesta a un mensaje del bot %s salió, pero no se pudo apuntar: %s", sobre.botId, e)
        return envio

    async def _publicar(self, sobre: MensajeRespondido, envio: Envio) -> Resultado:
        evento = SentReply(schemaVersion=SCHEMA_VERSION, botId=sobre.botId, clientId=sobre.clientId,
                           contactId=sobre.contact.uuid, channel=sobre.channel, inReplyTo=sobre.messageId,
                           messageId=envio.message_id, sentAt=envio.sent_at, text=sobre.respuesta.texto)
        traza = tracing.traceparent()
        headers = {"traceparent": traza} if traza else {}
        try:
            await self._publisher.publish(reply_subject(sobre.botId), evento.model_dump_json().encode(),
                                          f"{sobre.botId}:{envio.message_id}", headers)
        except bus.BusUnavailable as e:
            raise _Esperar(f"Bifröst: {e}") from None
        log.info("Respuesta enviada a un mensaje del bot %s (%s)", sobre.botId, sobre.respuesta.fuente)
        return Resultado.CONFIRMADO


async def preparar(settings: NotifierSettings, max_deliver: int, conexion, store: EngineKeyStore | None = None):
    """
        Lo que el worker abre al arrancar: la API del gateway, para los tokens, la Cloud API de WhatsApp, el bucket
        `enviados` con la conexión del worker, y el publicador. Devuelve cómo atender cada mensaje y cómo cerrar lo
        abierto.
    """
    store = store or EngineKeyStore(settings.andvari_addr, settings.engine_role_id, settings.engine_secret_id_file,
                                    settings.andvari_ca_file)
    tokens = ApiDelGateway(settings.gateway_url, settings.gateway_audience,
                           clave_publica_del_gateway(settings.gateway_public_keys_file), store, NOMBRE,
                           ca_file=settings.gateway_ca_file, timeout=settings.notifier_timeout)
    canal = WhatsAppCloud(settings.graph_url, settings.graph_version, settings.notifier_timeout)
    publisher = publicador(settings, NOMBRE)

    async def cerrar() -> None:
        await publisher.close()

    return Notificar(tokens, canal, EnviadosEnBifrost(conexion.jetstream()), publisher, max_deliver), cerrar


def main() -> None:
    """El worker: su configuración y su bucle sobre MOTOR."""
    settings = NotifierSettings()
    asyncio.run(ejecutar(NOMBRE, settings, STREAM, CONSUMIDOR,
                         lambda max_deliver, conexion: preparar(settings, max_deliver, conexion)))


if __name__ == "__main__":
    main()
