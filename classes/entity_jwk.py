# -*- coding: utf-8 -*-
import logging
from jwcrypto import jwk
from datetime import datetime
from uuid import uuid4, UUID
from mongoengine import *
from enums import Status, KeyTypes
from .tool_settings import Settings
from .entity_event_jwk import EventJwk

settings = Settings()
log = logging.getLogger(settings.environment)
connect(
    db=settings.db_name,
    username=settings.db_username,
    password=settings.db_password,
    host=settings.db_host
)


class Jwk(Document):
    kid = UUIDField(required=True, unique=True, default=uuid4())
    kty = StringField()
    n = StringField()
    e = StringField()
    use = StringField()
    x5t = StringField()
    x5c = StringField()
    createdAt = DateTimeField(required=True, default=datetime.now())
    status = IntField(required=True, default=Status.REG.value)
    statusDate = DateTimeField(required=True, default=datetime.now())

    @staticmethod
    async def create_key_for_event(event_id: UUID) -> UUID:
        """
            This method creates a key to be used in each event, and create an event_key entity with be an index to
            control this keys/event relationship.

            TODO: create an Enum to control the use of this keys. and compare pre-generated keys vs generated on demand

        :param event_id: the unique identification of this event
        :return: the uuid of this key.

        """

        _uuid = uuid4()
        _key = jwk.JWK.generate(kty=KeyTypes.RSA.name, size=settings.key_size)
        _pem = _key.export_to_pem(private_key=True, password=None)
        _dict = _key.export_public(as_dict=True)

        _private = open(settings.private_key_filename.format(UUID=str(_uuid)), "w")
        _private.write(_pem.decode())
        _private.close()

        _dict["kid"] = _uuid
        _dict["use"] = "enc"
        _dict["x5t"] = _key.thumbprint()

        _jwk = Jwk(**_dict)
        _jwk.save(force_insert=True)

        EventJwk(eventId=event_id, jwkId=_uuid).save()

        return _uuid


