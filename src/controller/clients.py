# -*- coding: utf8 -*-
"""
    The registry of clients and of their signing keys, as the API sees it. Only public keys come in and go out:
    a client's private key never reaches the gateway.
"""
import logging

from fastapi import HTTPException, status

from auth.client_keys import public_signing_key
from auth.gateway_keys import GatewayKeys
from classes import Client, ClientRequest, ResponseData, Settings, SigningKeyRequest
from enums import Status
from repository import (Conflict, NotFound, add_signing_key, get_client, list_clients, register_client,
                        remove_signing_key)

__all__ = ["ctr_register_client", "ctr_list_clients", "ctr_get_client", "ctr_add_signing_key",
           "ctr_remove_signing_key", "ctr_gateway_keys"]

settings = Settings()
log = logging.getLogger(settings.environment)

CONFLICTS = {
    "name taken": "CLIENT_NAME_TAKEN",
    "key already registered": "KEY_ALREADY_REGISTERED",
    "too many keys": "TOO_MANY_KEYS",
    "last key": "LAST_KEY",
}


def client_info(client: Client) -> dict:
    return {
        "uuid": str(client.uuid),
        "name": client.name,
        "role": client.role,
        "status": Status(client.status).name,
        "keys": [key.get("kid") for key in client.signingKeys],
    }


def gateway_info(gateway_keys: GatewayKeys) -> dict:
    """What a client needs to build a token for this gateway. All of it is public."""
    return {"audience": settings.gateway_audience, "keys": gateway_keys.public_set()["keys"]}


def _validated(request: SigningKeyRequest) -> dict:
    try:
        return public_signing_key(request.signingKey)
    except ValueError as e:
        # The texts are written in auth.client_keys: none of them repeats what was sent.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from None


def _conflict(e: Conflict) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=CONFLICTS.get(str(e), "CONFLICT"))


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HTTP_404_NOT_FOUND")


async def ctr_register_client(request: ClientRequest, gateway_keys: GatewayKeys) -> ResponseData:
    key = _validated(request)
    try:
        client = register_client(request.name, key)
    except Conflict as e:
        raise _conflict(e) from None
    log.info(f"Client registered: {client.uuid}")
    return ResponseData(data={**client_info(client), "gateway": gateway_info(gateway_keys)})


async def ctr_list_clients() -> ResponseData:
    return ResponseData(data=[client_info(client) for client in list_clients()])


async def ctr_get_client(client_id) -> ResponseData:
    try:
        return ResponseData(data=client_info(get_client(client_id)))
    except NotFound:
        raise _not_found() from None


async def ctr_add_signing_key(client_id, request: SigningKeyRequest) -> ResponseData:
    key = _validated(request)
    try:
        client = add_signing_key(client_id, key)
    except NotFound:
        raise _not_found() from None
    except Conflict as e:
        raise _conflict(e) from None
    log.info(f"Signing key added to client {client.uuid}")
    return ResponseData(data=client_info(client))


async def ctr_remove_signing_key(client_id, kid: str, keep_one: bool) -> ResponseData:
    try:
        client = remove_signing_key(client_id, kid, keep_one=keep_one)
    except NotFound:
        raise _not_found() from None
    except Conflict as e:
        raise _conflict(e) from None
    log.info(f"Signing key removed from client {client.uuid}")
    return ResponseData(data=client_info(client))


async def ctr_gateway_keys(gateway_keys: GatewayKeys) -> ResponseData:
    return ResponseData(data=gateway_info(gateway_keys))
