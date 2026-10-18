# -*- coding: utf-8 -*-
from datetime import datetime
from uuid import UUID

from mongoengine.errors import NotUniqueError

from classes import SeenToken


def remember_token(client_id: UUID, jti: str, expires_at: datetime) -> bool:
    """
        Records that a token was presented. False means it had been presented before. It is a single insert
        on the primary key, so two requests racing with the same token cannot both get True.
    """
    try:
        SeenToken(key=SeenToken.key_for(client_id, jti), clientId=client_id,
                  expiresAt=expires_at).save(force_insert=True)
    except NotUniqueError:
        return False
    return True


def forget_tokens(client_id: UUID) -> int:
    """Deletes what is remembered of a client's tokens. Only for a client that no longer gets in."""
    return SeenToken.objects(clientId=client_id).delete()
