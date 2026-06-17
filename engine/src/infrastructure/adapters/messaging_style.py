# -*- coding: utf-8 -*-
"""
    Base común para plataformas que usan la estructura `entry[].messaging[]`
    de la Messenger Platform (Messenger e Instagram comparten este formato).
"""
from datetime import datetime, timezone
from typing import Any

from src.domain.enums import Origen
from src.domain.models import Adjunto, MensajeEntrante
from src.domain.ports import WebhookParser
from .sanitize import sanitizar_texto, sanitizar_id


class MessagingStyleParser(WebhookParser):
    """
        Parser para webhooks con `object` de tipo página/instagram y eventos en
        `entry[].messaging[]`. Las subclases fijan `_object` y `_origen`.
    """
    _object: str = ""
    _origen: Origen = Origen.DESCONOCIDO

    def soporta(self, payload: dict[str, Any]) -> bool:
        return isinstance(payload, dict) and payload.get("object") == self._object

    def parsear(self, payload: dict[str, Any]) -> MensajeEntrante:
        evento = self._primer_evento(payload)
        if evento is None:
            raise ValueError(f"webhook {self._object} sin evento de mensaje")

        mensaje = evento.get("message") or {}
        mensaje_id = sanitizar_id(mensaje.get("mid"))
        remitente = sanitizar_id((evento.get("sender") or {}).get("id"))
        if not mensaje_id or not remitente:
            raise ValueError(f"webhook {self._object} con identificadores inválidos")

        adjuntos = [
            Adjunto(
                tipo=str(a.get("type", "desconocido")),
                url_o_id=(a.get("payload") or {}).get("url"),
            )
            for a in (mensaje.get("attachments") or [])
        ]

        return MensajeEntrante(
            mensaje_id=mensaje_id,
            origen=self._origen,
            remitente=remitente,
            texto=sanitizar_texto(mensaje.get("text", "")),
            adjuntos=adjuntos,
            timestamp=self._timestamp(evento.get("timestamp")),
            raw=evento,
        )

    @staticmethod
    def _primer_evento(payload: dict[str, Any]) -> dict[str, Any] | None:
        """
            Devuelve el primer evento de `messaging` que contenga un `message`.
        """
        for entry in payload.get("entry", []) or []:
            for evento in entry.get("messaging", []) or []:
                if evento.get("message"):
                    return evento
        return None

    @staticmethod
    def _timestamp(valor: Any) -> datetime | None:
        """
            Convierte el epoch en milisegundos de Meta a datetime UTC.
        """
        if valor is None:
            return None
        try:
            return datetime.fromtimestamp(int(valor) / 1000, tz=timezone.utc)
        except (ValueError, TypeError, OverflowError):
            return None
