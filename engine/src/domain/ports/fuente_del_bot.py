# -*- coding: utf-8 -*-
"""
    Puerto de lo que el coordinador necesita saber del bot y de la conversación para pedir la respuesta: la persona
    del bot con sus reglas, y las últimas vueltas. Lo guarda el gateway (ADR-0017), y el motor lo pide con la clave
    de cada worker para el cliente dueño del bot (ADR-0022 del gateway).
"""
from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.models.sobre import Persona, Vuelta


class NoEncontrado(Exception):
    """El bot o el contacto ya no existen: el mensaje no se podrá responder nunca."""


class FuenteNoDisponible(Exception):
    """
        No se pudo preguntar, o la respuesta no sirve. Lleva el tipo de fallo, nunca lo que se envió ni lo que
        volvió. Quien llama vuelve a intentarlo mientras le queden entregas.
    """


class FuenteDelBot(ABC):
    """Lo que el coordinador lee del gateway."""

    @abstractmethod
    async def persona(self, client_id: UUID, bot_id: UUID) -> Persona:
        """
        :return: quién es el bot y sus reglas.
        :raises NoEncontrado: si el bot ya no existe.
        :raises FuenteNoDisponible: si no se pudo saber.
        """

    @abstractmethod
    async def vueltas(self, client_id: UUID, bot_id: UUID, contact_id: UUID, sin: str) -> list[Vuelta]:
        """
        :param sin: el id de Meta del mensaje que se responde, que no es una vuelta anterior aunque ya esté guardado.
        :return: las últimas vueltas de la conversación, la más antigua primero.
        :raises NoEncontrado: si el contacto ya no existe.
        :raises FuenteNoDisponible: si no se pudo saber.
        """
