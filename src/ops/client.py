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
"""
import json
import os
import sys

from auth.client import build_token, new_signing_key, public_part


def new_key(path: str) -> dict:
    key = new_signing_key()
    # O_EXCL: an existing key is never overwritten, losing it would lock the client out.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        json.dump(key, file)
    return public_part(key)


def token(key_path: str, client_id: str, audience: str, gateway_keys_path: str) -> str:
    with open(key_path, "r", encoding="utf-8") as file:
        key = json.load(file)
    with open(gateway_keys_path, "r", encoding="utf-8") as file:
        # The last one is the newest: while the gateway rotates, that is the one to move to.
        gateway_key = json.load(file)["keys"][-1]
    return build_token(key, client_id, audience, gateway_key)


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if len(arguments) == 2 and arguments[0] == "new-key":
        print(json.dumps(new_key(arguments[1]), indent=2))
    elif len(arguments) == 5 and arguments[0] == "token":
        print(token(*arguments[1:]))
    else:
        raise SystemExit(__doc__)
