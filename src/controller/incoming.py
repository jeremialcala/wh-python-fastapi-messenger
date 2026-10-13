# -*- coding: utf8 -*-
"""
    The messages inside a notification from Meta.

    One notification may carry several messages, in several entries, next to things that are not a message from
    a person: delivery receipts, read marks, button presses, or the echo of what the page itself sent. Each
    message that can be answered becomes one envelope in the queue; the rest is left out.
"""
from dataclasses import dataclass

__all__ = ["WHATSAPP", "MESSENGER", "IncomingMessage", "incoming_messages"]

WHATSAPP = "whatsapp_business_account"
MESSENGER = "page"


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


def _whatsapp(entries):
    for entry in _dicts(entries):
        for change in _dicts(entry.get("changes")):
            value = change.get("value")
            metadata = value.get("metadata") if isinstance(value, dict) else None
            # Without the number the message was sent to, the response engine has nowhere to answer from.
            if not isinstance(metadata, dict) or not _text(metadata.get("phone_number_id")):
                continue
            contacts = _dicts(value.get("contacts"))
            for message in _dicts(value.get("messages")):
                message_id, number = _text(message.get("id")), _text(message.get("from"))
                if not (message_id and number):
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


def _messenger(entries):
    for entry in _dicts(entries):
        for event in _dicts(entry.get("messaging")):
            message, sender = event.get("message"), event.get("sender")
            if not isinstance(message, dict) or not isinstance(sender, dict):
                continue
            # An echo is what the page itself sent: queued, the bot would be answering its own messages.
            if message.get("is_echo"):
                continue
            message_id, sender_id = _text(message.get("mid")), _text(sender.get("id"))
            if message_id and sender_id:
                yield IncomingMessage(message_id=message_id, sender=sender_id, name=None, content=event)


READERS = {WHATSAPP: _whatsapp, MESSENGER: _messenger}


def incoming_messages(channel: str, entries) -> list[IncomingMessage]:
    """Every message of the notification that a person sent and the response engine can answer, in order."""
    reader = READERS.get(channel)
    return list(reader(entries)) if reader else []
