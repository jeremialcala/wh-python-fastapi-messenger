# -*- coding: utf-8 -*-
"""
    Registers a public signing key for the operator's client. It is how the first one gets in: every endpoint
    asks for a token, and nobody can sign one before a key is registered. It runs with the service's settings,
    against its database.

        python -m ops.operator_key <file with the operator's public JWK>

    The operator keeps the private key. With two keys already registered it refuses: remove one through the API.
"""
import json
import sys

from auth.client_keys import public_signing_key
from repository import Conflict, add_signing_key, operator_client


def register(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        key = public_signing_key(json.load(file))
    client = operator_client()
    try:
        add_signing_key(client.uuid, key)
    except Conflict as e:
        raise SystemExit(f"Not registered: {e}") from None
    return {"client": str(client.uuid), "kid": key["kid"]}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    try:
        print(json.dumps(register(sys.argv[1]), indent=2))
    except ValueError as e:
        raise SystemExit(f"Not registered: {e}") from None
