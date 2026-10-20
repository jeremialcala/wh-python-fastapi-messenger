# -*- coding: utf-8 -*-
"""
    Modelos de dominio para un mensaje entrante de Meta ya normalizado.

    Estos modelos son agnósticos a la plataforma: los adaptadores de
    infraestructura (Messenger/WhatsApp/Instagram) traducen cada webhook crudo
    a un `MensajeEntrante`.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.domain.enums import Origen


class Adjunto(BaseModel):
    """
        Archivo recibido junto a un mensaje (imagen, PDF, audio, vídeo, etc.).
    """
    tipo: str = Field(
        description="Tipo declarado por la plataforma: image, audio, video, document..."
    )
    url_o_id: Optional[str] = Field(
        default=None,
        description="URL pública o media-id de la plataforma para descargar el archivo."
    )
    mime_type: Optional[str] = Field(
        default=None,
        description="MIME type cuando la plataforma lo informa."
    )


class MensajeEntrante(BaseModel):
    """
        Mensaje entrante normalizado, independiente de la plataforma de origen.
    """
    mensaje_id: str = Field(
        description="Identificador único del mensaje en la plataforma de origen."
    )
    origen: Origen = Field(description="Plataforma de Meta de la que proviene el mensaje.")
    remitente: str = Field(description="Identificador del remitente (PSID, wa_id, IGSID).")
    texto: str = Field(default="", description="Contenido textual sanitizado del mensaje.")
    adjuntos: list[Adjunto] = Field(
        default_factory=list,
        description="Adjuntos recibidos con el mensaje."
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Marca de tiempo informada por la plataforma."
    )
    recibido_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Momento en que el servicio normalizó el mensaje."
    )
    raw: dict[str, Any] = Field(
        default_factory=dict,
        description="Fragmento crudo del webhook del que se derivó este mensaje."
    )

    @property
    def tiene_adjuntos(self) -> bool:
        """
        :return: True si el mensaje trae al menos un adjunto.
        """
        return len(self.adjuntos) > 0
