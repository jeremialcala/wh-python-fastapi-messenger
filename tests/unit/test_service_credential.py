# -*- coding: utf-8 -*-
"""
    The credential of the response engine (ADR-0016). The engine holds one key per client, and the operator
    registers its public part under that client. With it the engine reads what it needs to answer for the
    chatbots of that client, the Meta tokens among it, and reaches nothing else: no other client, and no route
    that is not written down for it.
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import mongoengine
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import app as app_module
import webhook as webhook_module
import controller.ingestion as ingestion
from auth import gateway_keys
from auth.client import build_token, new_signing_key, public_part
from classes import Client, Contact
from conftest import GATEWAY_AUDIENCE, GATEWAY_KEYS_FILE
from enums import Role, Status
from repository import TenantRepository, data_keys, find_signer

# What Meta calls is its own service, apart from the management API.
META = TestClient(webhook_module.app)

BOT = {"name": "Mine", "role": "Sales Assistant", "description": "A test chatbot", "tone": "helpful"}
SECRETS = {"facebookToken": "EAAG-page-token-0123456789", "whatsappToken": "EAAG-whatsapp-token-9876543210",
           "appSecret": "app-secret-of-this-test"}
INTENT = {"name": "check_order", "description": "Order status",
          "actions": [{"name": "get_order", "description": "Looks an order up",
                       "apiCall": {"url": "https://api.example.com/orders/{id}"}}]}
BODIES = {
    ("POST", "/bot"): BOT,
    ("POST", "/chat/{bot_id}/phones"): {"phoneNumber": "12025550101", "phoneId": "100000000000001"},
    ("POST", "/chat/{bot_id}/rules"): {"rules": ["Obey the engine"]},
    ("POST", "/chat/{bot_id}/intents"): INTENT,
    ("PUT", "/chat/{bot_id}/intents/{intent_id}"): INTENT,
    ("PUT", "/chat/{bot_id}/credentials"): {"appSecret": "another-secret"},
    ("POST", "/contacts/search"): {"waId": "12025550143"},
    ("POST", "/keys"): {"signingKey": public_part(new_signing_key())},
    ("POST", "/clients"): {"name": "initech", "signingKey": public_part(new_signing_key())},
    ("POST", "/clients/{client_id}/keys"): {"signingKey": public_part(new_signing_key())},
    ("POST", "/clients/{client_id}/service-keys"): {"signingKey": public_part(new_signing_key())},
}
PUBLIC = {("GET", "/chat/{bot_id}"), ("POST", "/chat/{bot_id}"), ("GET", "/health")}
ROUTES = sorted({(method, route.path) for route in app_module.app.routes if isinstance(route, APIRoute)
                 for method in route.methods} - PUBLIC)
FOR_THE_ENGINE = [("GET", "/chat/{bot_id}/contacts/{contact_id}/turns"), ("GET", "/chat/{bot_id}/rules"),
                  ("GET", "/chat/{bot_id}/tokens"), ("GET", "/chat/{bot_id}/tools"), ("GET", "/gateway/keys")]
NOT_FOR_THE_ENGINE = [route for route in ROUTES if route not in FOR_THE_ENGINE]


class Engine:
    """The response engine, with the key it holds for one client."""

    def __init__(self, client_id, key: dict | None = None):
        self.client_id = client_id
        self.key = key or new_signing_key()
        self.public = public_part(self.key)
        self.kid = None

    @property
    def auth(self) -> dict:
        gateway_key = gateway_keys.GatewayKeys.load(GATEWAY_KEYS_FILE).public_set()["keys"][0]
        return {"Authorization": f"Bearer {build_token(self.key, self.client_id, GATEWAY_AUDIENCE, gateway_key)}"}


@pytest.fixture
def http():
    return TestClient(app_module.app)


@pytest.fixture(autouse=True)
def queue(monkeypatch):
    sent = []

    async def capture(queue, message):
        sent.append(json.loads(message.to_json()))

    monkeypatch.setattr(ingestion, "send_message_to_queue", capture)
    return sent


@pytest.fixture
def acme(register):
    return register("acme")


@pytest.fixture
def globex(register):
    return register("globex")


def new_bot(http, caller, secrets=SECRETS) -> dict:
    created = http.post("/bot", headers=caller.auth, json=BOT).json()["data"]
    calls = [("POST", "rules", {"rules": ["Be kind"]}), ("POST", "intents", INTENT)]
    if secrets:
        calls.append(("PUT", "credentials", secrets))
    for method, path, body in calls:
        assert http.request(method, f"/chat/{created['uuid']}/{path}", headers=caller.auth,
                            json=body).status_code == 200
    return created


@pytest.fixture
def bot(http, acme):
    return new_bot(http, acme)["uuid"]


def let_in(http, operator, client_id, engine: Engine):
    """The operator registers the key the engine holds for a client."""
    response = http.post(f"/clients/{client_id}/service-keys", headers=operator.auth,
                         json={"signingKey": engine.public})
    if response.status_code == 200:
        engine.kid = response.json()["data"]["serviceKeys"][-1]
    return response


@pytest.fixture
def engine(http, operator, acme):
    """The response engine, let in for acme."""
    engine = Engine(acme.client_id)
    assert let_in(http, operator, acme.client_id, engine).status_code == 200
    return engine


def dump() -> str:
    """Everything in the database but the tokens already used, as text."""
    database = mongoengine.get_db()
    return json.dumps({name: list(database[name].find({})) for name in sorted(database.list_collection_names())
                       if name != "seen_token"}, default=str, sort_keys=True)


# --- What the engine gets -----------------------------------------------------------------------------------------

def test_the_engine_gets_the_tokens_of_a_chatbot_of_its_client(http, engine, bot):
    response = http.get(f"/chat/{bot}/tokens", headers=engine.auth)

    assert response.status_code == 200
    assert response.json()["data"] == {"uuid": bot, "facebookToken": SECRETS["facebookToken"],
                                       "whatsappToken": SECRETS["whatsappToken"]}


def test_the_engine_gets_the_rest_of_what_it_answers_with(http, engine, bot):
    rules = http.get(f"/chat/{bot}/rules", headers=engine.auth)
    tools = http.get(f"/chat/{bot}/tools", headers=engine.auth)
    keys = http.get("/gateway/keys", headers=engine.auth)

    assert (rules.status_code, tools.status_code, keys.status_code) == (200, 200, 200)
    assert "Be kind" in rules.json()["data"]
    assert [tool["name"] for tool in tools.json()["data"]] == ["get_order"]
    assert keys.json()["data"]["audience"] == GATEWAY_AUDIENCE


def test_what_the_engine_may_call_is_written_down_and_nothing_else_is():
    assert sorted(app_module.SERVICE_ROUTES) == FOR_THE_ENGINE
    assert set(FOR_THE_ENGINE) <= set(ROUTES)


def test_the_tokens_come_without_the_secrets_the_engine_has_no_use_for(http, acme, engine):
    """The App Secret only checks what Meta sends, and the verification token is the client's to paste in Meta."""
    created = new_bot(http, acme)

    response = http.get(f"/chat/{created['uuid']}/tokens", headers=engine.auth)

    assert set(response.json()["data"]) == {"uuid", "facebookToken", "whatsappToken"}
    assert SECRETS["appSecret"] not in response.text and created["verifyToken"] not in response.text


