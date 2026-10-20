# -*- coding: utf-8 -*-
"""
    Puerto para publicar el resultado clasificado aguas abajo.
"""
from abc import ABC, abstractmethod

from src.domain.models import ResultadoClasificado


class MessagePublisher(ABC):
    """
        Publica el `ResultadoClasificado` para que otro servicio lo entregue.
    """

    @abstractmethod
    def publicar(self, resultado: ResultadoClasificado) -> None:
        """
        :param resultado: resultado del pipeline a publicar.
        """
