# -*- coding: utf-8 -*-
"""
    Which messages a notification from Meta carries. One notification may bring several messages, and things that
    are not a message from a person; each message that can be answered has to come out once, and nothing else.
"""
import copy

import pytest

from controller.incoming import MESSENGER, WHATSAPP, incoming_messages

METADATA = {"display_phone_number": "12025550101", "phone_number_id": "100000000000001"}
ANA = {"profile": {"name": "Ana"}, "wa_id": "12025550143"}
LUIS = {"profile": {"name": "Luis"}, "wa_id": "12025550199"}


def text(message_id, number="12025550143"):
    return {"from": number, "id": message_id, "timestamp": "1760000000", "type": "text", "text": {"body": "hola"}}


def whatsapp(*values):
    return [{"id": "1", "changes": [{"field": "messages", "value": value}]} for value in values]


def value(messages, contacts=(ANA,)):
    return {"messaging_product": "whatsapp", "metadata": METADATA, "contacts": list(contacts),
            "messages": list(messages)}


def event(mid, sender="123456789", **message):
    return {"sender": {"id": sender}, "recipient": {"id": "987654321"}, "timestamp": 1760000000000,
            "message": {"mid": mid, "text": "hola", **message}}


def messenger(*events):
    return [{"id": "1", "time": 1760000000000, "messaging": list(events)}]


def ids(found):
    return [message.message_id for message in found]


# --- WhatsApp --------------------------------------------------------------------------------------------------------

def test_a_whatsapp_message_comes_out_with_its_identifier_its_sender_and_the_number_it_was_sent_to():
    (message,) = incoming_messages(WHATSAPP, whatsapp(value([text("wamid.A")])))

    assert (message.message_id, message.sender, message.name) == ("wamid.A", "12025550143", "Ana")
    assert message.content == {"messaging_product": "whatsapp", "metadata": METADATA, "contacts": [ANA],
                               "messages": [text("wamid.A")]}


def test_every_message_of_a_whatsapp_notification_comes_out_alone_and_in_order():
    found = incoming_messages(WHATSAPP, whatsapp(value([text("wamid.A"), text("wamid.B")])))

    assert ids(found) == ["wamid.A", "wamid.B"]
    assert [message.content["messages"] for message in found] == [[text("wamid.A")], [text("wamid.B")]]


def test_every_entry_and_every_change_of_a_whatsapp_notification_is_read():
    entries = whatsapp(value([text("wamid.A")]), value([text("wamid.B")]))
    entries[0]["changes"].append({"field": "messages", "value": value([text("wamid.C")])})

    assert ids(incoming_messages(WHATSAPP, entries)) == ["wamid.A", "wamid.C", "wamid.B"]


def test_with_several_contacts_each_whatsapp_message_goes_with_the_one_who_wrote_it():
    found = incoming_messages(WHATSAPP, whatsapp(value([text("wamid.A"), text("wamid.B", "12025550199")],
                                                       contacts=(ANA, LUIS))))

    assert [(m.sender, m.name, m.content["contacts"]) for m in found] == [
        ("12025550143", "Ana", [ANA]), ("12025550199", "Luis", [LUIS])]


def test_a_whatsapp_message_whose_sender_is_not_among_several_contacts_keeps_the_number_it_came_from():
    (message,) = incoming_messages(WHATSAPP, whatsapp(value([text("wamid.A", "12025550000")], contacts=(ANA, LUIS))))

    assert (message.sender, message.name, message.content["contacts"]) == ("12025550000", None, [])


def test_a_whatsapp_message_without_contacts_keeps_the_number_it_came_from():
    (message,) = incoming_messages(WHATSAPP, whatsapp(value([text("wamid.A")], contacts=())))

    assert (message.sender, message.name, message.content["contacts"]) == ("12025550143", None, [])


def test_a_whatsapp_contact_without_a_name_is_still_the_sender():
    (message,) = incoming_messages(WHATSAPP, whatsapp(value([text("wamid.A")], contacts=({"wa_id": "12025550143"},))))

    assert (message.sender, message.name) == ("12025550143", None)


def test_a_delivery_receipt_is_not_a_message():
    receipt = {"messaging_product": "whatsapp", "metadata": METADATA,
               "statuses": [{"id": "wamid.SENT", "status": "delivered", "recipient_id": "12025550143"}]}

    assert incoming_messages(WHATSAPP, whatsapp(receipt)) == []


