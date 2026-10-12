# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from uuid import uuid4

from mongoengine import *

from enums import Status, Role
from .tool_settings import Settings

settings = Settings()
log = logging.getLogger(settings.environment)

connect(
    db=settings.db_name,
    username=settings.db_username,
    password=settings.db_password,
    host=settings.db_host
)


class Client(Document):
    """
        A customer of the service: the owner of chatbots and of everything stored for them. Every document that
        holds a client's data carries this uuid as its clientId.
    """
    uuid = UUIDField(required=True, unique=True, default=uuid4)
    name = StringField(required=True, unique=True)
    role = StringField(required=True, default=Role.CLIENT.value, choices=[role.value for role in Role])
    # Not used yet. The public key the client signs its tokens with, and its data key wrapped by the master key.
    signingKey = DictField()
    wrappedDataKey = StringField()
    createdAt = DateTimeField(required=True, default=datetime.now)
    status = IntField(required=True, default=Status.REG.value)
    statusDate = DateTimeField(required=True, default=datetime.now)
