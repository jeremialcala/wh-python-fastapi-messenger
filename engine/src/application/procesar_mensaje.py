# -*- coding: utf-8 -*-
"""
    Caso de uso que orquesta el pipeline de procesamiento de un mensaje Meta:

        1. Identificar origen + normalizar (WebhookResolver / WebhookParser)
        2. Capa de seguridad (GuardrailsPolicy)  -> bloquea jailbreak/off-topic
        3. Detección de intención (IntentEngine)
        4. Publicar ResultadoClasificado (MessagePublisher)

    Depende solo de puertos del dominio (regla de dependencia hacia adentro).
"""
import logging
from inspect import currentframe

from src.domain.enums import TipoRespuesta
from src.domain.models import MensajeEntrante, ResultadoClasificado
from src.domain.ports import (
    GuardrailsPolicy, IntentEngine, MessageNormalizer, MessagePublisher, OrigenNoSoportado
)
from src.infrastructure.shared import (
    STARTING_AT, ENDING_AT, enmascarar,
    AUDIT_RECIBIDO, AUDIT_BLOQUEADO, AUDIT_INTENCION, AUDIT_PUBLICADO,
)

log = logging.getLogger(__name__)


class ProcesarMensajeUseCase:
    """
        Orquesta el pipeline. Recibe el payload crudo del webhook y publica el
        resultado clasificado. Registra auditoría con PII enmascarada (SOC2).
    """

    def __init__(self, resolver: MessageNormalizer, guardrails: GuardrailsPolicy,
                 intent_engine: IntentEngine, publisher: MessagePublisher):
        self._resolver = resolver
        self._guardrails = guardrails
        self._intent_engine = intent_engine
        self._publisher = publisher

    def ejecutar(self, raw_payload) -> ResultadoClasificado | None:
        """
        :param raw_payload: cuerpo crudo del mensaje AMQP (bytes/str/dict).
        :return: el ResultadoClasificado publicado, o None si el payload se descartó.
        """
        log.info(STARTING_AT, currentframe().f_code.co_name)

        # 1. Identificar origen + normalizar
        try:
            mensaje = self._resolver.parsear(raw_payload)
        except OrigenNoSoportado as exc:
            log.warning("Payload de origen no soportado, descartado: %s", exc)
            return None
        except ValueError as exc:
            log.warning("Payload inválido, descartado: %s", exc)
            return None

        log.info(AUDIT_RECIBIDO, mensaje.origen.value,
                 mensaje.mensaje_id, enmascarar(mensaje.remitente))

        # 2. Capa de seguridad (guardrails)
        veredicto = self._guardrails.evaluar(mensaje.texto)
        if not veredicto.permitido:
            log.warning(AUDIT_BLOQUEADO, mensaje.mensaje_id, veredicto.motivo)
            return self._publicar(self._resultado_bloqueado(mensaje, veredicto.motivo))

        # 3. Detección de intención
        intencion = self._intent_engine.detectar(mensaje)
        log.info(AUDIT_INTENCION, mensaje.mensaje_id, intencion.etiqueta,
                 intencion.tipo_respuesta.value, intencion.confianza)

        # 4. Publicar resultado clasificado
        resultado = ResultadoClasificado(
            mensaje_id=mensaje.mensaje_id,
            origen=mensaje.origen,
            remitente=mensaje.remitente,
            tipo_respuesta=intencion.tipo_respuesta,
            intencion=intencion,
            payload={
                "texto": mensaje.texto,
                "adjuntos": [a.model_dump() for a in mensaje.adjuntos],
            },
        )
        salida = self._publicar(resultado)
        log.info(ENDING_AT, currentframe().f_code.co_name)
        return salida

    def _publicar(self, resultado: ResultadoClasificado) -> ResultadoClasificado:
        """Publica el resultado y deja traza de auditoría."""
        self._publisher.publicar(resultado)
        log.info(AUDIT_PUBLICADO, resultado.mensaje_id, resultado.tipo_respuesta.value)
        return resultado

    @staticmethod
    def _resultado_bloqueado(mensaje: MensajeEntrante, motivo: str) -> ResultadoClasificado:
        """Construye el resultado para una entrada bloqueada por guardrails."""
        return ResultadoClasificado(
            mensaje_id=mensaje.mensaje_id,
            origen=mensaje.origen,
            remitente=mensaje.remitente,
            tipo_respuesta=TipoRespuesta.TEXTO,
            permitido=False,
            motivo_bloqueo=motivo,
        )
