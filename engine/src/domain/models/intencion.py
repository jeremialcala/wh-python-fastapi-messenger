# -*- coding: utf-8 -*-
"""
    Modelo de dominio para la intención detectada por el motor de IA.
"""
from typing import Any

from pydantic import BaseModel, Field

from src.domain.enums import TipoRespuesta


class Intencion(BaseModel):
    """
        Resultado de la detección de intención sobre un `MensajeEntrante`.
    """
    etiqueta: str = Field(
        description="Nombre/etiqueta de la intención detectada (ej: consulta_stock)."
    )
    tipo_respuesta: TipoRespuesta = Field(
        description="Estrategia de salida sugerida: texto, action o adjunto."
    )
    confianza: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Confianza del modelo en la clasificación, en el rango [0, 1]."
    )
    entidades: dict[str, Any] = Field(
        default_factory=dict,
        description="Entidades/slots extraídos del mensaje."
    )
    razonamiento: str = Field(
        default="",
        description="Explicación breve provista por el modelo (auditoría)."
    )
