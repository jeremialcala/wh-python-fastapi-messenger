# -*- coding: utf-8 -*-
"""
    Resolver de origen: selecciona el `WebhookParser` adecuado según el campo
    `object` del webhook de Meta.
"""
import json
from typing import Any, Union

from src.domain.models import MensajeEntrante
from src.domain.ports import MessageNormalizer, OrigenNoSoportado, WebhookParser
from .messenger import MessengerParser
from .whatsapp import WhatsAppParser
from .instagram import InstagramParser


class WebhookResolver(MessageNormalizer):
    """
        Identificador de origen (Messenger / WhatsApp / Instagram). Recorre los
        parsers registrados y delega en el primero que soporte el payload.
    """

    def __init__(self, parsers: list[WebhookParser] | None = None):
        # `is None` (no `or`) para permitir pasar explícitamente una lista vacía.
        if parsers is None:
            parsers = [MessengerParser(), WhatsAppParser(), InstagramParser()]
        self._parsers = parsers

    def parsear(self, raw: Union[bytes, str, dict[str, Any]]) -> MensajeEntrante:
        """
            Deserializa (si hace falta) y normaliza el webhook crudo.

        :param raw: payload como bytes, str JSON o dict ya deserializado.
        :return: el `MensajeEntrante` normalizado.
        :raises OrigenNoSoportado: si el `object` no corresponde a una plataforma soportada.
        :raises ValueError: si el payload no es JSON válido o no contiene un mensaje.
        """
        payload = self._deserializar(raw)
        for parser in self._parsers:
            if parser.soporta(payload):
                return parser.parsear(payload)
        obj = payload.get("object") if isinstance(payload, dict) else type(payload)
        raise OrigenNoSoportado(f"object no soportado: {obj}")

    @staticmethod
    def _deserializar(raw: Union[bytes, str, dict[str, Any]]) -> dict[str, Any]:
        """
        :raises ValueError: si el JSON es inválido.
        """
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("payload de webhook no es JSON válido") from exc
