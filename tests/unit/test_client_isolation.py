# -*- coding: utf-8 -*-
"""
    The isolation between clients, seen from outside: every management route is called for a chatbot of client A
    with the credentials of client B, and each one must answer 404, exactly as for a chatbot that does not exist.

    The routes are taken from the application, so a new one that is not covered here fails the test.
"""
import os
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import app as app_module
from classes import ChatBot, ChatbotPhone, Intent, Rule
from repository import TenantRepository

ADMIN = {"X-API-Key": os.environ["ADMIN_API_KEY"]}

INTENT = {"name": "check_order", "description": "Order status"}
BODIES = {
    ("POST", "/chat/{bot_id}/phones"): {"phoneNumber": "12025550101", "phoneId": "100000000000001"},
    ("POST", "/chat/{bot_id}/rules"): {"rules": ["Be kind"]},
    ("POST", "/chat/{bot_id}/intents"): INTENT,
    ("PUT", "/chat/{bot_id}/intents/{intent_id}"): INTENT,
}
PUBLIC = {("GET", "/chat/{bot_id}"), ("POST", "/chat/{bot_id}"), ("GET", "/health")}
ROUTES = sorted((method, route.path) for route in app_module.app.routes if isinstance(route, APIRoute)
                for method in route.methods)
BOT_ROUTES = [route for route in ROUTES if route not in PUBLIC and "{bot_id}" in route[1]]


@pytest.fixture
def clients():
    """Returns a function that gives an HTTP client authenticated as the given client."""
    def acting_as(repo: TenantRepository) -> TestClient:
        app_module.app.dependency_overrides[app_module.get_repository] = lambda: repo
        return TestClient(app_module.app)

    yield acting_as
    app_module.app.dependency_overrides.clear()


@pytest.fixture
def owner():
    return TenantRepository(uuid4())


@pytest.fixture
def stranger():
    return TenantRepository(uuid4())


@pytest.fixture
def stored(owner):
    bot = owner.add_bot(ChatBot(name="Bot", role="Sales Assistant", description="A test chatbot", tone="helpful"))
    owner.add_phone(bot.uuid, ChatbotPhone(phoneNumber="12025550101", phoneId="100000000000001"))
    owner.add_rules(bot.uuid, ["Be kind"])
    intent = owner.add_intent(bot.uuid, Intent(name="check_order", description="Order status"))
    return bot, intent


def call(http: TestClient, method: str, path: str, bot_id, intent_id):
    return http.request(method, path.format(bot_id=bot_id, intent_id=intent_id), json=BODIES.get((method, path)))


def test_every_route_of_a_chatbot_is_covered():
    assert len(BOT_ROUTES) == 11
    assert [route for route in ROUTES if route not in PUBLIC and route not in BOT_ROUTES] == [("POST", "/bot")]


@pytest.mark.parametrize("method,path", BOT_ROUTES)
def test_the_owner_reaches_its_chatbot(clients, owner, stored, method, path):
    bot, intent = stored

    assert call(clients(owner), method, path, bot.uuid, intent.uuid).status_code == 200


@pytest.mark.parametrize("method,path", BOT_ROUTES)
def test_another_client_gets_not_found(clients, stranger, stored, method, path):
    bot, intent = stored
    before = {document: document.objects.count() for document in (ChatbotPhone, Rule, Intent)}

    response = call(clients(stranger), method, path, bot.uuid, intent.uuid)

    assert response.status_code == 404
    assert {document: document.objects.count() for document in before} == before
    assert Intent.objects(uuid=intent.uuid).first().status == intent.status


@pytest.mark.parametrize("method,path", BOT_ROUTES)
def test_a_chatbot_of_another_client_answers_like_one_that_does_not_exist(clients, stranger, stored, method, path):
    bot, intent = stored
    http = clients(stranger)

    foreign = call(http, method, path, bot.uuid, intent.uuid)
    missing = call(http, method, path, uuid4(), intent.uuid)

    assert (foreign.status_code, foreign.json()["code"]) == (missing.status_code, missing.json()["code"]) == (404, 404)


@pytest.mark.parametrize("method,path", [route for route in BOT_ROUTES if "{intent_id}" in route[1]])
def test_an_intent_is_not_reachable_through_another_chatbot(clients, owner, stored, method, path):
    _, intent = stored
    other = owner.add_bot(ChatBot(name="Other", role="r", description="d", tone="t"))

    assert call(clients(owner), method, path, other.uuid, intent.uuid).status_code == 404


def test_a_chatbot_belongs_to_whoever_creates_it(clients, owner, stranger):
    created = clients(owner).post("/bot", json={"name": "Mine", "role": "Sales Assistant",
                                                "description": "A test chatbot", "tone": "helpful"})
    bot_id = created.json()["data"]["uuid"]

    assert created.status_code == 200
    assert ChatBot.objects(uuid=bot_id).first().clientId == owner.client_id
    assert clients(owner).get(f"/chat/{bot_id}/info").status_code == 200
    assert clients(stranger).get(f"/chat/{bot_id}/info").status_code == 404


def test_the_admin_key_works_for_the_operator_client(owner, stored):
    """Until clients have their own tokens, the admin key reaches the operator's chatbots and nobody else's."""
    bot, _ = stored
    http = TestClient(app_module.app)

    created = http.post("/bot", headers=ADMIN, json={"name": "Operator bot", "role": "Sales Assistant",
                                                     "description": "A test chatbot", "tone": "helpful"})

    assert http.get(f"/chat/{created.json()['data']['uuid']}/info", headers=ADMIN).status_code == 200
    assert http.get(f"/chat/{bot.uuid}/info", headers=ADMIN).status_code == 404