def test_a_chatbot_without_tokens_has_none_to_give(http, acme, engine):
    created = new_bot(http, acme, secrets=None)

    response = http.get(f"/chat/{created['uuid']}/tokens", headers=engine.auth)

    assert response.status_code == 200
    assert response.json()["data"] == {"uuid": created["uuid"], "facebookToken": None, "whatsappToken": None}


def test_the_answer_with_the_tokens_is_not_to_be_kept(http, engine, bot):
    assert http.get(f"/chat/{bot}/tokens", headers=engine.auth).headers["cache-control"] == "no-store"


@pytest.mark.parametrize("bot_id", [str(uuid4()), "not-a-uuid"])
def test_there_are_no_tokens_of_a_chatbot_that_does_not_exist(http, engine, bot_id):
    response = http.get(f"/chat/{bot_id}/tokens", headers=engine.auth)

    assert (response.status_code, response.json()["code"]) == (404, 404)


def test_without_the_key_service_no_token_is_handed_out(http, engine, bot, key_service):
    key_service.down = True
    data_keys.forget()

    response = http.get(f"/chat/{bot}/tokens", headers=engine.auth)

    assert (response.status_code, response.json()["code"]) == (503, 503)
    assert "data" not in response.json()


def test_a_failure_handing_out_the_tokens_says_nothing_of_itself(http, engine, bot, monkeypatch, caplog):
    # Everything the service writes, down to its debug lines: development and staging keep those.
    caplog.set_level(logging.DEBUG, logger=app_module.settings.environment)

    def fails(*args, **kwargs):
        raise RuntimeError(f"failure-text-marker {SECRETS['facebookToken']}")

    monkeypatch.setattr(TenantRepository, "bot_secrets", fails)

    response = http.get(f"/chat/{bot}/tokens", headers=engine.auth)

    assert response.status_code == 500
    for part in ("failure-text-marker", SECRETS["facebookToken"]):
        assert part not in response.text and part not in caplog.text


