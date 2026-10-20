# -*- coding: utf-8 -*-
"""
    Modelo de dominio para el resultado clasificado que se publica aguas abajo.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.domain.enums import Origen, TipoRespuesta
from src.domain.models.intencion import Intencion


class ResultadoClasificado(BaseModel):
    """
        Salida del pipeline. Se serializa a JSON y se publica en la cola de
        salida para que un servicio aguas abajo entregue la respuesta al usuario.
    """
    mensaje_id: str = Field(description="Identificador del mensaje de origen.")
    origen: Origen = Field(description="Plataforma de Meta del mensaje.")
    remitente: str = Field(description="Identificador del remitente al que responder.")
    tipo_respuesta: TipoRespuesta = Field(description="Estrategia de respuesta determinada.")
    permitido: bool = Field(
        default=True,
        description="False cuando la entrada fue bloqueada por los guardrails."
    )
    motivo_bloqueo: str = Field(
        default="",
        description="Motivo del bloqueo cuando permitido es False."
    )
    intencion: Optional[Intencion] = Field(
        default=None,
        description="Intención detectada (ausente cuando la entrada fue bloqueada)."
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Datos adicionales para el servicio aguas abajo."
    )
    procesado_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Momento en que se produjo el resultado."
    )

    def to_json(self) -> str:
        """
        :return: Representación JSON del resultado, lista para publicar en AMQP.
        """
        return self.model_dump_json(by_alias=False)
