# -*- coding: utf-8 -*-
"""
    The ingestion of a notification (ADR-0021): what the webhook used to do before answering Meta, now done after,
    by the ingestion worker (ingest.py), from the event the webhook published on WEBHOOK. For each message of the
    notification, in order:

        1. it is skipped if it is already in the history: Meta sent it again;
        2. the contact is found, or stored, as before, asking the Graph API in Messenger;
        3. the message identified is published on its conversation's partition of MENSAJES, and the envelope of
           version 1 goes to the queue `llm` of Hermod, for the response engine that still reads it;
        4. the message is stored in the history.

    Publishing goes before storing: if the worker stops in between, the event is delivered again and the message
    published again, and the bus drops the second copy by Nats-Msg-Id. The other way round, a message stored but
    never published would be skipped on the next delivery and lost. The engine has to bear a duplicate anyway.

    Without a bus (development and the tests) the webhook runs this itself, on the event it would have published.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import bus
from classes import ChatBot, Contact, MessageBody, QueueMessage, Settings
from classes.entity_conversation_message import INCOMING
from crypto.key_service import KeyServiceUnavailable
from repository import NotFound, TenantRepository, database_failed
from utils import describe

from .amqp_broker import BrokerUnavailable
from .facebook import ctr_identify_contact_by_wa_id, ctr_identify_fb_contact
from .incoming import IncomingMessage
from .webhook_event import SCHEMA_VERSION, traceparent

__all__ = ["DatabaseUnavailable", "Unprocessable", "RETRY_LATER", "PARTITIONS", "partition", "ingest_notification"]

settings = Settings()
log = logging.getLogger(settings.environment)

# The queue the response engine reads from, until it reads the bus.
QUEUE = "llm"
# Fixed: changing it means emptying MENSAJES first (ADR-0019).
PARTITIONS = 16


class DatabaseUnavailable(Exception):
    """The database did not do its part while a notification was being processed."""


class Unprocessable(Exception):
    """
        An event that would fail the same way however many times it is delivered: of a version this service does
        not know, or for a chatbot that no longer exists. It is dropped, and the log says why.
    """


# What makes the whole notification wait and be tried again: something the service needs is not there, and it will be.
RETRY_LATER = (BrokerUnavailable, bus.BusUnavailable, KeyServiceUnavailable, DatabaseUnavailable)


def partition(bot_id, contact_id) -> int:
    """
        The partition of a conversation: the first four bytes of the SHA-256 of `<botId>.<contactId>`, as an
        unsigned big-endian integer, modulo 16 (asyncapi-v2.yaml). Each one is read by a single worker, in order.
    """
    digest = hashlib.sha256(f"{bot_id}.{contact_id}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % PARTITIONS


# --- What a message of the event says ---------------------------------------------------------------------------------

def _first(items) -> dict:
    return items[0] if isinstance(items, list) and items and isinstance(items[0], dict) else {}


def _text(value) -> str | None:
    return value if isinstance(value, str) and value else None


def incoming(channel: str, item: dict) -> IncomingMessage:
    """
        A message of the event as the webhook read it: who sent it and what the engine receives. WhatsApp sends
        the value of the change reduced to that message; Messenger, the element of `messaging`.
    """
    content = item["message"]
    if channel == "whatsapp":
        contact, message = _first(content.get("contacts")), _first(content.get("messages"))
        profile = contact.get("profile") if isinstance(contact.get("profile"), dict) else {}
        sender = _text(contact.get("wa_id")) or _text(message.get("from"))
        name = _text(profile.get("name"))
    else:
        sender, name = _text((content.get("sender") or {}).get("id")), None
    if not sender:
        raise ValueError("a message without sender")
    return IncomingMessage(message_id=item["messageId"], sender=sender, name=name, content=content)


def what_was_said(channel: str, content: dict) -> tuple[str | None, tuple, datetime | None]:
    """
        What goes to the history of a message: its text, the type of each attachment and when Meta says it was
        sent. Of an attachment, never its address (ADR-0017).
    """
    if channel == "whatsapp":
        message = _first(content.get("messages"))
        kind = message.get("type")
        body = message.get(kind) if isinstance(message.get(kind), dict) else {}
        reply = body.get("button_reply") or body.get("list_reply") or {}
        text = (_text(body.get("body")) if kind == "text" else
                _text(reply.get("title")) if kind == "interactive" else
                _text(body.get("text")) if kind == "button" else
                _text(body.get("caption")))
        attachments = () if kind in ("text", "interactive", "button") or not _text(kind) else (kind,)
        sent = message.get("timestamp")
        sent_at = datetime.fromtimestamp(int(sent), timezone.utc) if str(sent).isdigit() else None
    else:
        message = content.get("message") if isinstance(content.get("message"), dict) else {}
        text = _text(message.get("text"))
        attachments = tuple(_text(each.get("type")) or "unknown" for each in message.get("attachments") or []
                            if isinstance(each, dict))
        sent = content.get("timestamp")
        sent_at = datetime.fromtimestamp(sent / 1000, timezone.utc) if isinstance(sent, (int, float)) else None
    return text, attachments, sent_at


# --- Each step --------------------------------------------------------------------------------------------------------

async def _identify(channel: str, message: IncomingMessage, bot: ChatBot) -> Contact:
    if channel == "whatsapp":
        return await ctr_identify_contact_by_wa_id(wa_id=message.sender, name=message.name, _bot=bot)
    return await ctr_identify_fb_contact(fbId=message.sender, _bot=bot)


def identified_event(event: dict, item: dict, contact: Contact, message: IncomingMessage) -> dict:
    """MensajeIdentificado (asyncapi-v2.yaml): what the engine's workers read, one per message."""
    who = {"uuid": str(contact._uuid), "name": contact.firstName}
    who["waId" if event["channel"] == "whatsapp" else "fbId"] = message.sender
    return {
        "schemaVersion": SCHEMA_VERSION,
        "botId": event["botId"],
        "clientId": event["clientId"],
        "messageId": item["messageId"],
        "message": item["message"],
        "channel": event["channel"],
        "receivedAt": event["receivedAt"],
        "orderKey": f"{event['botId']}.{contact._uuid}",
        "contact": who,
    }


