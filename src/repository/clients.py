# -*- coding: utf-8 -*-
from datetime import datetime
from uuid import uuid4

from classes import Client
from enums import Role, Status

OPERATOR_NAME = "operator"


def operator_client() -> Client:
    """
        The operator's own client. It owns the chatbots that existed before clients did, and it is who the admin
        key works for until clients authenticate with their own tokens. It is created on first use; the name is
        unique, so several workers starting at once end up with the same one.
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
