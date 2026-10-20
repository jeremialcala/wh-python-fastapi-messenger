# -*- coding: utf-8 -*-
"""
    What a client of the service does on its side, as a reference implementation. It needs neither the service's
    settings nor its database: copy it, or do the same with any JOSE library.

        python -m ops.client new-key <file>
            Writes a new private signing key to the file, owner-only, and prints its public part: that is what
            gets registered. The private key is never printed.

        python -m ops.client token <key file> <client id> <audience> <gateway keys file>
            Prints a token for one request. It is valid once and for 60 seconds, so build one per call:

                curl -H "Authorization: Bearer $(python -m ops.client token ...)" https://.../bot

            The gateway keys file is what GET /gateway/keys or the registration answer gave under "keys",
            saved as {"keys": [...]}.

        python -m ops.client add-key <key file> <new key file> <client id> <audience> <gateway keys file>
            Prints what POST /keys takes to add the new key, as {"token": ..., "body": {...}}: a token signed
            with the key the client has, and a body with the public part of the new one and the proof it signs
            for that same token. Like the token, it is good once and for 60 seconds.
"""
import json
import os
import sys
from uuid import uuid4

from shared.auth.client import build_token, key_proof, new_signing_key, public_part


def new_key(path: str) -> dict:
    key = new_signing_key()
    # O_EXCL: an existing key is never overwritten, losing it would lock the client out.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        json.dump(key, file)
    return public_part(key)


def _read(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def token(key_path: str, client_id: str, audience: str, gateway_keys_path: str, jti: str | None = None) -> str:
    # The last gateway key is the newest: while the gateway rotates, that is the one to move to.
    return build_token(_read(key_path), client_id, audience, _read(gateway_keys_path)["keys"][-1], jti=jti)


def add_key(key_path: str, new_key_path: str, client_id: str, audience: str, gateway_keys_path: str) -> dict:
    jti = str(uuid4())
    new_key = _read(new_key_path)
    return {"token": token(key_path, client_id, audience, gateway_keys_path, jti=jti),
            "body": {"signingKey": public_part(new_key), "proof": key_proof(new_key, client_id, audience, jti)}}


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if len(arguments) == 2 and arguments[0] == "new-key":
        print(json.dumps(new_key(arguments[1]), indent=2))
    elif len(arguments) == 5 and arguments[0] == "token":
        print(token(*arguments[1:]))
    elif len(arguments) == 6 and arguments[0] == "add-key":
        print(json.dumps(add_key(*arguments[1:])))
    else:
        raise SystemExit(__doc__)
