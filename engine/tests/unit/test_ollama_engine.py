# -*- coding: utf-8 -*-
"""
    Pruebas de la Fase 2: motor de intención con Ollama (cliente mockeado).
"""
import json
from unittest.mock import MagicMock

from src.domain.enums import Origen, TipoRespuesta
from src.domain.models import Adjunto, MensajeEntrante
from src.infrastructure.llm import OllamaIntentEngine


def _mensaje(texto="¿Cuánto cuesta?", adjuntos=None):
    return MensajeEntrante(
        mensaje_id="m1", origen=Origen.WHATSAPP, remitente="user1",
        texto=texto, adjuntos=adjuntos or [],
    )


def _engine_con_respuesta(contenido: str) -> OllamaIntentEngine:
    client = MagicMock()
    client.chat.return_value = {"message": {"content": contenido}}
    return OllamaIntentEngine(host="http://x", model="m", client=client)


def test_clasificacion_action():
    """Respuesta JSON válida -> intención con tipo ACTION."""
    contenido = json.dumps({
        "etiqueta": "consultar_precio", "tipo_respuesta": "action",
        "confianza": 0.9, "entidades": {"producto": "x"}, "razonamiento": "pide precio",
    })
    intencion = _engine_con_respuesta(contenido).detectar(_mensaje())
    assert intencion.tipo_respuesta == TipoRespuesta.ACTION
    assert intencion.etiqueta == "consultar_precio"
    assert intencion.confianza == 0.9


def test_adjunto_atajo_sin_llm():
    """Si el mensaje trae adjuntos, clasifica ADJUNTO sin invocar al LLM."""
    client = MagicMock()
    engine = OllamaIntentEngine(host="http://x", model="m", client=client)
    msg = _mensaje(texto="", adjuntos=[Adjunto(tipo="image", url_o_id="id1")])
    intencion = engine.detectar(msg)
    assert intencion.tipo_respuesta == TipoRespuesta.ADJUNTO
    client.chat.assert_not_called()


def test_json_malformado_fallback_texto():
    """JSON inválido del modelo -> fallback seguro a TEXTO."""
    intencion = _engine_con_respuesta("esto no es json").detectar(_mensaje())
    assert intencion.tipo_respuesta == TipoRespuesta.TEXTO
    assert intencion.confianza == 0.0


def test_confianza_baja_fallback():
    """Confianza por debajo del umbral -> fallback a TEXTO."""
    contenido = json.dumps({"etiqueta": "x", "tipo_respuesta": "action", "confianza": 0.1})
    intencion = _engine_con_respuesta(contenido).detectar(_mensaje())
    assert intencion.tipo_respuesta == TipoRespuesta.TEXTO


def test_error_cliente_fallback():
    """Una excepción del cliente -> fallback a TEXTO."""
    client = MagicMock()
    client.chat.side_effect = RuntimeError("conexión rechazada")
    engine = OllamaIntentEngine(host="http://x", model="m", client=client)
    intencion = engine.detectar(_mensaje())
    assert intencion.tipo_respuesta == TipoRespuesta.TEXTO
