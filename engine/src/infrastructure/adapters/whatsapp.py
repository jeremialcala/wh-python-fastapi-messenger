# -*- coding: utf-8 -*-
"""
    Parser de webhooks de WhatsApp Cloud API (object == "whatsapp_business_account").

    Estructura: entry[].changes[].value.messages[] con `type` indicando el
    contenido (text, image, audio, video, document, ...).
    Ref: https://developers.facebook.com/documentation/business-messaging/whatsapp/calling
"""
from datetime import datetime, timezone
from typing import Any

from src.domain.enums import Origen
from src.domain.models import Adjunto, MensajeEntrante
from src.domain.ports import WebhookParser
from .sanitize import sanitizar_texto, sanitizar_id

# Tipos de mensaje de WhatsApp que transportan un adjunto multimedia.
_TIPOS_MEDIA = {"image", "audio", "video", "document", "sticker", "voice"}


class WhatsAppParser(WebhookParser):
    """
        Normaliza mensajes entrantes de la WhatsApp Cloud API.
    """

    def soporta(self, payload: dict[str, Any]) -> bool:
        return isinstance(payload, dict) and payload.get("object") == "whatsapp_business_account"

    def parsear(self, payload: dict[str, Any]) -> MensajeEntrante:
        mensaje = self._primer_mensaje(payload)
        if mensaje is None:
            raise ValueError("webhook whatsapp sin mensaje")

        mensaje_id = sanitizar_id(mensaje.get("id"))
        remitente = sanitizar_id(mensaje.get("from"))
        if not mensaje_id or not remitente:
            raise ValueError("webhook whatsapp con identificadores inválidos")

        tipo = mensaje.get("type", "text")
        texto = ""
        adjuntos: list[Adjunto] = []

        if tipo == "text":
            texto = sanitizar_texto((mensaje.get("text") or {}).get("body", ""))
        elif tipo in _TIPOS_MEDIA:
            media = mensaje.get(tipo) or {}
            # WhatsApp incluye 'caption' en imágenes/vídeos/documentos.
            texto = sanitizar_texto(media.get("caption", ""))
            media_id = sanitizar_id(media.get("id"))
            # Solo se adjunta si hay un media-id usable para descargar el archivo.
            if media_id:
                adjuntos.append(Adjunto(
                    tipo=tipo,
                    url_o_id=media_id,
                    mime_type=media.get("mime_type"),
                ))
        else:
            # interactive, location, contacts, etc.: se preserva el texto si lo hay.
            texto = sanitizar_texto((mensaje.get("text") or {}).get("body", ""))

        return MensajeEntrante(
            mensaje_id=mensaje_id,
            origen=Origen.WHATSAPP,
            remitente=remitente,
            texto=texto,
            adjuntos=adjuntos,
            timestamp=self._timestamp(mensaje.get("timestamp")),
            raw=mensaje,
        )

    @staticmethod
    def _primer_mensaje(payload: dict[str, Any]) -> dict[str, Any] | None:
        """
            Devuelve el primer mensaje en entry[].changes[].value.messages[].
            Ignora cambios que solo traen `statuses` (entregado/leído).
        """
        for entry in payload.get("entry", []) or []:
            if not isinstance(entry, dict):
                continue
            for change in entry.get("changes", []) or []:
                if not isinstance(change, dict):
                    continue
                valor = change.get("value")
                mensajes = (valor.get("messages") if isinstance(valor, dict) else None) or []
                if mensajes and isinstance(mensajes[0], dict):
                    return mensajes[0]
        return None

    @staticmethod
    def _timestamp(valor: Any) -> datetime | None:
        """
            WhatsApp envía el epoch en segundos como string.
        """
        if valor is None:
            return None
        try:
            return datetime.fromtimestamp(int(valor), tz=timezone.utc)
        except (ValueError, TypeError, OverflowError):
            return None
