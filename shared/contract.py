# -*- coding: utf-8 -*-
"""
    The events of version 2 that cross between the gateway and the response engine, as models
    (docs/02-design/contracts/asyncapi-v2.yaml): what the ingestion publishes for the engine, and what the engine's
    notifier publishes back for the history. Both sides validate against these, so a change of the contract is a
    change here, tested on both sides at once (ADR-0023).

    They read what comes in strictly: a field missing or of another type is a broken event, not a default.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 2

Channel = Literal["whatsapp", "messenger", "instagram"]


def identified_subject(partition: int, bot_id, contact_id) -> str:
    """Where the ingestion publishes a message identified, in the stream MENSAJES."""
    return f"gateway.message.{partition}.{bot_id}.{contact_id}"


def reply_subject(bot_id) -> str:
    """Where the notifier publishes what it sent, in the stream RESPUESTAS."""
    return f"engine.reply.sent.{bot_id}"


class _Event(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    schemaVersion: Literal[2]
    botId: UUID
    # The client that owns the chatbot: which key the worker signs with (ADR-0022).
    clientId: UUID


class Contact(BaseModel):
    """Who writes. Personal data: the engine needs the id of the channel to answer, and passes none of it to the LLM."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    uuid: UUID
    name: str | None = None
    waId: str | None = None
    fbId: str | None = None
    igsid: str | None = None


class IdentifiedMessage(_Event):
    """MensajeIdentificado: one per message, from the ingestion to the engine's classifier."""
    messageId: str = Field(min_length=1)
    # The value of the WhatsApp change reduced to this message, or one entry[].messaging[] item of Messenger or of
    # Instagram. Personal data.
    message: dict
    channel: Channel
    receivedAt: datetime
    orderKey: str = Field(min_length=1)
    contact: Contact


class SentAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str


class SentReply(_Event):
    """RespuestaEnviada: what the notifier sent and Meta accepted, for the history of the conversation."""
    contactId: UUID
    channel: Channel
    # The Meta id of the message it answers.
    inReplyTo: str = Field(min_length=1)
    # The id Meta gave to what was sent.
    messageId: str = Field(min_length=1)
    sentAt: datetime
    text: str = Field(max_length=4096)
    attachments: list[SentAttachment] = []
