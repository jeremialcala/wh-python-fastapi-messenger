# -*- coding: utf-8 -*-
"""
    Configuración compartida de pytest: variables de entorno mínimas para
    instanciar Settings y fixtures de webhooks de Meta.
"""
import os

import pytest

# Settings se instancia al importar varios módulos; fijamos el entorno mínimo
# (estas variables tienen precedencia sobre config.env) antes de cualquier import.
_ENV_DEFAULTS = {
    "national_id_url": "https://example.com/national-id",
    "service_name": "ms-python-metamsghandler-test",
    "db_name": "testdb",
    "db_host": "mongodb://localhost:27017",
    "db_username": "tester",
    "db_password": "secret",
    "qms_server": "localhost",
    "qms_port": "5672",
    "qms_user": "guest",
    "qms_password": "guest",
    "queue_name": "meta-inbound",
    "amqp_exchange": "my_exchange",
    "amqp_routing_key": "meta.#",
    "output_queue_name": "meta-classified",
    "output_routing_key": "meta.classified",
    "ollama_host": "http://localhost:11434",
    "ollama_model": "llama3.1",
    "guardrails_config_path": "src/infrastructure/guardrails/config",
    "key_size": "2048",
    "private_key_filename": "certs/private.pem",
    "public_key_filename": "certs/public.pem",
    "environment": "development",
    "version": "0.0.1-test",
    "entity_schema": '{"firstName": {"type": "StringField", "required": true, "unique": false}}',
    "entity_jwk": '{"kid": {"type": "StringField", "required": true, "unique": true}}',
    "dto_schema": '{"firstName": {"type": "string", "description": "User first name"}}',
    "dto_message": '{"client_id": {"type": "string", "description": "Client identifier"}}',
}
for _k, _v in _ENV_DEFAULTS.items():
    os.environ.setdefault(_k, _v)


@pytest.fixture(name="messenger_payload")
def fixture_messenger_payload():
    """Webhook de Messenger con un mensaje de texto."""
    return {
        "object": "page",
        "entry": [{
            "id": "PAGE_ID",
            "time": 1458692752478,
            "messaging": [{
                "sender": {"id": "USER_PSID"},
                "recipient": {"id": "PAGE_ID"},
                "timestamp": 1458692752478,
                "message": {"mid": "mid.123", "text": "Hola, ¿tienen stock?"},
            }],
        }],
    }


@pytest.fixture(name="instagram_payload")
def fixture_instagram_payload():
    """Webhook de Instagram con un mensaje de texto."""
    return {
        "object": "instagram",
        "entry": [{
            "id": "IG_ID",
            "time": 1569262486134,
            "messaging": [{
                "sender": {"id": "IGSID"},
                "recipient": {"id": "IG_ID"},
                "timestamp": 1569262485349,
                "message": {"mid": "mid.ig.1", "text": "Buenas"},
            }],
        }],
    }


@pytest.fixture(name="whatsapp_payload")
def fixture_whatsapp_payload():
    """Webhook de WhatsApp Cloud API con un mensaje de texto."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WABA_ID",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "1555", "phone_number_id": "PNID"},
                    "contacts": [{"wa_id": "5215512345678", "profile": {"name": "Ana"}}],
                    "messages": [{
                        "from": "5215512345678",
                        "id": "wamid.ABC",
                        "timestamp": "1603059201",
                        "type": "text",
                        "text": {"body": "Quiero información"},
                    }],
                },
            }],
        }],
    }


@pytest.fixture(name="whatsapp_image_payload")
def fixture_whatsapp_image_payload():
    """Webhook de WhatsApp con un adjunto de imagen."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WABA_ID",
            "changes": [{
                "field": "messages",
                "value": {
                    "messages": [{
                        "from": "5215512345678",
                        "id": "wamid.IMG",
                        "timestamp": "1603059300",
                        "type": "image",
                        "image": {"id": "MEDIA_ID", "mime_type": "image/jpeg", "caption": "mira"},
                    }],
                },
            }],
        }],
    }