@pytest.mark.parametrize("metadata", [None, [], [["phone_number_id", "100000000000001"]], {}, {"phone_number_id": ""},
                                      {"phone_number_id": 100000000000001}])
def test_a_whatsapp_message_without_the_number_it_was_sent_to_is_left_out(metadata):
    broken = value([text("wamid.A")])
    broken["metadata"] = metadata

    assert ids(incoming_messages(WHATSAPP, whatsapp(broken, value([text("wamid.B")])))) == ["wamid.B"]


@pytest.mark.parametrize("message", [{"from": "12025550143"}, {"id": "wamid.A"}, {"id": "", "from": "12025550143"},
                                     {"id": 7, "from": "12025550143"}, {"id": "wamid.A", "from": None}, "text", None])
def test_a_whatsapp_message_without_identifier_or_sender_is_left_out_and_the_rest_is_kept(message):
    assert ids(incoming_messages(WHATSAPP, whatsapp(value([message, text("wamid.B")])))) == ["wamid.B"]


# --- Messenger -------------------------------------------------------------------------------------------------------

def test_a_messenger_message_comes_out_as_meta_sent_it():
    sent = event("m_A")
    (message,) = incoming_messages(MESSENGER, messenger(sent))

    assert (message.message_id, message.sender, message.name, message.content) == ("m_A", "123456789", None, sent)


def test_every_message_of_every_entry_of_a_messenger_notification_comes_out_in_order():
    entries = messenger(event("m_A"), event("m_B")) + messenger(event("m_C", sender="555"))

    found = incoming_messages(MESSENGER, entries)

    assert [(m.message_id, m.sender) for m in found] == [("m_A", "123456789"), ("m_B", "123456789"), ("m_C", "555")]


def test_the_echo_of_what_the_page_sent_is_not_a_message_from_a_person():
    assert ids(incoming_messages(MESSENGER, messenger(event("m_ECHO", is_echo=True), event("m_A")))) == ["m_A"]


@pytest.mark.parametrize("without_message", [
    {"postback": {"title": "Empezar", "payload": "GET_STARTED", "mid": "m_PB"}},
    {"read": {"watermark": 1760000000000}},
    {"delivery": {"mids": ["m_SENT"], "watermark": 1760000000000}},
    {"reaction": {"mid": "m_SENT", "action": "react", "emoji": "x"}},
])
def test_a_messenger_event_that_is_not_a_message_is_left_out(without_message):
    other = event("m_unused")
    del other["message"]
    other.update(without_message)

    assert ids(incoming_messages(MESSENGER, messenger(other, event("m_A")))) == ["m_A"]


@pytest.mark.parametrize("change", [
    lambda e: e["message"].pop("mid"), lambda e: e["message"].update(mid=""), lambda e: e["message"].update(mid=7),
    lambda e: e.pop("sender"), lambda e: e.update(sender="123456789"), lambda e: e["sender"].update(id=None),
    lambda e: e.update(message="hola"),
])
def test_a_messenger_message_without_identifier_or_sender_is_left_out_and_the_rest_is_kept(change):
    broken = event("m_BROKEN")
    change(broken)

    assert ids(incoming_messages(MESSENGER, messenger(broken, event("m_A")))) == ["m_A"]


# --- Whatever comes ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("channel", ["instagram", "Page", "", None])
def test_a_channel_the_gateway_does_not_serve_has_no_messages(channel):
    assert incoming_messages(channel, messenger(event("m_A"))) == []


@pytest.mark.parametrize("channel", [WHATSAPP, MESSENGER])
@pytest.mark.parametrize("entries", [None, "entry", {}, [], [None], ["entry"], [{}], [{"changes": None, "messaging": None}],
                                     [{"changes": "x", "messaging": "x"}], [{"changes": [None, {}], "messaging": [None, {}]}],
                                     [{"changes": [{"value": None}, {"value": []}]}]])
def test_a_notification_that_is_not_shaped_as_expected_has_no_messages_and_does_not_fail(channel, entries):
    assert incoming_messages(channel, entries) == []


def test_reading_a_notification_does_not_change_it():
    entries = whatsapp(value([text("wamid.A"), text("wamid.B")]))
    before = copy.deepcopy(entries)

    incoming_messages(WHATSAPP, entries)

    assert entries == before