# --- One key per client ---------------------------------------------------------------------------------------------

def test_the_key_for_one_client_does_not_reach_the_chatbots_of_another(http, operator, globex, engine, bot):
    theirs = new_bot(http, globex)["uuid"]

    for path in ("tokens", "rules", "tools"):
        foreign = http.get(f"/chat/{theirs}/{path}", headers=engine.auth)
        missing = http.get(f"/chat/{uuid4()}/{path}", headers=engine.auth)

        assert (foreign.status_code, foreign.json()["code"]) == (missing.status_code, missing.json()["code"]) == (
            404, 404)
        assert SECRETS["facebookToken"] not in foreign.text


def test_the_engine_needs_another_key_for_another_client(http, operator, globex, engine, bot):
    theirs = new_bot(http, globex)["uuid"]
    for_globex = Engine(globex.client_id)
    assert let_in(http, operator, globex.client_id, for_globex).status_code == 200

    assert http.get(f"/chat/{theirs}/tokens", headers=for_globex.auth).status_code == 200
    assert http.get(f"/chat/{bot}/tokens", headers=for_globex.auth).status_code == 404
    assert http.get(f"/chat/{bot}/tokens", headers=engine.auth).status_code == 200


def test_the_key_registered_for_one_client_does_not_sign_for_another(http, globex, engine):
    """The same key, saying it is for globex: it is not registered there."""
    as_globex = Engine(globex.client_id, engine.key)
    theirs = new_bot(http, globex)["uuid"]

    assert http.get(f"/chat/{theirs}/tokens", headers=as_globex.auth).status_code == 401


def test_the_envelope_says_whose_chatbot_it_is_and_that_is_all_the_engine_needs(http, operator, acme, bot, queue):
    """From the message in the queue to the tokens: the chatbot and its client come in the envelope."""
    engine_key = new_signing_key()
    payload = json.dumps({"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [{
        "field": "messages", "value": {
            "messaging_product": "whatsapp", "metadata": {"phone_number_id": "100000000000001"},
            "contacts": [{"profile": {"name": "Ana"}, "wa_id": "12025550143"}],
            "messages": [{"from": "12025550143", "id": "wamid.ONE", "type": "text", "text": {"body": "hola"}}]}}]}]})
    signature = "sha256=" + hmac.new(SECRETS["appSecret"].encode(), payload.encode(), hashlib.sha256).hexdigest()
    assert META.post(f"/chat/{bot}", content=payload, headers={"content-type": "application/json",
                                                               "X-Hub-Signature-256": signature}).status_code == 200
    (envelope,) = queue
    body = envelope["jwe_body"]
    assert (body["botId"], body["clientId"]) == (bot, str(acme.client_id))

    engine = Engine(body["clientId"], engine_key)
    assert let_in(http, operator, body["clientId"], engine).status_code == 200

    assert http.get(f"/chat/{body['botId']}/tokens", headers=engine.auth).json()["data"]["whatsappToken"] == SECRETS[
        "whatsappToken"]


# --- What the engine does not get -----------------------------------------------------------------------------------

