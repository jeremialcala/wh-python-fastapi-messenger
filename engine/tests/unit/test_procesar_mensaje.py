# -*- coding: utf-8 -*-
"""
    Pruebas del caso de uso que orquesta el pipeline (puertos mockeados).
"""
from unittest.mock import MagicMock

from src.application import ProcesarMensajeUseCase
from src.domain.enums import TipoRespuesta
from src.domain.models import Intencion, ResultadoGuardrail
from src.domain.ports import GuardrailsPolicy, IntentEngine, MessagePublisher
from src.infrastructure.adapters import WebhookResolver


def _use_case(guardrails, intent_engine, publisher):
    return ProcesarMensajeUseCase(WebhookResolver(), guardrails, intent_engine, publisher)


def test_flujo_completo_publica_clasificado(whatsapp_payload):
    """Entrada permitida -> detecta intención y publica el resultado."""
    guardrails = MagicMock(spec_set=GuardrailsPolicy)
    guardrails.evaluar.return_value = ResultadoGuardrail(permitido=True)
    intent_engine = MagicMock(spec_set=IntentEngine)
    intent_engine.detectar.return_value = Intencion(
        etiqueta="consulta", tipo_respuesta=TipoRespuesta.ACTION, confianza=0.8)
    publisher = MagicMock(spec_set=MessagePublisher)

    resultado = _use_case(guardrails, intent_engine, publisher).ejecutar(whatsapp_payload)

    assert resultado is not None
    assert resultado.permitido is True
    assert resultado.tipo_respuesta == TipoRespuesta.ACTION
    publisher.publicar.assert_called_once_with(resultado)


def test_bloqueado_no_invoca_intencion(messenger_payload):
    """Entrada bloqueada -> publica bloqueado y no llama al motor de intención."""
    guardrails = MagicMock(spec_set=GuardrailsPolicy)
    guardrails.evaluar.return_value = ResultadoGuardrail(permitido=False, motivo="jailbreak")
    intent_engine = MagicMock(spec_set=IntentEngine)
    publisher = MagicMock(spec_set=MessagePublisher)

    resultado = _use_case(guardrails, intent_engine, publisher).ejecutar(messenger_payload)

    assert resultado is not None
    assert resultado.permitido is False
    assert resultado.motivo_bloqueo == "jailbreak"
    intent_engine.detectar.assert_not_called()
    publisher.publicar.assert_called_once()


def test_origen_no_soportado_se_descarta():
    """Un payload de origen no soportado se descarta sin publicar."""
    guardrails = MagicMock(spec_set=GuardrailsPolicy)
    intent_engine = MagicMock(spec_set=IntentEngine)
    publisher = MagicMock(spec_set=MessagePublisher)

    resultado = _use_case(guardrails, intent_engine, publisher).ejecutar(
        {"object": "marketplace", "entry": []})

    assert resultado is None
    guardrails.evaluar.assert_not_called()
    intent_engine.detectar.assert_not_called()
    publisher.publicar.assert_not_called()
