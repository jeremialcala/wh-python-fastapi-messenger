# -*- coding: utf-8 -*-
import logging

from classes import ChatBot, Settings

from . import kept_bots
from .errors import NotFound
from .tenant import as_uuid

settings = Settings()
log = logging.getLogger(settings.environment)


def find_webhook_bot(bot_id) -> ChatBot:
    """
        The one lookup that is not scoped to a client. Meta calls the webhook: the chatbot id in the URL says who
        the notification is for and the signature authenticates it, so there is no client to ask for. The client
        is taken from the chatbot, and everything after this goes through its repository.

        What is found is kept for kept_bots.KEEP_FOR seconds. What is not found is not: anybody can send ids.
    """
    bot_uuid = as_uuid(bot_id)
    bot = kept_bots.kept(bot_uuid)
    if bot is not None:
        return bot
    bot = ChatBot.objects(uuid=bot_uuid).first()
    if bot is None:
        raise NotFound(bot_id)
    if bot.clientId is None:
        # A chatbot from before clients existed that the migration has not reached: it has no owner to store
        # its contacts under.
        log.error(f"Chatbot {bot.uuid} has no client: run the operator client migration")
        raise NotFound(bot_id)
    kept_bots.keep(bot)
    return bot
