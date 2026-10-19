# -*- coding: utf-8 -*-
import time
from dataclasses import dataclass
from uuid import UUID

from enums import Role, Worker
from repository import find_signer, remember_token

from .gateway_keys import GatewayKeys
from .tokens import InvalidToken, verify


@dataclass(frozen=True)
class Principal:
    """Who is calling. What it may do comes from its registry entry, never from the token."""
    client_id: UUID
    role: Role
    # The registered key the token was signed with.
    kid: str
    # The token's, used up by this request: what a request that needs a proof binds it to.
    jti: str
    # For the response engine, which of its workers signs: it decides the routes it reaches. None for a key
    # registered before keys had a worker (ADR-0022).
    worker: Worker | None = None

    @property
    def worker_name(self) -> str:
        """The worker, as the log writes it."""
        return self.worker.value if self.worker else "none"


def authenticate(token: str | None, gateway_keys: GatewayKeys, audience: str) -> Principal:
    """Turns the token of a request into its caller, or raises InvalidToken."""
    if not token:
        raise InvalidToken("no token")
    signer = {}

    def signing_key(client_id: UUID, kid: str) -> dict | None:
        found = find_signer(client_id, kid)
        if found is None:
            return None
        _, key, signer["role"], signer["worker"] = found
        signer["key"] = key
        return key

    claims = verify(token, gateway_keys, audience, signing_key, time.time())
    # Last, and only for a token that was valid: a forged one must not be able to burn somebody's jti.
    if not remember_token(claims.client_id, claims.jti, claims.expires_at):
        raise InvalidToken("token already used")
    return Principal(client_id=claims.client_id, role=signer["role"], kid=signer["key"]["kid"],
                     jti=claims.jti, worker=signer["worker"])
