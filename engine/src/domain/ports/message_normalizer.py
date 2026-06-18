# -*- coding: utf-8 -*-
"""
    Puerto para normalizar un webhook crudo de Meta a un `MensajeEntrante`,
    identificando previamente la plataforma de origen.
"""
from abc import ABC, abstractmethod
from typing import Any, Union

from src.domain.models import MensajeEntrante


class OrigenNoSoportado(ValueError):
    """
        Se lanza cuando ningún origen soportado corresponde al payload recibido.
    """


class MessageNormalizer(ABC):
    """
        Deserializa e identifica el origen de un webhook crudo y lo normaliza.
    """

    @abstractmethod
    def parsear(self, raw: Union[bytes, str, dict[str, Any]]) -> MensajeEntrante:
        """
        :param raw: payload como bytes, str JSON o dict ya deserializado.
        :return: el `MensajeEntrante` normalizado.
        :raises OrigenNoSoportado: si el origen no corresponde a una plataforma soportada.
        :raises ValueError: si el payload no es JSON válido o no contiene un mensaje.
        """
