# -*- coding: utf-8 -*-
"""
    The management controllers build their own Response and replace its body afterwards. These tests go through
    the real controller, with only the database lookup replaced: the body has to reach the client, whole.
"""
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app as app_module
from classes import ChatBot

ADMIN = {"X-API-Key": os.environ["ADMIN_API_KEY"]}


@pytest.fixture
def client():
    return TestClient(app_module.app)


def test_a_controller_response_reaches_the_client(client, monkeypatch):
    monkeypatch.setattr(ChatBot, "get_chatbot_by_uuid", AsyncMock(side_effect=ValueError))

    response = client.get(f"/chat/{uuid4()}/info", headers=ADMIN)

    assert response.status_code == 404
    assert response.json()["code"] == 404


def test_content_length_counts_bytes_not_characters(client, monkeypatch):
    bot = SimpleNamespace(chatbot_info=lambda: {"name": "Ñandú"})
    monkeypatch.setattr(ChatBot, "get_chatbot_by_uuid", AsyncMock(return_value=bot))

    response = client.get(f"/chat/{uuid4()}/info", headers=ADMIN)

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Ñandú"
    assert int(response.headers["content-length"]) == len(response.content)
