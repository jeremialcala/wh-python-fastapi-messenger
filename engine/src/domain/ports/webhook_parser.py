# -*- coding: utf-8 -*-
"""
    Puerto para los parsers de webhooks de Meta.
"""
from abc import ABC, abstractmethod
from typing import Any

from src.domain.models import MensajeEntrante


class WebhookParser(ABC):
    """
        Traduce un payload crudo de webhook de Meta a un `MensajeEntrante`.

        Cada implementación cubre una plataforma (Messenger, WhatsApp, Instagram)
        y declara si soporta un payload dado mediante `soporta`.
    """

    @abstractmethod
    def soporta(self, payload: dict[str, Any]) -> bool:
        """
        :param payload: webhook crudo deserializado.
        :return: True si esta implementación puede parsear el payload.
        """

    @abstractmethod
    def parsear(self, payload: dict[str, Any]) -> MensajeEntrante:
        """
        :param payload: webhook crudo deserializado.
        :return: el mensaje normalizado.
        :raises ValueError: si el payload no contiene un mensaje válido.
        """
