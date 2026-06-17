# -*- coding: utf-8 -*-
"""
    Parser de webhooks de Instagram (object == "instagram").

    Instagram Messaging comparte la estructura `entry[].messaging[]` de la
    Messenger Platform, por lo que reutiliza la misma base.
"""
from src.domain.enums import Origen
from .messaging_style import MessagingStyleParser


class InstagramParser(MessagingStyleParser):
    """
        Normaliza eventos de mensajería directa de Instagram.
    """
    _object = "instagram"
    _origen = Origen.INSTAGRAM
