# -*- coding: utf-8 -*-
import time
from dataclasses import dataclass
from uuid import UUID

from enums import Role
from repository import find_signer, remember_token

from .gateway_keys import GatewayKeys
from .tokens import InvalidToken, verify


@dataclass(frozen=True)
class Principal:
    """Who is calling. What it may do comes from its registry entry, never from the token."""
    client_id: UUID
    role: Role


def authenticate(token: str | None, gateway_keys: GatewayKeys, audience: str) -> Principal:
    """Turns the token of a request into its caller, or raises InvalidToken."""
    if not token:
        raise InvalidToken("no token")
    signer = {}

    def signing_key(client_id: UUID, kid: str) -> dict | None:
        found = find_signer(client_id, kid)
        if found is None:
            return None
        signer["client"], key = found
        return key

    claims = verify(token, gateway_keys, audience, signing_key, time.time())
    # Last, and only for a token that was valid: a forged one must not be able to burn somebody's jti.
    if not remember_token(claims.client_id, claims.jti, claims.expires_at):
        raise InvalidToken("token already used")
    return Principal(client_id=claims.client_id, role=Role(signer["client"].role))
