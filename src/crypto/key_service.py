# -*- coding: utf-8 -*-
"""
    The key service: where the master key lives. The gateway never sees that key; it asks the service to make a
    data key for a client and to open one it wrapped before. It is an OpenBao with the Transit engine and a key
    derived per client, so a data key cannot be opened in the name of another client.
"""
import base64
import logging
import time
from uuid import UUID

import requests

log = logging.getLogger(__name__)

KEY_BYTES = 32
TIMEOUT = 3     # seconds: a request waiting for a key must not hang
RENEW_BEFORE = 30  # seconds before the token expires at which a new one is asked for


class KeyServiceUnavailable(Exception):
    """
        The key service did not answer, or refused. Nothing encrypted can be read or written until it does:
        the caller answers 503, never with data in clear.
    """


class OpenBaoKeyService:

    def __init__(self, address: str, role_id: str, secret_id_file: str, ca_file: str | None = None,
                 key: str = "clientes", mount: str = "transit"):
        self._address = address.rstrip("/")
        self._role_id = role_id
        self._secret_id_file = secret_id_file
        self._verify = ca_file or True
        self._key = key
        self._mount = mount
        self._token = None
        self._token_expires = 0.0

    @staticmethod
    def _context(client_id: UUID) -> str:
        # What the master key is derived with. A data key wrapped for a client only opens with its id.
        return base64.b64encode(str(client_id).encode()).decode()

    def _post(self, path: str, body: dict, token: str | None = None) -> requests.Response:
        headers = {"X-Vault-Token": token} if token else {}
        try:
            return requests.post(f"{self._address}/v1/{path}", json=body, headers=headers,
                                 timeout=TIMEOUT, verify=self._verify)
        except (requests.RequestException, OSError) as e:
            # Only the kind of failure: the text of these exceptions can carry the address and more.
            raise KeyServiceUnavailable(type(e).__name__) from None

    @staticmethod
    def _read(response: requests.Response, *path):
        """
            A field of an answer of the key service. An answer without it is the key service failing, not the
            gateway: it is told apart from any other error so that it ends in a 503 too.
        """
        try:
            value = response.json()
            for key in path:
                value = value[key]
            return value
        except (ValueError, KeyError, TypeError, IndexError):
            raise KeyServiceUnavailable("unexpected answer") from None

    def _login(self) -> str:
        try:
            # Read every time, so the credential can be rotated without restarting the service.
            with open(self._secret_id_file, "r", encoding="utf-8") as file:
                secret_id = file.read().strip()
        except OSError as e:
            raise KeyServiceUnavailable(type(e).__name__) from None
        response = self._post("auth/approle/login", {"role_id": self._role_id, "secret_id": secret_id})
        if response.status_code != 200:
            raise KeyServiceUnavailable(f"login refused: {response.status_code}")
        self._token = self._read(response, "auth", "client_token")
        lease = self._read(response, "auth").get("lease_duration", 0)
        self._token_expires = time.monotonic() + (lease if isinstance(lease, (int, float)) else 0) - RENEW_BEFORE
        return self._token

    def _call(self, operation: str, body: dict) -> requests.Response:
        token = self._token if self._token and time.monotonic() < self._token_expires else self._login()
        response = self._post(f"{self._mount}/{operation}/{self._key}", body, token)
        if response.status_code == 403:
            # The token may have been revoked before its time: once more with a new one.
            response = self._post(f"{self._mount}/{operation}/{self._key}", body, self._login())
        if response.status_code != 200:
            raise KeyServiceUnavailable(f"{operation} refused: {response.status_code}")
        return response

    @classmethod
    def _key_in(cls, response: requests.Response) -> bytes:
        try:
            key = base64.b64decode(cls._read(response, "data", "plaintext"), validate=True)
        except (ValueError, TypeError):
            raise KeyServiceUnavailable("unexpected answer") from None
        if len(key) != KEY_BYTES:
            raise KeyServiceUnavailable("unexpected answer")
        return key

    def new_data_key(self, client_id: UUID) -> tuple:
        """A new data key for the client: the key itself, to use now, and wrapped, the only form that is stored."""
        response = self._call("datakey/plaintext", {"context": self._context(client_id), "bits": KEY_BYTES * 8})
        wrapped = self._read(response, "data", "ciphertext")
        if not isinstance(wrapped, str) or not wrapped:
            raise KeyServiceUnavailable("unexpected answer")
        return self._key_in(response), wrapped

    def unwrap(self, client_id: UUID, wrapped: str) -> bytes:
        return self._key_in(self._call("decrypt", {"context": self._context(client_id), "ciphertext": wrapped}))
