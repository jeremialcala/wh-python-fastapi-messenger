# -*- coding: utf-8 -*-
"""
    A round trip to Atlas costs about 60 ms and Meta allows 250 for the whole answer, so what the webhook asks the
    database for is counted here. The chatbot it finds is kept in memory for a moment: these tests also check that
    what is kept never outlives a deletion or a change of credentials made in this process.
"""
import hashlib
import hmac
import json
import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import mongomock
import pymongo.collection
import pytest
from fastapi.testclient import TestClient

import webhook as webhook_module
import controller.facebook as facebook
import controller.messages as messages
from classes import ChatBot
from repository import TenantRepository, delete_client, kept_bots

# What Meta calls is its own service, apart from the management API.
META = TestClient(webhook_module.app)

APP_SECRET = os.environ["FACEBOOK_APP_SECRET"]
# What mongoengine sends the database for: each call is one round trip.
OPERATIONS = ("find", "find_one", "count_documents", "insert_one", "insert_many", "update_one", "update_many",
              "replace_one", "delete_one", "delete_many", "find_one_and_update", "aggregate")

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
def round_trips(monkeypatch):
    """The operations sent to the database, by collection, from the moment it is reset."""
    sent = []

    def counted(cls, name):
        original = getattr(cls, name)

        def operation(self, *args, **kwargs):
            sent.append((self.name, name))
            return original(self, *args, **kwargs)

        monkeypatch.setattr(cls, name, operation)

    for cls in (mongomock.collection.Collection, pymongo.collection.Collection):
        for name in OPERATIONS:
            if hasattr(cls, name):
                counted(cls, name)
    return sent


@pytest.fixture(autouse=True)
def queue(monkeypatch):
    monkeypatch.setattr(messages, "send_message_to_queue", AsyncMock())


@pytest.fixture(autouse=True)
def graph_api(monkeypatch):
    profile = {"first_name": "Ana", "last_name": "Diaz"}
    get = lambda url, timeout: SimpleNamespace(status_code=200, text="{}", json=lambda: profile)  # noqa: E731
    monkeypatch.setattr(facebook.requests, "get", get)


@pytest.fixture
def owner(register):
    return TenantRepository(register("acme").client_id)


@pytest.fixture
def bot(owner):
    return owner.add_bot(ChatBot(name="Bot", role="Sales Assistant", description="A test chatbot", tone="helpful",
                                 facebookToken="page-token"))


def notify(bot_id, payload, secret=APP_SECRET):
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return META.post(f"/chat/{bot_id}", content=body,
                                           headers={"content-type": "application/json",
                                                    "X-Hub-Signature-256": signature})


@pytest.mark.parametrize("payload", [WHATSAPP, MESSENGER], ids=["whatsapp", "messenger"])
def test_a_known_contact_costs_two_round_trips(bot, round_trips, payload):
    assert notify(bot.uuid, payload).status_code == 200
    round_trips.clear()

    assert notify(bot.uuid, payload).status_code == 200
    # Whether the chatbot is still the client's, and the contact. The chatbot itself comes from memory.
    assert round_trips == [("chat_bot", "find"), ("contact", "find")]


def test_a_new_contact_costs_five(bot, round_trips):
    assert notify(bot.uuid, WHATSAPP).status_code == 200
    round_trips.clear()
    other = json.loads(json.dumps(WHATSAPP).replace("12025550143", "12025550144"))

    assert notify(bot.uuid, other).status_code == 200
    # Five: the chatbot and the contact, as for a known one; then the chatbot again, saving the contact and making
    # sure the chatbot was not deleted in the meantime. The find before the count is not a round trip: mongoengine
    # opens a cursor for it and never reads it, and pymongo only goes to the database when one is read.
    assert round_trips == [("chat_bot", "find"), ("contact", "find"), ("chat_bot", "find"),
                           ("contact", "insert_one"), ("chat_bot", "find"), ("chat_bot", "count_documents")]


def test_a_deleted_chatbot_is_not_answered_from_memory(owner, bot):
    assert notify(bot.uuid, WHATSAPP).status_code == 200
    owner.delete_bot(bot.uuid)

    assert notify(bot.uuid, WHATSAPP).status_code == 404


def test_new_credentials_count_at_once(owner, bot):
    assert notify(bot.uuid, WHATSAPP).status_code == 200
    owner.set_bot_credentials(bot.uuid, appSecret="the-new-app-secret")

    assert notify(bot.uuid, WHATSAPP).status_code == 403
    assert notify(bot.uuid, WHATSAPP, secret="the-new-app-secret").status_code == 200


def test_a_deleted_client_takes_its_chatbots_out_of_memory(register):
    caller = register("globex")
    their_bot = TenantRepository(caller.client_id).add_bot(ChatBot(name="Theirs", role="r", description="d", tone="t"))
    assert notify(their_bot.uuid, WHATSAPP).status_code == 200

    delete_client(caller.client_id)

    assert kept_bots.kept(their_bot.uuid) is None
    assert notify(their_bot.uuid, WHATSAPP).status_code == 404


def test_what_is_not_found_is_not_kept(round_trips):
    unknown = uuid.uuid4()
    assert notify(unknown, WHATSAPP).status_code == 404
    assert notify(unknown, WHATSAPP).status_code == 404

    # Anybody can send ids: every one of them goes to the database, and none stays in memory.
    assert round_trips == [("chat_bot", "find"), ("chat_bot", "find")]
    assert kept_bots.kept(unknown) is None


def test_what_changed_in_another_process_counts_once_the_time_is_up(bot, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(kept_bots.time, "monotonic", lambda: now[0])
    assert notify(bot.uuid, WHATSAPP).status_code == 200
    # Deleted behind the back of this process, as another worker or a migration would.
    ChatBot.objects(uuid=bot.uuid).delete()

    now[0] += kept_bots.KEEP_FOR - 1
    assert kept_bots.kept(bot.uuid) is not None
    now[0] += 1
    assert kept_bots.kept(bot.uuid) is None
    assert notify(bot.uuid, WHATSAPP).status_code == 404


def test_memory_holds_a_bounded_number_of_chatbots(monkeypatch):
    monkeypatch.setattr(kept_bots, "MAX_KEPT", 2)
    first, second, third = (SimpleNamespace(uuid=uuid.uuid4()) for _ in range(3))
    for bot in (first, second, third):
        kept_bots.keep(bot)

    # The one found longest ago makes room.
    assert [kept_bots.kept(bot.uuid) for bot in (first, second, third)] == [None, second, third]
