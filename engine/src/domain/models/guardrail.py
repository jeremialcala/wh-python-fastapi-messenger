# -*- coding: utf-8 -*-
"""
    Modelo de dominio para el resultado de la capa de seguridad (guardrails).
"""
from pydantic import BaseModel, Field


class ResultadoGuardrail(BaseModel):
    """
        Veredicto de la política de guardrails sobre un texto de entrada.
    """
    permitido: bool = Field(description="True si la entrada pasa la política de seguridad.")
    motivo: str = Field(
        default="",
        description="Razón del bloqueo (jailbreak, off-topic, etc.) cuando permitido es False."
    )
