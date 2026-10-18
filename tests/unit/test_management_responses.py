# -*- coding: utf-8 -*-
"""
    The management controllers build their own Response and replace its body afterwards. These tests go through
    the real controller and the real repository: the body has to reach the client, whole.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app as app_module
from classes import ChatBot
from repository import TenantRepository


@pytest.fixture
def client():
    return TestClient(app_module.app)


def test_a_controller_response_reaches_the_client(client, operator):
    response = client.get(f"/chat/{uuid4()}/info", headers=operator.auth)

    assert response.status_code == 404
    assert response.json()["code"] == 404


def test_content_length_counts_bytes_not_characters(client, operator):
    bot = TenantRepository(operator.client_id).add_bot(
        ChatBot(name="Ñandú", role="Sales Assistant", description="A test chatbot", tone="helpful"))

    response = client.get(f"/chat/{bot.uuid}/info", headers=operator.auth)

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Ñandú"
    assert int(response.headers["content-length"]) == len(response.content)