@pytest.mark.parametrize("method,path", NOT_FOR_THE_ENGINE)
def test_the_engine_reaches_no_other_route(http, acme, operator, engine, bot, method, path):
    intent = http.get(f"/chat/{bot}/intents", headers=acme.auth).json()["data"][0]["uuid"]
    address = path.format(bot_id=bot, intent_id=intent, contact_id=uuid4(), client_id=acme.client_id,
                          kid=acme.kid)
    before = dump()

    response = http.request(method, address, headers=engine.auth, json=BODIES.get((method, path)))

    assert response.status_code == 403
    assert dump() == before


def test_every_route_is_either_for_the_engine_or_closed_to_it():
    assert len(NOT_FOR_THE_ENGINE) == 26
    assert sorted(FOR_THE_ENGINE + NOT_FOR_THE_ENGINE) == ROUTES


def test_a_client_does_not_get_its_own_tokens_back(http, acme, operator, bot, caplog):
    """They go in through the API and do not come out to whoever loaded them."""
    # Everything the service writes, down to its debug lines: development and staging keep those.
    caplog.set_level(logging.DEBUG, logger=app_module.settings.environment)
    for caller in (acme, operator):
        response = http.get(f"/chat/{bot}/tokens", headers=caller.auth)

        assert response.status_code == 403
        assert SECRETS["facebookToken"] not in response.text
    assert "handed to the response engine" not in caplog.text


def test_a_token_of_the_engine_is_valid_once(http, engine, bot):
    headers = engine.auth

    assert http.get(f"/chat/{bot}/tokens", headers=headers).status_code == 200
    assert http.get(f"/chat/{bot}/tokens", headers=headers).status_code == 401


# --- A trace of every time ------------------------------------------------------------------------------------------

def test_every_time_the_tokens_are_handed_out_leaves_a_trace_that_production_keeps(http, acme, engine, bot, caplog):
    # Everything the service writes, down to its debug lines: development and staging keep those.
    caplog.set_level(logging.DEBUG, logger=app_module.settings.environment)
    http.get(f"/chat/{bot}/tokens", headers=engine.auth)
    http.get(f"/chat/{bot}/tokens", headers=engine.auth)

    kept = [record.getMessage() for record in caplog.records
            if record.levelno >= logging.WARNING and "handed to the response engine" in record.getMessage()]
    assert kept == [f"Meta tokens of chatbot {bot} handed to the response engine: client {acme.client_id}, "
                    f"key {engine.kid}"] * 2
    for secret in SECRETS.values():
        assert secret not in caplog.text


def test_tokens_that_were_not_handed_out_leave_no_such_trace(http, globex, engine, caplog):
    # Everything the service writes, down to its debug lines: development and staging keep those.
    caplog.set_level(logging.DEBUG, logger=app_module.settings.environment)
    theirs = new_bot(http, globex)["uuid"]

    http.get(f"/chat/{theirs}/tokens", headers=engine.auth)

    assert "handed to the response engine" not in caplog.text


# --- Letting the engine in, and out -----------------------------------------------------------------------------------

def test_only_the_operator_lets_the_engine_in(http, acme, globex, engine):
    another = Engine(acme.client_id)

    for caller in (acme, globex, engine):
        added = http.post(f"/clients/{acme.client_id}/service-keys", headers=caller.auth,
                          json={"signingKey": another.public})
        removed = http.delete(f"/clients/{acme.client_id}/service-keys/{engine.kid}", headers=caller.auth)

        assert (added.status_code, removed.status_code) == (403, 403)
    assert [key["kid"] for key in Client.objects(uuid=acme.client_id).first().serviceKeys] == [engine.kid]


def test_the_client_sees_which_keys_of_the_engine_reach_its_chatbots(http, acme, operator, engine):
    mine = http.get("/keys", headers=acme.auth).json()["data"]
    listed = {client["name"]: client for client in http.get("/clients", headers=operator.auth).json()["data"]}

    assert (mine["keys"], mine["serviceKeys"]) == ([acme.kid], [engine.kid])
    assert listed["acme"]["serviceKeys"] == [engine.kid] and listed["operator"]["serviceKeys"] == []


def test_only_the_public_part_of_the_key_of_the_engine_is_stored(http, operator, acme, engine):
    stored = Client.objects(uuid=acme.client_id).first().serviceKeys

    assert [set(key) for key in stored] == [{"kty", "crv", "x", "y", "kid", "use", "alg"}]
    assert engine.key["d"] not in dump()


