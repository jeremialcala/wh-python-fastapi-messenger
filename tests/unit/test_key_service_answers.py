# -*- coding: utf-8 -*-
"""
    What the client of the key service does with an answer it cannot use. Against a real OpenBao, the answers are
    the good ones: tests/integration/test_openbao_key_service.py. Here the HTTP layer is replaced, to give it the
    ones a key service should never send.
"""
import base64
from types import SimpleNamespace
from uuid import uuid4

import pytest

import crypto.key_service as key_service
from crypto.key_service import KeyServiceUnavailable, OpenBaoKeyService

KEY = base64.b64encode(b"k" * 32).decode()
LOGIN = {"auth": {"client_token": "token", "lease_duration": 3600}}


def answer(body, status_code=200):
    def read():
        if isinstance(body, Exception):
            raise body
        return body
    return SimpleNamespace(status_code=status_code, json=read)


@pytest.fixture
def service(tmp_path):
    secret_id = tmp_path / "secret-id"
    secret_id.write_text("secret", encoding="utf-8")
    return OpenBaoKeyService("https://andvari.example", "role", str(secret_id))


def replying(monkeypatch, login, operation):
    def post(url, **kwargs):
        return answer(*login) if url.endswith("auth/approle/login") else answer(*operation)
    monkeypatch.setattr(key_service.requests, "post", post)


def test_good_answers_give_the_key(service, monkeypatch):
    replying(monkeypatch, (LOGIN,), ({"data": {"plaintext": KEY, "ciphertext": "vault:v1:abc"}},))

    assert service.new_data_key(uuid4()) == (b"k" * 32, "vault:v1:abc")
    assert service.unwrap(uuid4(), "vault:v1:abc") == b"k" * 32


@pytest.mark.parametrize("login", [
    (ValueError("not json"),), ({},), ({"auth": None},), ({"auth": {}},), ([],),
], ids=["not json", "no auth", "auth null", "no token", "a list"])
def test_a_login_answer_without_a_token_is_the_key_service_failing(service, monkeypatch, login):
    """Found in the dual review of Gate 2: it ended in a 500, as if the gateway had failed."""
    replying(monkeypatch, login, ({"data": {"plaintext": KEY, "ciphertext": "vault:v1:abc"}},))

    with pytest.raises(KeyServiceUnavailable):
        service.unwrap(uuid4(), "vault:v1:abc")


@pytest.mark.parametrize("operation", [
    (ValueError("not json"),), ({},), ({"data": None},), ({"data": {}},), ({"data": {"plaintext": "%%%"}},),
    ({"data": {"plaintext": base64.b64encode(b"short").decode(), "ciphertext": "vault:v1:abc"}},),
    ({"data": {"plaintext": KEY}},), ({"data": {"plaintext": KEY, "ciphertext": ""}},),
], ids=["not json", "no data", "data null", "no key", "not base64", "not 32 bytes", "no wrapped key",
        "empty wrapped key"])
def test_an_answer_without_a_usable_key_is_the_key_service_failing(service, monkeypatch, operation):
    replying(monkeypatch, (LOGIN,), operation)

    with pytest.raises(KeyServiceUnavailable):
        service.new_data_key(uuid4())


def test_a_refusal_says_which_operation_and_with_what_status(service, monkeypatch):
    """A refusal is told apart from a key service that does not answer: one is fixed in the key service."""
    replying(monkeypatch, (LOGIN,), ({"errors": ["the text of the key service"]}, 400))

    with pytest.raises(KeyServiceUnavailable) as failure:
        service.unwrap(uuid4(), "vault:v1:abc")

    assert str(failure.value) == "decrypt refused: 400"
