"""
    The default values of the webhook models are published: they are in a public repository and in the
    API documentation the app serves. They once held real phone numbers, one of them also encoded inside a
    WhatsApp message id. Example numbers must come from the range reserved for fiction (555-0100 to 555-0199).
"""
import base64
import re

from classes.dto_facebook_contact import Contact
from classes.dto_facebook_message import Message
from classes.dto_facebook_metadata import Metadata

FICTIONAL_NUMBER = re.compile(r"1\d{3}55501\d{2}")


def test_the_example_contact_number_is_fictional():
    assert FICTIONAL_NUMBER.fullmatch(Contact().wa_id)


def test_the_example_sender_number_is_fictional():
    assert FICTIONAL_NUMBER.fullmatch(Message().from_)


def test_the_example_business_number_is_fictional():
    assert all(FICTIONAL_NUMBER.fullmatch(number) for number in Metadata().display_phone_number)


def test_the_example_message_id_does_not_encode_a_phone_number():
    # A real wamid is base64 and carries the sender's number in clear inside it.
    payload = Message().id.removeprefix("wamid.")
    try:
        decoded = base64.b64decode(payload + "=" * (-len(payload) % 4)).decode("latin-1")
    except ValueError:
        decoded = ""

    assert not re.search(r"\d{10,}", decoded)
