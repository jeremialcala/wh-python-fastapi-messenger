# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4, UUID
from mongoengine import *
from jwcrypto import jwe, jwk
from inspect import currentframe

from enums import Status
from utils import get_private_key

from .tool_settings import Settings
from .entity_jwk import EventJwk
from .entity_jwk import Jwk
from .dto_protected_header import ProtectedHeader
from .dto_message_body import MessageBody


settings = Settings()
log = logging.getLogger(settings.environment)
connect(
    db=settings.db_name,
    username=settings.db_username,
    password=settings.db_password,
    host=settings.db_host
)


class QueueMessage(Document):
    _uuid = UUIDField(required=True, unique=True, default=uuid4())
    eventId = UUIDField(required=True)
    endpoint = StringField()
    operation = StringField()
    jwe_body = StringField()
    createdAt = DateTimeField(required=True, default=datetime.now())
    status = IntField(required=True, default=Status.REG.value)
    statusDate = DateTimeField(required=True, default=datetime.now())

    def set_jwe_body(self, body: MessageBody):
        log.info(f"Starting: {currentframe().f_code.co_name}")
        try:
            ev_jk = [ev_jk for ev_jk in EventJwk.objects(eventId=self.eventId)][-1]
            log.info(ev_jk)

            _jwk = Jwk.get_jwk_from_uuid(ev_jk.jwkId)
            log.info(_jwk)

            _protected_header = ProtectedHeader(kid=_jwk.x5t)
            log.info(_protected_header.json())

            _jwe_tk = jwe.JWE(
                body.json().encode("utf-8"),
                recipient=_jwk.get_jwk(),
                protected=_protected_header.__dict__
            )

            self.jwe_body = _jwe_tk.serialize(compact=True)
            log.info(f"Ending: {currentframe().f_code.co_name}")
        except Exception as e:
            log.error(e.__str__())

