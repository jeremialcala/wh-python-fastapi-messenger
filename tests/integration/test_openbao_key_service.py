# -*- coding: utf-8 -*-
"""
    The client of the key service against a real OpenBao, set up the way the one in production is: the Transit
    engine with a key derived per client, and an AppRole whose policy only lets it ask for a data key and open one.

    It needs an OpenBao in development mode to configure:

        docker run --rm -p 127.0.0.1:18200:8200 -e BAO_DEV_ROOT_TOKEN_ID=dev-root openbao/openbao:2.7.1
        OPENBAO_TEST_ADDR=http://127.0.0.1:18200 OPENBAO_TEST_TOKEN=dev-root pytest tests/integration

    Without those two variables the tests are skipped; with OPENBAO_TEST_REQUIRED set they fail instead, which is
    how the pipeline makes sure they are not skipped there.
"""
import os
import pathlib
from uuid import uuid4

import pytest
import requests

from crypto.key_service import KeyServiceUnavailable, OpenBaoKeyService

ADDRESS, ROOT_TOKEN = os.environ.get("OPENBAO_TEST_ADDR"), os.environ.get("OPENBAO_TEST_TOKEN")
POLICY = """
path "transit/datakey/plaintext/clientes" { capabilities = ["update"] }
path "transit/decrypt/clientes" { capabilities = ["update"] }
"""

def as_root(method: str, path: str, body: dict | None = None, allowed=(200, 204)) -> dict:
    response = requests.request(method, f"{ADDRESS}/v1/{path}", json=body, headers={"X-Vault-Token": ROOT_TOKEN},
                                timeout=5)
    assert response.status_code in allowed, (path, response.status_code)
    return response.json() if response.content else {}


def issue_secret_id(path: str) -> None:
    """Asks the server for a new secret id and leaves it where the gateway reads it from: a file."""
    issued = as_root("POST", "auth/approle/role/gateway/secret-id")["data"]
    pathlib.Path(path).write_text(issued["secret_id"] + "\n", encoding="utf-8")


@pytest.fixture(scope="module")
def approle(tmp_path_factory):
    """Configures the server like the one in production and returns the role id and the secret id file."""
    if not (ADDRESS and ROOT_TOKEN):
        if os.environ.get("OPENBAO_TEST_REQUIRED"):
            pytest.fail("OPENBAO_TEST_ADDR and OPENBAO_TEST_TOKEN are required here")
        pytest.skip("No OpenBao to test against: set OPENBAO_TEST_ADDR and OPENBAO_TEST_TOKEN")
    # 400 is "already there": the same server may be used for more than one run.
    as_root("POST", "sys/mounts/transit", {"type": "transit"}, allowed=(200, 204, 400))
    as_root("POST", "transit/keys/clientes", {"type": "aes256-gcm96", "derived": True})
    as_root("PUT", "sys/policies/acl/gateway", {"policy": POLICY})
    as_root("POST", "sys/auth/approle", {"type": "approle"}, allowed=(200, 204, 400))
    as_root("POST", "auth/approle/role/gateway", {"token_policies": "gateway", "token_ttl": "20m"})
    role_id = as_root("GET", "auth/approle/role/gateway/role-id")["data"]["role_id"]
    secret_file = str(tmp_path_factory.mktemp("openbao") / "secret-id")
    issue_secret_id(secret_file)
    return role_id, secret_file


@pytest.fixture
def service(approle):
    return OpenBaoKeyService(ADDRESS, *approle)


def test_a_data_key_is_32_bytes_and_comes_wrapped(service):
    key, wrapped = service.new_data_key(uuid4())

    assert len(key) == 32
    assert wrapped.startswith("vault:v1:") and key.hex() not in wrapped


def test_a_wrapped_key_opens_for_its_client(service):
    client = uuid4()
    key, wrapped = service.new_data_key(client)

    assert service.unwrap(client, wrapped) == key


def test_a_wrapped_key_does_not_open_for_another_client(service):
    _, wrapped = service.new_data_key(uuid4())

    with pytest.raises(KeyServiceUnavailable):
        service.unwrap(uuid4(), wrapped)


def test_every_data_key_is_different(service):
    client = uuid4()

    assert service.new_data_key(client)[0] != service.new_data_key(client)[0]


def test_the_client_logs_in_again_when_its_token_is_revoked(service):
    client = uuid4()
    key, wrapped = service.new_data_key(client)

    as_root("POST", "auth/token/revoke", {"token": service._token})

    assert service.unwrap(client, wrapped) == key


def test_the_client_logs_in_again_when_its_token_is_about_to_expire(service):
    client = uuid4()
    key, wrapped = service.new_data_key(client)
    first, service._token_expires = service._token, 0.0

    assert service.unwrap(client, wrapped) == key
    assert service._token != first


def test_the_secret_id_is_read_again_each_time_so_it_can_be_rotated(service, approle):
    client = uuid4()
    key, wrapped = service.new_data_key(client)
    issue_secret_id(approle[1])
    as_root("POST", "auth/token/revoke", {"token": service._token})

    assert service.unwrap(client, wrapped) == key


def test_the_policy_of_the_gateway_reaches_nothing_else(service):
    service.new_data_key(uuid4())
    headers = {"X-Vault-Token": service._token}

    for method, path in (("GET", "transit/keys/clientes"), ("GET", "transit/export/encryption-key/clientes"),
                         ("POST", "transit/keys/clientes/rotate"), ("DELETE", "transit/keys/clientes"),
                         ("LIST", "transit/keys"), ("GET", "sys/mounts"), ("POST", "transit/encrypt/clientes")):
        response = requests.request(method, f"{ADDRESS}/v1/{path}", headers=headers, json={}, timeout=5)
        assert response.status_code == 403, (method, path)


@pytest.mark.parametrize("problem", ["wrong secret", "no secret file", "wrong role", "nobody listening"])
def test_a_key_service_that_cannot_be_used_is_reported_and_nothing_else(approle, tmp_path, problem):
    role_id, secret_file = approle
    wrong = tmp_path / "secret-id"
    wrong.write_text("not-the-secret", encoding="utf-8")
    service = {
        "wrong secret": OpenBaoKeyService(ADDRESS, role_id, str(wrong)),
        "no secret file": OpenBaoKeyService(ADDRESS, role_id, str(tmp_path / "missing")),
        "wrong role": OpenBaoKeyService(ADDRESS, "not-a-role", secret_file),
        "nobody listening": OpenBaoKeyService("http://127.0.0.1:1", role_id, secret_file),
    }[problem]

    with pytest.raises(KeyServiceUnavailable) as failure:
        service.new_data_key(uuid4())

    # What is reported goes to the log: neither the secret nor the address may be in it.
    assert "not-the-secret" not in str(failure.value) and "127.0.0.1" not in str(failure.value)
