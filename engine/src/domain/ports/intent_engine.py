# -*- coding: utf-8 -*-
"""
    Puerto para el motor de detección de intención.
"""
from abc import ABC, abstractmethod

from src.domain.models import Intencion, MensajeEntrante


class IntentEngine(ABC):
    """
        Determina la intención y el tipo de respuesta de un mensaje entrante.
    """

    @abstractmethod
    def detectar(self, mensaje: MensajeEntrante) -> Intencion:
        """
        :param mensaje: mensaje normalizado a clasificar.
        :return: la intención detectada.
        """
