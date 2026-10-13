# -*- coding: utf-8 -*-
"""
    The registry of clients: who they are and which public keys they sign their tokens with. It is the operator's
    side of the data layer, and what authentication looks a signer up in.
"""
from datetime import datetime
from uuid import UUID, uuid4

from mongoengine.errors import NotUniqueError

from classes import Client
from enums import Role, Status

from .errors import Conflict, NotFound
from .tenant import as_uuid

OPERATOR_NAME = "operator"
# Two at most: the one in use and the one that replaces it, so a client rotates without a gap.
MAX_SIGNING_KEYS = 2


def operator_client() -> Client:
    """
        The operator's own client. It owns the chatbots that existed before clients did, and it is who registers
        the others. It is created on first use; the name is unique, so several workers starting at once end up
        with the same one.
    """
    client = Client.objects(name=OPERATOR_NAME).first()
    if client is None:
        now = datetime.now()
        client = Client.objects(name=OPERATOR_NAME).upsert_one(
            set_on_insert__uuid=uuid4(),
            set_on_insert__role=Role.OPERATOR.value,
            set_on_insert__createdAt=now,
            set_on_insert__status=Status.ACT.value,
            set_on_insert__statusDate=now
        )
    return client


def register_client(name: str, signing_key: dict) -> Client:
    """`signing_key` must already be a validated public key: see auth.client_keys."""
    client = Client(name=name, role=Role.CLIENT.value, status=Status.ACT.value, signingKeys=[signing_key])
    try:
        client.save()
    except NotUniqueError:
        raise Conflict("name taken") from None
    return client


def get_client(client_id) -> Client:
    client = Client.objects(uuid=as_uuid(client_id)).first()
    if client is None:
        raise NotFound(client_id)
    return client


def list_clients() -> list:
    return list(Client.objects.order_by("createdAt"))


def add_signing_key(client_id, signing_key: dict) -> Client:
    client = get_client(client_id)
    if any(key.get("kid") == signing_key["kid"] for key in client.signingKeys):
        raise Conflict("key already registered")
    if len(client.signingKeys) >= MAX_SIGNING_KEYS:
        raise Conflict("too many keys")
    client.signingKeys.append(signing_key)
    client.save()
    return client


def remove_signing_key(client_id, kid: str, keep_one: bool = False) -> Client:
    """
        Revoking a key is deleting it. `keep_one` is for a client acting on itself: without it, it could leave
        itself with no way back in.
    """
    client = get_client(client_id)
    remaining = [key for key in client.signingKeys if key.get("kid") != kid]
    if len(remaining) == len(client.signingKeys):
        raise NotFound(kid)
    if keep_one and not remaining:
        raise Conflict("last key")
    client.signingKeys = remaining
    client.save()
    return client


def find_signer(client_id: UUID, kid: str) -> tuple | None:
    """The active client and the public key it registered under that kid, or None."""
    client = Client.objects(uuid=client_id, status=Status.ACT.value).first()
    if client is None:
        return None
    for key in client.signingKeys:
        if key.get("kid") == kid:
            return client, dict(key)
    return None
