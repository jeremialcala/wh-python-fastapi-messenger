# -*- coding: utf-8 -*-
"""
    The gateway's key file, the one GATEWAY_KEYS_FILE points to. Run it on the machine where the key will live:
    the private key is written to the file, owner-only, and never printed. It needs neither settings nor database.

        python -m ops.gateway_key generate <file>     # adds a new key pair; creates the file if it is not there
        python -m ops.gateway_key show <file>         # the public keys, the only thing a client is given
        python -m ops.gateway_key drop <file> <kid>   # removes a key pair once nobody encrypts to it

    To rotate: generate, restart the service, give the clients the new public key, and drop the old one when
    they have moved. The service reads the file when it starts.
"""
import json
import os
import sys

from auth.gateway_keys import GatewayKeys, new_key, public_part, read_file, write_file


def generate(path: str) -> dict:
    keys = read_file(path) if os.path.exists(path) else []
    key = new_key()
    write_file(path, keys + [key])
    return public_part(key)


def show(path: str) -> dict:
    return GatewayKeys.load(path).public_set()


def drop(path: str, kid: str) -> dict:
    keys = read_file(path)
    remaining = [key for key in keys if key.get("kid") != kid]
    if len(remaining) == len(keys):
        raise SystemExit(f"There is no key {kid} in the file")
    if not remaining:
        raise SystemExit("That is the only key: generate the new one first")
    write_file(path, remaining)
    return {"keys": [public_part(key) for key in remaining]}


if __name__ == "__main__":
    commands = {"generate": (generate, 1), "show": (show, 1), "drop": (drop, 2)}
    arguments = sys.argv[1:]
    if not arguments or arguments[0] not in commands or len(arguments) - 1 != commands[arguments[0]][1]:
        raise SystemExit(__doc__)
    print(json.dumps(commands[arguments[0]][0](*arguments[1:]), indent=2))
