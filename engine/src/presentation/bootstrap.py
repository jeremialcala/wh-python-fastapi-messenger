# -*- coding: utf-8 -*-
"""
    Punto de entrada del servicio: construye e inyecta las dependencias del
    pipeline (composición) y arranca el consumidor AMQP.
"""
import logging.config
from inspect import currentframe

from src.application import ProcesarMensajeUseCase
from src.infrastructure.adapters import WebhookResolver
from src.infrastructure.amqp import AmqpConsumer, AmqpPublisher
from src.infrastructure.config import Settings
from src.infrastructure.guardrails import NeMoGuardrailsPolicy
from src.infrastructure.llm import OllamaIntentEngine
from src.infrastructure.logging import configure_logging
from src.infrastructure.shared import STARTING_AT, ENDING_AT

_set = Settings()
logging.config.dictConfig(configure_logging())
log = logging.getLogger(_set.environment)


def construir_use_case(settings: Settings = _set) -> ProcesarMensajeUseCase:
    """
        Compone el caso de uso con sus implementaciones concretas.

    :param settings: configuración del servicio.
    :return: el caso de uso listo para procesar mensajes.
    """
    resolver = WebhookResolver()
    guardrails = NeMoGuardrailsPolicy(
        config_path=settings.guardrails_config_path,
        ollama_model=settings.ollama_model,
        ollama_base_url=settings.ollama_host,
    )
    intent_engine = OllamaIntentEngine(
        host=settings.ollama_host,
        model=settings.ollama_model,
    )
    publisher = AmqpPublisher(
        queue=settings.output_queue_name,
        routing_key=settings.output_routing_key,
    )
    return ProcesarMensajeUseCase(resolver, guardrails, intent_engine, publisher)


def run(settings: Settings = _set) -> None:
    """
        Arranca el consumidor AMQP conectado al pipeline.
    """
    log.info(STARTING_AT, currentframe().f_code.co_name)
    use_case = construir_use_case(settings)
    consumer = AmqpConsumer(handler=use_case.ejecutar)
    consumer.start(
        queue=settings.queue_name,
        exchange=settings.amqp_exchange,
        routing_key=settings.amqp_routing_key,
    )
    log.info(ENDING_AT, currentframe().f_code.co_name)
