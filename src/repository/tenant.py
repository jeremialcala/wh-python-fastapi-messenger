# -*- coding: utf-8 -*-
"""
    The only way to a client's data. A repository is bound to one client when it is built, and every query it
    sends carries that client's id, so the isolation between clients does not depend on each caller remembering
    to check who owns what.
"""
from uuid import UUID

from classes import ChatBot, ChatbotPhone, Contact, Intent, Rule
from enums import Status

from .errors import NotFound


def as_uuid(value) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        # An id that cannot exist is answered like one that does not.
        raise NotFound(value) from None


class TenantRepository:

    def __init__(self, client_id: UUID):
        if not isinstance(client_id, UUID):
            raise TypeError("A repository cannot be built without the client it works for")
        self.client_id = client_id

    def _own(self, document, **filters):
        return document.objects(clientId=self.client_id, **filters)

    def _save_own(self, document):
        if document.clientId != self.client_id:
            raise NotFound(type(document).__name__)
        document.save()
        return document

    # --- Chatbots ---------------------------------------------------------------------------------------------------

    def add_bot(self, bot: ChatBot) -> ChatBot:
        bot.clientId = self.client_id
        bot.save()
        return bot

    def get_bot(self, bot_id) -> ChatBot:
        bot = self._own(ChatBot, uuid=as_uuid(bot_id)).first()
        if bot is None:
            raise NotFound(bot_id)
        return bot

    def _add_to_bot(self, bot_id, document, field: str):
        setattr(document, field, self.get_bot(bot_id).uuid)
        document.clientId = self.client_id
        document.save()
        return document

    # --- Phones -----------------------------------------------------------------------------------------------------

    def add_phone(self, bot_id, phone: ChatbotPhone) -> ChatbotPhone:
        return self._add_to_bot(bot_id, phone, "bot_id")

    def list_phones(self, bot_id, environment: str | None = None) -> list:
        filters = {"bot_id": self.get_bot(bot_id).uuid}
        if environment is not None:
            filters["environment"] = environment
        return list(self._own(ChatbotPhone, **filters))

    # --- Rules ------------------------------------------------------------------------------------------------------

    def add_rules(self, bot_id, rules: list) -> list:
        return [self._add_to_bot(bot_id, Rule(rule=rule), "botId") for rule in rules]

    def list_rules(self, bot_id) -> list:
        return list(self._own(Rule, botId=self.get_bot(bot_id).uuid))

    # --- Intents ----------------------------------------------------------------------------------------------------

    def add_intent(self, bot_id, intent: Intent) -> Intent:
        return self._add_to_bot(bot_id, intent, "botId")

    def list_intents(self, bot_id) -> list:
        return [intent for intent in self._own(Intent, botId=self.get_bot(bot_id).uuid)
                if intent.status != Status.DIS.value]

    def get_intent(self, bot_id, intent_id) -> Intent:
        intent = self._own(Intent, botId=self.get_bot(bot_id).uuid, uuid=as_uuid(intent_id)).first()
        if intent is None:
            raise NotFound(intent_id)
        return intent

    def save_intent(self, intent: Intent) -> Intent:
        return self._save_own(intent)

    # --- Contacts ---------------------------------------------------------------------------------------------------

    def find_contact_by_wa_id(self, bot_id, wa_id: str) -> Contact | None:
        return self._last_contact(bot_id, waId=wa_id)

    def find_contact_by_fb_id(self, bot_id, fb_id: str) -> Contact | None:
        return self._last_contact(bot_id, fbId=fb_id)

    def _last_contact(self, bot_id, **identity) -> Contact | None:
        contacts = list(self._own(Contact, botId=self.get_bot(bot_id).uuid, **identity))
        return contacts[-1] if contacts else None

    def add_contact(self, bot_id, contact: Contact) -> Contact:
        return self._add_to_bot(bot_id, contact, "botId")
