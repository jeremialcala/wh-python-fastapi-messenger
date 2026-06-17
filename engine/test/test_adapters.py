# -*- coding: utf-8 -*-
"""
    Pruebas de la Fase 1: parseo e identificación de origen de webhooks Meta.
"""
import json

import pytest

from src.domain.enums import Origen
from src.infrastructure.adapters import (
    WebhookResolver, OrigenNoSoportado, sanitizar_texto, sanitizar_id
)


def test_messenger(messenger_payload):
    """Messenger -> origen MESSENGER y texto normalizado."""
    msg = WebhookResolver().parsear(messenger_payload)
    assert msg.origen == Origen.MESSENGER
    assert msg.remitente == "USER_PSID"
    assert msg.mensaje_id == "mid.123"
    assert msg.texto == "Hola, ¿tienen stock?"
    assert not msg.tiene_adjuntos


def test_instagram(instagram_payload):
    """Instagram -> origen INSTAGRAM."""
    msg = WebhookResolver().parsear(instagram_payload)
    assert msg.origen == Origen.INSTAGRAM
    assert msg.remitente == "IGSID"


def test_whatsapp_texto(whatsapp_payload):
    """WhatsApp texto -> origen WHATSAPP y body extraído."""
    msg = WebhookResolver().parsear(whatsapp_payload)
    assert msg.origen == Origen.WHATSAPP
    assert msg.remitente == "5215512345678"
    assert msg.mensaje_id == "wamid.ABC"
    assert msg.texto == "Quiero información"


def test_whatsapp_imagen(whatsapp_image_payload):
    """WhatsApp imagen -> adjunto con media id y caption como texto."""
    msg = WebhookResolver().parsear(whatsapp_image_payload)
    assert msg.tiene_adjuntos
    assert msg.adjuntos[0].tipo == "image"
    assert msg.adjuntos[0].url_o_id == "MEDIA_ID"
    assert msg.adjuntos[0].mime_type == "image/jpeg"
    assert msg.texto == "mira"


def test_acepta_bytes_json(messenger_payload):
    """El resolver acepta el payload como bytes JSON (cuerpo AMQP)."""
    raw = json.dumps(messenger_payload).encode("utf-8")
    msg = WebhookResolver().parsear(raw)
    assert msg.origen == Origen.MESSENGER


def test_origen_desconocido():
    """Un object no soportado lanza OrigenNoSoportado."""
    with pytest.raises(OrigenNoSoportado):
        WebhookResolver().parsear({"object": "marketplace", "entry": []})


def test_json_invalido():
    """Un payload no-JSON lanza ValueError."""
    with pytest.raises(ValueError):
        WebhookResolver().parsear(b"no soy json")


def test_payload_sin_mensaje():
    """Un webhook válido sin mensaje (solo statuses) lanza ValueError."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"statuses": [{"status": "delivered"}]}}]}],
    }
    with pytest.raises(ValueError):
        WebhookResolver().parsear(payload)


def test_sanitizar_texto_recorta_control_y_longitud():
    """Sanitización: elimina control chars y limita longitud."""
    assert sanitizar_texto("hola\x00\x07 mundo") == "hola mundo"
    assert len(sanitizar_texto("a" * 5000, max_len=10)) == 10
    assert sanitizar_texto(None) == ""


def test_sanitizar_id_descarta_caracteres():
    """Sanitización de IDs: descarta caracteres no permitidos."""
    assert sanitizar_id("abc-123_DEF") == "abc-123_DEF"
    assert sanitizar_id("<script>") == "script"
