# -*- coding: utf-8 -*-
"""
    Parser de webhooks de Messenger (object == "page").
"""
from src.domain.enums import Origen
from .messaging_style import MessagingStyleParser


class MessengerParser(MessagingStyleParser):
    """
        Normaliza eventos de la Messenger Platform (Facebook Page).
    """
    _object = "page"
    _origen = Origen.MESSENGER
