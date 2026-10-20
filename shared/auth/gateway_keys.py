# -*- coding: utf-8 -*-
"""
    The gateway's own key pairs. Clients encrypt their tokens to the public half, so only the gateway reads them.
    They live in a JWK Set file outside the repository and the image: one key normally, two while rotating.
"""
import json
import os

from jwcrypto import jwk
from jwcrypto.common import base64url_decode

MIN_BITS = 2048
NEW_KEY_BITS = 3072
ALGORITHM = "RSA-OAEP-256"


def new_key() -> dict:
    """A new private key as a JWK. Its kid is its thumbprint, so two keys never share one."""
    key = jwk.JWK.generate(kty="RSA", size=NEW_KEY_BITS)
    return {**json.loads(key.export_private()), "kid": key.thumbprint(), "use": "enc", "alg": ALGORITHM}


def public_part(private: dict) -> dict:
    return {name: private[name] for name in ("kty", "n", "e", "kid", "use", "alg") if name in private}


def read_file(path: str) -> list:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)["keys"]


def write_file(path: str, keys: list) -> None:
    """Owner-only from the first byte, and replaced in one step so a reader never sees half a file."""
    temporary = f"{path}.new"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        json.dump({"keys": keys}, file)
    os.replace(temporary, path)


class GatewayKeys:

    def __init__(self, keys: list):
        self._private = {}
        for entry in keys:
            if (entry.get("kty") != "RSA" or not entry.get("kid") or "d" not in entry
                    or len(base64url_decode(entry["n"])) * 8 < MIN_BITS):
                raise ValueError("Every gateway key must be a private RSA JWK with a kid and at least 2048 bits")
            self._private[entry["kid"]] = jwk.JWK(**entry)
        if not self._private:
            raise ValueError("The gateway has no key: clients could not encrypt their tokens to it")
        self._public = [public_part(entry) for entry in keys]

    @classmethod
    def load(cls, path: str) -> "GatewayKeys":
        return cls(read_file(path))

    def private(self, kid) -> jwk.JWK | None:
        return self._private.get(kid) if isinstance(kid, str) else None

    def public_set(self) -> dict:
        """What a client needs to encrypt a token: safe to hand out."""
        return {"keys": self._public}