@pytest.mark.parametrize("key", [new_signing_key(), {"kty": "RSA", "n": "AQAB", "e": "AQAB"}, {"kty": "EC"}, "a-key"],
                         ids=["a private key", "not an elliptic curve key", "without coordinates", "not a key"])
def test_only_a_public_p256_key_is_accepted_for_the_engine(http, operator, acme, key):
    response = http.post(f"/clients/{acme.client_id}/service-keys", headers=operator.auth, json={"signingKey": key})

    assert response.status_code == 422
    assert Client.objects(uuid=acme.client_id).first().serviceKeys == []


@pytest.mark.parametrize("client_id", [str(uuid4()), "not-a-uuid"])
def test_the_engine_is_not_let_in_for_a_client_that_does_not_exist(http, operator, client_id):
    added = http.post(f"/clients/{client_id}/service-keys", headers=operator.auth,
                      json={"signingKey": Engine(client_id).public})
    removed = http.delete(f"/clients/{client_id}/service-keys/a-kid", headers=operator.auth)

    assert (added.status_code, removed.status_code) == (404, 404)


def test_removing_a_key_that_is_not_there_is_not_found(http, operator, acme, engine):
    response = http.delete(f"/clients/{acme.client_id}/service-keys/{acme.kid}", headers=operator.auth)

    assert response.status_code == 404
    assert len(Client.objects(uuid=acme.client_id).first().signingKeys) == 1


def test_the_engine_rotates_its_key_for_a_client_without_a_gap(http, operator, acme, engine, bot):
    new = Engine(acme.client_id)
    assert let_in(http, operator, acme.client_id, new).status_code == 200

    # Both work while the engine moves to the new one.
    assert [http.get(f"/chat/{bot}/tokens", headers=key.auth).status_code for key in (engine, new)] == [200, 200]

    taken_out = http.delete(f"/clients/{acme.client_id}/service-keys/{engine.kid}", headers=operator.auth)

    assert taken_out.status_code == 200
    assert [http.get(f"/chat/{bot}/tokens", headers=key.auth).status_code for key in (engine, new)] == [401, 200]


def test_the_engine_has_two_keys_for_a_client_at_most(http, operator, acme, engine):
    assert let_in(http, operator, acme.client_id, Engine(acme.client_id)).status_code == 200

    third = let_in(http, operator, acme.client_id, Engine(acme.client_id))

    assert (third.status_code, third.json()["detail"]) == (409, "TOO_MANY_KEYS")


def test_a_key_is_the_client_s_or_the_engine_s_never_both(http, operator, acme, engine):
    """Which list a key is in says who signs with it. In both, it would say two things."""
    as_engine = http.post(f"/clients/{acme.client_id}/service-keys", headers=operator.auth,
                          json={"signingKey": public_part(acme.key)})
    # Even holding its private part, which a client never has: without it, the proof alone turns it away.
    as_client = http.post("/keys", **acme.adding(engine.key))
    again = let_in(http, operator, acme.client_id, engine)

    for response in (as_engine, as_client, again):
        assert (response.status_code, response.json()["detail"]) == (409, "KEY_ALREADY_REGISTERED")
    client = Client.objects(uuid=acme.client_id).first()
    assert ([key["kid"] for key in client.signingKeys], [key["kid"] for key in client.serviceKeys]) == (
        [acme.kid], [engine.kid])


def test_who_signs_is_told_by_the_list_its_key_is_in(operator, acme, engine):
    assert find_signer(acme.client_id, acme.kid)[2] is Role.CLIENT
    assert find_signer(acme.client_id, engine.kid)[2] is Role.SERVICE
    assert find_signer(operator.client_id, operator.kid)[2] is Role.OPERATOR
    assert find_signer(acme.client_id, "another-kid") is None


def test_the_engine_does_not_get_in_for_a_client_that_was_shut_out(http, engine, bot, acme):
    Client.objects(uuid=acme.client_id).update_one(set__status=Status.DIS.value)

    assert http.get(f"/chat/{bot}/tokens", headers=engine.auth).status_code == 401


def test_deleting_a_client_takes_the_key_of_the_engine_with_it(http, operator, acme, engine, bot):
    deleted = http.delete(f"/clients/{acme.client_id}", headers=operator.auth)

    assert deleted.status_code == 200
    assert http.get(f"/chat/{bot}/tokens", headers=engine.auth).status_code == 401
    assert engine.kid not in dump()


