# -*- coding: utf-8 -*-
"""
    The only way to a client's data. A repository is bound to one client when it is built, and every query it
    sends carries that client's id, so the isolation between clients does not depend on each caller remembering
    to check who owns what.
"""
from dataclasses import dataclass
from uuid import UUID

from classes import ChatBot, ChatbotPhone, Contact, Intent, Rule
from crypto.fields import ClientCipher
from enums import Status

from .data_keys import cipher_for
from .errors import NotFound

# What is stored encrypted with the client's data key. The documents always hold the ciphertext: whoever
# needs the value asks the repository for it, so a document saved again never writes it in clear.
BOT_SECRETS = ("verifyToken", "facebookToken", "whatsappToken", "appSecret")
BOT_CREDENTIALS = ("facebookToken", "whatsappToken", "appSecret")
PHONE_FIELDS = ("phoneNumber", "phoneId")


@dataclass(frozen=True)
class BotSecrets:
    """The secrets of a chatbot, opened. It is never stored and never goes into a response as a whole."""
    verify_token: str | None
    facebook_token: str | None
    whatsapp_token: str | None
    app_secret: str | None


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

    @property
    def _cipher(self) -> ClientCipher:
        return cipher_for(self.client_id)

    def _own(self, document, **filters):
        return document.objects(clientId=self.client_id, **filters)

    def _save_own(self, document):
        if document.clientId != self.client_id:
            raise NotFound(type(document).__name__)
        document.save()
        return document

    # --- Chatbots ---------------------------------------------------------------------------------------------------

    def add_bot(self, bot: ChatBot) -> ChatBot:
        """A new chatbot. Whatever secrets it carries are in clear, and they are encrypted here."""
        bot.clientId = self.client_id
        for field in BOT_SECRETS:
            setattr(bot, field, self._cipher.encrypt(f"ChatBot.{field}", getattr(bot, field)))
        bot.save()
        return bot

    def bot_secrets(self, bot: ChatBot) -> BotSecrets:
        if bot.clientId != self.client_id:
            raise NotFound(bot.uuid)
        opened = {field: self._cipher.decrypt(f"ChatBot.{field}", getattr(bot, field)) for field in BOT_SECRETS}
        return BotSecrets(verify_token=opened["verifyToken"], facebook_token=opened["facebookToken"],
                          whatsapp_token=opened["whatsappToken"], app_secret=opened["appSecret"])

    def set_bot_credentials(self, bot_id, **credentials) -> ChatBot:
        """Loads or rotates the Meta credentials of a chatbot. Only the ones given change."""
        bot = self.get_bot(bot_id)
        for field, value in credentials.items():
            if field not in BOT_CREDENTIALS:
                raise ValueError(field)
            if value is not None:
                setattr(bot, field, self._cipher.encrypt(f"ChatBot.{field}", value))
        bot.save()
        return bot

    def get_bot(self, bot_id) -> ChatBot:
        bot = self._own(ChatBot, uuid=as_uuid(bot_id)).first()
        if bot is None:
            raise NotFound(bot_id)
        return bot

    def _add_to_bot(self, bot_id, document, field: str, seal=None):
        setattr(document, field, self.get_bot(bot_id).uuid)
        document.clientId = self.client_id
        if seal is not None:
            # Only once the chatbot is known to be the client's: nothing is encrypted for a stranger.
            seal(document)
        document.save()
        return document

    # --- Phones -----------------------------------------------------------------------------------------------------

    def add_phone(self, bot_id, phone: ChatbotPhone) -> ChatbotPhone:
        def seal(document):
            for field in PHONE_FIELDS:
                setattr(document, field, self._cipher.encrypt(f"ChatbotPhone.{field}", getattr(document, field)))

        return self._add_to_bot(bot_id, phone, "bot_id", seal)

    def phone_numbers(self, phone: ChatbotPhone) -> dict:
        """The number and the Meta id of a phone, opened."""
        if phone.clientId != self.client_id:
            raise NotFound(phone.uuid)
        return {field: self._cipher.decrypt(f"ChatbotPhone.{field}", getattr(phone, field)) for field in PHONE_FIELDS}

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
        # The number is not stored in clear, so it is looked up by its blind index.
        bot = self.get_bot(bot_id)
        return self._last_contact(bot.uuid, waIdIndex=self._cipher.blind_index("Contact.waId", wa_id))

    def find_contact_by_fb_id(self, bot_id, fb_id: str) -> Contact | None:
        return self._last_contact(bot_id, fbId=fb_id)

    def _last_contact(self, bot_id, **identity) -> Contact | None:
        contacts = list(self._own(Contact, botId=self.get_bot(bot_id).uuid, **identity))
        return contacts[-1] if contacts else None

    def add_contact(self, bot_id, contact: Contact) -> Contact:
        def seal(document):
            if document.waId is not None:
                document.waIdIndex = self._cipher.blind_index("Contact.waId", document.waId)
                document.waId = self._cipher.encrypt("Contact.waId", document.waId)

        return self._add_to_bot(bot_id, contact, "botId", seal)

    def contact_number(self, contact: Contact) -> str | None:
        if contact.clientId != self.client_id:
            raise NotFound(contact._uuid)
        return self._cipher.decrypt("Contact.waId", contact.waId)
