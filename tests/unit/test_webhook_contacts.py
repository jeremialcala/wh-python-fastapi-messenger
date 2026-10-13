# -*- coding: utf-8 -*-
"""
    The webhook has no authenticated client: the chatbot in the URL says whose notification it is. These tests
    send signed notifications to a stored chatbot, with only the broker and the Graph API replaced, and check
    that the contact ends up under the client that owns the chatbot.
"""
import hashlib
import hmac
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import app as app_module
import controller.facebook as facebook
import controller.messages as messages
from classes import ChatBot, Contact
from repository import TenantRepository

APP_SECRET = os.environ["FACEBOOK_APP_SECRET"]

WHATSAPP = {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [{"field": "messages", "value": {
    "messaging_product": "whatsapp",
    "metadata": {"display_phone_number": "12025550101", "phone_number_id": "100000000000001"},
    "contacts": [{"profile": {"name": "Ana"}, "wa_id": "12025550143"}],
    "messages": [{"from": "12025550143", "id": "wamid.TEST", "timestamp": "1760000000", "type": "text",
                  "text": {"body": "hola"}}]}}]}]}
MESSENGER = {"object": "page", "entry": [{"id": "1", "time": 1760000000000, "messaging": [{
    "sender": {"id": "123456789"}, "recipient": {"id": "987654321"}, "timestamp": 1760000000000,
    "message": {"mid": "m_TEST", "text": "hola"}}]}]}


@pytest.fixture
def queue(monkeypatch):
    send = AsyncMock()
    monkeypatch.setattr(messages, "send_message_to_queue", send)
    return send


@pytest.fixture
def graph_api(monkeypatch):
    profile = {"id": "123456789", "first_name": "Ana", "last_name": "Diaz", "profile_pic": "https://example.com/a.jpg"}
    get = lambda url, timeout: SimpleNamespace(status_code=200, text="{}", json=lambda: profile)  # noqa: E731
    monkeypatch.setattr(facebook.requests, "get", get)


@pytest.fixture
def owner(register):
    return TenantRepository(register("acme").client_id)


@pytest.fixture
def bot(owner):
    return owner.add_bot(ChatBot(name="Bot", role="Sales Assistant", description="A test chatbot", tone="helpful",
                                 facebookToken="page-token"))


def notify(bot_id, payload):
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return TestClient(app_module.app).post(f"/chat/{bot_id}", content=body,
                                           headers={"content-type": "application/json",
                                                    "X-Hub-Signature-256": signature})


def test_a_whatsapp_contact_is_stored_under_the_client_of_the_chatbot(owner, bot, queue):
    assert notify(bot.uuid, WHATSAPP).status_code == 200

    contact = Contact.objects.get()
    assert (contact.clientId, contact.botId, owner.contact_number(contact), contact.firstName) == (
        owner.client_id, bot.uuid, "12025550143", "Ana")
    queue.assert_awaited_once()


def test_a_messenger_contact_is_stored_under_the_client_of_the_chatbot(owner, bot, queue, graph_api):
    assert notify(bot.uuid, MESSENGER).status_code == 200

    contact = Contact.objects.get()
    assert (contact.clientId, contact.botId, contact.fbId, contact.firstName) == (
        owner.client_id, bot.uuid, "123456789", "Ana")
    queue.assert_awaited_once()


@pytest.mark.parametrize("payload", [WHATSAPP, MESSENGER], ids=["whatsapp", "messenger"])
def test_a_known_contact_is_not_stored_again(bot, queue, graph_api, payload):
    notify(bot.uuid, payload)
    notify(bot.uuid, payload)

    assert Contact.objects.count() == 1
    assert queue.await_count == 2


def test_the_same_person_writing_to_chatbots_of_two_clients_is_two_contacts(owner, bot, queue, register):
    other = TenantRepository(register("globex").client_id)
    their_bot = other.add_bot(ChatBot(name="Theirs", role="r", description="d", tone="t"))

    notify(bot.uuid, WHATSAPP)
    notify(their_bot.uuid, WHATSAPP)

    assert sorted(str(contact.clientId) for contact in Contact.objects) == sorted(
        [str(owner.client_id), str(other.client_id)])
    assert other.find_contact_by_wa_id(their_bot.uuid, "12025550143").botId == their_bot.uuid


def test_the_queued_message_names_the_chatbot(bot, queue):
    notify(bot.uuid, WHATSAPP)

    message = json.loads(queue.await_args.kwargs["message"].to_json())
    assert message["jwe_body"]["botId"] == str(bot.uuid)
