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

from . import data_keys, erasures
from .errors import Conflict, NotFound
from .tenant import TenantRepository, as_uuid
from .tokens import forget_tokens

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


def _add_key(client_id, keys: str, key: dict) -> Client:
    """
        Adds a public key to one of the two lists of a client. A key is in one list at most: which list it is in
        is what says whether whoever signs with it is the client or the response engine.
    """
    client = get_client(client_id)
    if any(known.get("kid") == key["kid"] for known in [*client.signingKeys, *client.serviceKeys]):
        raise Conflict("key already registered")
    if len(getattr(client, keys)) >= MAX_SIGNING_KEYS:
        raise Conflict("too many keys")
    getattr(client, keys).append(key)
    client.save()
    return client


def _remove_key(client_id, keys: str, kid: str, keep_one: bool) -> Client:
    client = get_client(client_id)
    remaining = [key for key in getattr(client, keys) if key.get("kid") != kid]
    if len(remaining) == len(getattr(client, keys)):
        raise NotFound(kid)
    if keep_one and not remaining:
        raise Conflict("last key")
    setattr(client, keys, remaining)
    client.save()
    return client


def add_signing_key(client_id, signing_key: dict) -> Client:
    return _add_key(client_id, "signingKeys", signing_key)


def remove_signing_key(client_id, kid: str, keep_one: bool = False) -> Client:
    """
        Revoking a key is deleting it. `keep_one` is for a client acting on itself: without it, it could leave
        itself with no way back in.
    """
    return _remove_key(client_id, "signingKeys", kid, keep_one)


def add_service_key(client_id, service_key: dict) -> Client:
    """
        Lets the response engine act for a client: it registers the public key the engine signs with for it. Two
        at most, as with the client's own, so that the engine rotates without a gap.
    """
    return _add_key(client_id, "serviceKeys", service_key)


def remove_service_key(client_id, kid: str) -> Client:
    """Revoking the engine's key for a client is deleting it: it stops reaching that client's chatbots at once."""
    return _remove_key(client_id, "serviceKeys", kid, keep_one=False)


def delete_client(client_id) -> dict:
    """
        Deletes a client with everything stored for it, and says how many of each. The order is what makes it
        safe to interrupt and to call again: first nobody gets in as the client, then its data goes, and the
        client itself goes last, taking its wrapped data key with it.
    """
    client = get_client(client_id)
    if client.role == Role.OPERATOR.value:
        # Without the operator nobody registers a client or lets one back in.
        raise Conflict("operator")
    erasures.record(erasures.CLIENT, client.uuid)
    return erase_client(client.uuid)


def erase_client(client_id: UUID) -> dict:
    """
        Deletes a client without writing it down in the register of erasures: for delete_client, which writes
        it down first, and for making again the deletions the register holds.
    """
    Client.objects(uuid=client_id).update_one(set__signingKeys=[], set__serviceKeys=[],
                                              set__status=Status.DIS.value, set__statusDate=datetime.now())
    deleted = TenantRepository(client_id).erase_all()
    forget_tokens(client_id)
    Client.objects(uuid=client_id).delete()
    # The open key of this process. Any other process drops its own within data_keys.OPEN_FOR seconds.
    data_keys.forget(client_id)
    return deleted


def find_signer(client_id: UUID, kid: str) -> tuple | None:
    """
        The active client, the public key registered for it under that kid, and what whoever signs with it is:
        the client itself, with the role of its entry, or the response engine acting for it. None if there is
        no such key.
    """
    client = Client.objects(uuid=client_id, status=Status.ACT.value).first()
    if client is None:
        return None
    for keys, role in ((client.signingKeys, Role(client.role)), (client.serviceKeys, Role.SERVICE)):
        for key in keys:
            if key.get("kid") == kid:
                return client, dict(key), role
    return None
