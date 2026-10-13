# -*- coding: utf-8 -*-
"""
    The data key of each client: where it comes from and how long it is kept open. In the database there is only
    the wrapped key; the key service opens it, and the open key stays in memory for a few minutes so that not
    every request has to ask for it.
"""
import time
from uuid import UUID

from classes import Client
from crypto.fields import ClientCipher

from .errors import NotFound

# How long an open data key is kept in memory. Short: it is what an attacker reading the process would find.
OPEN_FOR = 300

_service = None
_open = {}


def configure(service) -> None:
    """Sets the key service the data keys are asked from. Done once, when the application starts."""
    global _service
    _service = service
    _open.clear()


def forget(client_id: UUID | None = None) -> None:
    """Drops the open keys from memory: one client's, or all of them."""
    if client_id is None:
        _open.clear()
    else:
        _open.pop(client_id, None)


def _data_key(client_id: UUID) -> bytes:
    client = Client.objects(uuid=client_id).first()
    if client is None:
        raise NotFound(client_id)
    if client.wrappedDataKey:
        return _service.unwrap(client_id, client.wrappedDataKey)
    # The first time a client needs its key. Only stored if nobody stored one in the meantime: two workers
    # starting at once must end up with the same key, or one of them would encrypt what the other cannot read.
    key, wrapped = _service.new_data_key(client_id)
    stored = Client.objects(uuid=client_id, wrappedDataKey__in=[None, ""]).update_one(set__wrappedDataKey=wrapped)
    if stored:
        return key
    return _service.unwrap(client_id, Client.objects(uuid=client_id).first().wrappedDataKey)


def cipher_for(client_id: UUID) -> ClientCipher:
    """What encrypts and decrypts the fields of one client. Raises KeyServiceUnavailable if the key cannot be had."""
    if _service is None:
        raise RuntimeError("No key service configured")
    cached = _open.get(client_id)
    if cached and cached[1] > time.monotonic():
        return cached[0]
    cipher = ClientCipher(client_id, _data_key(client_id))
    _open[client_id] = (cipher, time.monotonic() + OPEN_FOR)
    return cipher