async def _publish(event: dict, item: dict, contact: Contact, message: IncomingMessage, trace: str | None) -> None:
    if bus.configured():
        await bus.publisher().publish(
            f"gateway.message.{partition(event['botId'], contact._uuid)}.{event['botId']}.{contact._uuid}",
            json.dumps(identified_event(event, item, contact, message), separators=(",", ":")).encode("utf-8"),
            f"{event['botId']}:{item['messageId']}", headers={"traceparent": trace or traceparent()})
    body = MessageBody(botId=event["botId"], clientId=event["clientId"], type=_KINDS[event["channel"]],
                       contact={"name": contact.firstName, ("waId" if event["channel"] == "whatsapp" else "fbId"):
                                message.sender},
                       message=message.content)
    # Late import: the test doubles replace it where the webhook used to call it.
    from . import messages
    await messages.send_message_to_queue(queue=QUEUE, message=QueueMessage(messageId=item["messageId"],
                                                                           jwe_body=body.__dict__))


# The kind of object of version 1, which the envelope still carries as `type`.
_KINDS = {"whatsapp": "whatsapp_business_account", "messenger": "page"}


async def ingest_notification(event: dict, trace: str | None = None, bot: ChatBot | None = None) -> dict:
    """
        Ingests one EventoWebhook. Raises Unprocessable for an event that cannot ever be ingested, and one of
        RETRY_LATER when it has to wait. A message that fails by itself is left in the log and the rest go on.
        Says how many messages were ingested, skipped as already seen, and failed. The webhook, which has just
        found the chatbot, passes it along so that it is not looked for again.
    """
    if not isinstance(event, dict) or event.get("schemaVersion") != SCHEMA_VERSION:
        raise Unprocessable("not an event of version 2")
    try:
        repo = TenantRepository(UUID(event["clientId"]))
        bot = bot or repo.get_bot(event["botId"])
    except (NotFound, KeyError, ValueError, TypeError):
        raise Unprocessable("for a chatbot that does not exist") from None
    except Exception as e:
        if database_failed(e):
            raise DatabaseUnavailable(type(e).__name__) from None
        raise
    received_at = datetime.fromisoformat(event["receivedAt"])
    outcome = {"ingested": 0, "seen": 0, "failed": 0}
    for item in event["messages"]:
        try:
            if repo.has_message(bot.uuid, INCOMING, item["messageId"]):
                outcome["seen"] += 1
                continue
            message = incoming(event["channel"], item)
            contact = await _identify(event["channel"], message, bot)
            await _publish(event, item, contact, message, trace)
            text, attachments, sent_at = what_was_said(event["channel"], message.content)
            repo.record_message(contact, INCOMING, item["messageId"], event["channel"], sent_at or received_at,
                                text=text, attachments=attachments)
            outcome["ingested"] += 1
        except RETRY_LATER:
            raise
        except Exception as e:
            if database_failed(e):
                log.error(f"The database is unavailable: {describe(e)}")
                raise DatabaseUnavailable(type(e).__name__) from None
            # A message that fails by itself would fail again, and must not take the rest of the notification with it.
            log.error(f"A message for chatbot {bot.uuid} could not be ingested: {describe(e)}")
            outcome["failed"] += 1
    return outcome