def test_letting_the_engine_in_and_out_leaves_a_trace_that_production_keeps(http, operator, acme, caplog):
    engine = Engine(acme.client_id)

    let_in(http, operator, acme.client_id, engine)
    http.delete(f"/clients/{acme.client_id}/service-keys/{engine.kid}", headers=operator.auth)

    kept = [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]
    assert kept == [f"Service key {engine.kid} added to client {acme.client_id}",
                    f"Service key removed from client {acme.client_id}"]


# --- The last turns of a conversation, for the coordinator (RF15) ------------------------------------------------

def conversation(acme, bot, turns: int) -> Contact:
    """A contact of the chatbot who wrote `turns` times, and got two answers each time, a minute apart."""
    repo = TenantRepository(acme.client_id)
    contact = repo.add_contact(bot, Contact(firstName="Ana", waId="12025550143"))
    start = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
    for turn in range(turns):
        at = start + timedelta(minutes=turn)
        repo.record_message(contact, "in", f"wamid.IN{turn:02d}", "whatsapp", at, text=f"pregunta {turn}")
        for answer in range(2):
            repo.record_message(contact, "out", f"wamid.OUT{turn:02d}{answer}", "whatsapp",
                                at + timedelta(seconds=answer + 1), text=f"respuesta {turn}.{answer}",
                                in_reply_to=f"wamid.IN{turn:02d}")
    return contact


def turns_of(http, engine, bot, contact):
    return http.get(f"/chat/{bot}/contacts/{contact._uuid}/turns", headers=engine.auth)


def test_the_engine_gets_the_last_ten_turns_both_ways_and_oldest_first(http, acme, engine, bot):
    contact = conversation(acme, bot, turns=12)

    response = turns_of(http, engine, bot, contact)

    assert response.status_code == 200
    messages = response.json()["data"]["messages"]
    assert [m["messageId"] for m in messages if m["direction"] == "in"] == [f"wamid.IN{t:02d}" for t in range(2, 12)]
    assert len(messages) == 30
    assert (messages[0]["text"], messages[1]["inReplyTo"]) == ("pregunta 2", "wamid.IN02")
    assert response.headers["Cache-Control"] == "no-store"


def test_a_shorter_conversation_comes_whole(http, acme, engine, bot):
    contact = conversation(acme, bot, turns=3)

    assert len(turns_of(http, engine, bot, contact).json()["data"]["messages"]) == 9


def test_a_contact_who_never_wrote_has_no_turns(http, acme, engine, bot):
    contact = conversation(acme, bot, turns=0)

    assert turns_of(http, engine, bot, contact).json()["data"]["messages"] == []


def test_the_turns_of_a_contact_of_another_client_are_not_found(http, operator, acme, globex, engine, bot):
    theirs = new_bot(http, globex)["uuid"]
    contact = conversation(globex, theirs, turns=2)

    assert turns_of(http, engine, theirs, contact).status_code == 404
    assert turns_of(http, engine, bot, contact).status_code == 404


def test_a_client_does_not_get_the_turns_with_its_own_key(http, acme, bot):
    """It has the export of the contact for that: the turns are the engine's."""
    contact = conversation(acme, bot, turns=1)

    assert http.get(f"/chat/{bot}/contacts/{contact._uuid}/turns", headers=acme.auth).status_code == 403


def test_without_the_key_service_no_turn_is_handed_out(http, acme, engine, bot, key_service):
    contact = conversation(acme, bot, turns=1)
    key_service.down = True
    data_keys.forget()

    response = turns_of(http, engine, bot, contact)

    assert response.status_code == 503 and "pregunta" not in response.text


def test_every_time_the_turns_are_handed_out_leaves_a_trace_that_production_keeps(http, acme, engine, bot, caplog):
    contact = conversation(acme, bot, turns=2)
    caplog.set_level(logging.WARNING)

    turns_of(http, engine, bot, contact)

    assert f"Last turns of contact {contact._uuid} of chatbot {bot} handed to the response engine" in caplog.text
    assert "pregunta" not in caplog.text and "12025550143" not in caplog.text
