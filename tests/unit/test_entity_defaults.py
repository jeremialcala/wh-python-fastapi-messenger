# -*- coding: utf-8 -*-
"""
    Default values must be computed for each object, not once when the module is imported.
    They used to be written as `default=uuid4()` and `default=datetime.now()`: every document then carried the
    process start time as its creation date, and every queue message shared one `_uuid`.
"""
import time
from datetime import datetime, timedelta

import pytest

from classes import ChatBot, ChatbotPhone, Contact, Event, EventAction, Intent, Jwk, QueueMessage, ResponseData, Rule
from classes.entity_credentials import Credentials

ENTITIES = [ChatBot, ChatbotPhone, Contact, Event, EventAction, Intent, Jwk, QueueMessage, Rule, Credentials]
IDENTIFIER = {Contact: "_uuid", QueueMessage: "_uuid", Jwk: "kid"}


@pytest.mark.parametrize("entity", ENTITIES, ids=lambda entity: entity.__name__)
def test_each_document_gets_its_own_identifier(entity):
    field = IDENTIFIER.get(entity, "uuid")

    assert getattr(entity(), field) != getattr(entity(), field)


@pytest.mark.parametrize("entity", [e for e in ENTITIES if e is not Credentials], ids=lambda entity: entity.__name__)
def test_creation_date_is_the_moment_the_document_is_created(entity):
    before = time.time()
    time.sleep(0.002)

    document = entity()

    assert document.createdAt.timestamp() > before
    assert document.statusDate.timestamp() > before


def test_a_queue_message_is_dated_with_its_time_zone():
    # Without one, the date in the envelope shifts by the offset of whatever machine created it.
    message = QueueMessage()

    assert message.createdAt.utcoffset() == message.statusDate.utcoffset() == timedelta(0)


def test_each_credential_gets_its_own_signing_key():
    assert Credentials()._key != Credentials()._key


def test_credentials_do_not_share_the_header_dictionary():
    first, second = Credentials(), Credentials()
    first._header["alg"] = "none"

    assert second._header == {"alg": "HS256"}


def test_response_timestamp_is_the_moment_of_the_response():
    before = datetime.now()
    time.sleep(0.002)

    assert ResponseData().timestamp > before
