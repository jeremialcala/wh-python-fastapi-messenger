# -*- coding: utf-8 -*-
"""
    What the gateway really publishes to the `llm` queue must match the AsyncAPI contract the response engine reads.
    The message is produced by the real processing code; only the database and the broker are replaced.
"""
import asyncio
import copy
import json
import pathlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import yaml
from jsonschema import Draft202012Validator

import controller.messages as messages
from classes import FacebookRequest

ROOT = pathlib.Path(__file__).resolve().parents[2]
ASYNCAPI = yaml.safe_load((ROOT / "docs" / "02-design" / "contracts" / "asyncapi.yaml").read_text(encoding="utf-8"))
ENVELOPE = Draft202012Validator({"$ref": "#/components/schemas/SobreMensaje", "components": ASYNCAPI["components"]})

BOT_ID = "11111111-1111-4111-8111-111111111111"
PAYLOADS = {
    "whatsapp": {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "15550001111", "phone_number_id": "100000000000001"},
        "contacts": [{"profile": {"name": "Ana"}, "wa_id": "584120000000"}],
        "messages": [{"from": "584120000000", "id": "wamid.TEST", "timestamp": "1760000000", "type": "text",
                      "text": {"body": "hola"}}]}}]}]},
    "messenger": {"object": "page", "entry": [{"id": "1", "time": 1760000000000, "messaging": [{
        "sender": {"id": "123456789"}, "recipient": {"id": "987654321"}, "timestamp": 1760000000000,
        "message": {"mid": "m_TEST", "text": "hola"}}]}]},
}


@pytest.fixture
def published(monkeypatch):
    """Returns a function that runs a webhook payload through the gateway and gives back the queued message."""
    captured = {}

    async def capture(queue, message):
        captured["queue"], captured["body"] = queue, json.loads(message.to_json())

    contact = SimpleNamespace(firstName="Ana", waId="584120000000", fbId="123456789")
    monkeypatch.setattr(messages, "send_message_to_queue", capture)
    monkeypatch.setattr(messages, "ctr_identify_contact_by_wa_id", AsyncMock(return_value=contact))
    monkeypatch.setattr(messages, "ctr_identify_fb_contact", AsyncMock(return_value=contact))

    def run(payload):
        captured.clear()
        asyncio.run(messages.ctr_process_messages(req=FacebookRequest(**payload), _bot=SimpleNamespace(uuid=BOT_ID)))
        return dict(captured)

    return run


@pytest.mark.parametrize("channel", sorted(PAYLOADS))
def test_published_message_matches_the_contract(published, channel):
    result = published(PAYLOADS[channel])

    assert result["queue"] == ASYNCAPI["channels"]["llm"]["address"]
    assert [error.message for error in ENVELOPE.iter_errors(result["body"])] == []


@pytest.mark.parametrize("channel", sorted(PAYLOADS))
def test_published_message_carries_the_target_bot(published, channel):
    assert published(PAYLOADS[channel])["body"]["jwe_body"]["botId"] == BOT_ID


def test_contract_rejects_a_message_without_the_target_bot(published):
    body = copy.deepcopy(published(PAYLOADS["whatsapp"])["body"])
    del body["jwe_body"]["botId"]

    assert not ENVELOPE.is_valid(body)


def test_contract_rejects_an_unknown_channel(published):
    body = copy.deepcopy(published(PAYLOADS["whatsapp"])["body"])
    body["jwe_body"]["type"] = "instagram"

    assert not ENVELOPE.is_valid(body)
