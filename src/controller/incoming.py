# -*- coding: utf8 -*-
"""
    The messages inside a notification from Meta.

    One notification may carry several messages, in several entries, next to things that are not a message from
    a person: delivery receipts, read marks, button presses, or the echo of what the page itself sent. Each
    message that can be answered becomes one envelope in the queue; the rest is left out.
"""
from dataclasses import dataclass

from pydantic import ValidationError

from classes import FacebookRequest

__all__ = ["WHATSAPP", "MESSENGER", "IncomingMessage", "NotUnderstood", "read_notification", "incoming_messages"]

WHATSAPP = "whatsapp_business_account"
MESSENGER = "page"

# Why a message of a notification is left out. Said to the log as it is: none of it comes from the notification.
NO_NUMBER = "sent to no number"
INCOMPLETE = "without identifier or sender"


class NotUnderstood(ValueError):
    """
        What was sent is not a notification the service can read. It says which kind of problem it is, in words
        of the service: never anything of what was sent.
    """


def read_notification(raw: bytes) -> FacebookRequest:
    """The notification in a body that Meta signed. Read only once the signature is known to be good."""
    try:
        return FacebookRequest.model_validate_json(raw)
    except ValidationError as e:
        not_json = any(error["type"] == "json_invalid" for error in e.errors())
        raise NotUnderstood("it is not JSON" if not_json else "it does not have the shape of one") from None


@dataclass(frozen=True)
class IncomingMessage:
    message_id: str  # The identifier Meta gave it: `id` (wamid) in WhatsApp, `mid` in Messenger.
    sender: str  # WhatsApp number or Messenger PSID.
    name: str | None  # Only WhatsApp sends the name along with the message.
    content: dict  # What the response engine receives as the message.


def _dicts(items) -> list[dict]:
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _text(value) -> str | None:
    return value if isinstance(value, str) and value else None


def _whatsapp_sender(contacts: list[dict], number: str) -> dict | None:
    # Meta sends one contact per notification; with more than one, the message says which one wrote it.
    if len(contacts) == 1:
        return contacts[0]
    return next((contact for contact in contacts if contact.get("wa_id") == number), None)


def _whatsapp(entries, left_out: list):
    for entry in _dicts(entries):
        for change in _dicts(entry.get("changes")):
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            metadata, messages = value.get("metadata"), _dicts(value.get("messages"))
            # Without the number the message was sent to, the response engine has nowhere to answer from.
            if not isinstance(metadata, dict) or not _text(metadata.get("phone_number_id")):
                left_out.extend([NO_NUMBER] * len(messages))
                continue
            contacts = _dicts(value.get("contacts"))
            for message in messages:
                message_id, number = _text(message.get("id")), _text(message.get("from"))
                if not (message_id and number):
                    left_out.append(INCOMPLETE)
                    continue
                contact = _whatsapp_sender(contacts, number)
                profile = contact.get("profile") if contact else None
                yield IncomingMessage(
                    message_id=message_id,
                    sender=(contact and _text(contact.get("wa_id"))) or number,
                    name=_text(profile.get("name")) if isinstance(profile, dict) else None,
                    content={
                        "messaging_product": _text(value.get("messaging_product")) or "whatsapp",
                        "metadata": metadata,
                        "contacts": [contact] if contact else [],
                        "messages": [message],
                    })


def _messenger(entries, left_out: list):
    for entry in _dicts(entries):
        for event in _dicts(entry.get("messaging")):
            message, sender = event.get("message"), event.get("sender")
            if not isinstance(message, dict) or not isinstance(sender, dict):
                continue
            # An echo is what the page itself sent: queued, the bot would be answering its own messages.
            if message.get("is_echo"):
                continue
            message_id, sender_id = _text(message.get("mid")), _text(sender.get("id"))
            if not (message_id and sender_id):
                left_out.append(INCOMPLETE)
                continue
            yield IncomingMessage(message_id=message_id, sender=sender_id, name=None, content=event)


READERS = {WHATSAPP: _whatsapp, MESSENGER: _messenger}


def incoming_messages(channel: str, entries, left_out: list | None = None) -> list[IncomingMessage]:
    """
        Every message of the notification that a person sent and the response engine can answer, in order. Why
        each message that is not among them was left out is added to `left_out`, if it is given. What is not a
        message from a person is not there: nothing was left out.
    """
    reader = READERS.get(channel)
    return list(reader(entries, [] if left_out is None else left_out)) if reader else []
