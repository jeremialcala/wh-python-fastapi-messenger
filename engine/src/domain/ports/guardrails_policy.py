# -*- coding: utf-8 -*-
"""
    Puerto para la capa de seguridad de IA (guardrails).
"""
from abc import ABC, abstractmethod

from src.domain.models import ResultadoGuardrail


class GuardrailsPolicy(ABC):
    """
        Evalúa un texto de entrada y decide si puede continuar por el pipeline.
    """

    @abstractmethod
    def evaluar(self, texto: str) -> ResultadoGuardrail:
        """
        :param texto: contenido textual del mensaje a evaluar.
        :return: veredicto con permitido/motivo.
        """
