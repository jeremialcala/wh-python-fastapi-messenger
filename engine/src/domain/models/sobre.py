# -*- coding: utf-8 -*-
"""
    El sobre que se pasan los workers del motor por el stream `MOTOR` de Bifröst (ADR-0008, punto 6): lo que llegó
    del gateway, sin lo que ningún paso necesita, y lo que añade cada paso. Ningún worker guarda nada entre
    mensajes: todo lo que el siguiente necesita va aquí. Es el contrato interno del motor, versionado con
    `schemaVersion` (docs/02-design/contracts/asyncapi-motor.yaml).

    Los campos que vienen del gateway conservan sus nombres del contrato v2 (`shared.contract`); los que añade el
    motor van en el idioma del motor. Se lee estricto, como el contrato v2: un campo que falta o de otro tipo es un
    sobre roto, no un valor por defecto.

        motor.clasificado.{partición}.{botId}.{contactId}    MensajeClasificado, del clasificador al coordinador
"""
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ESQUEMA = 1

# La partición es la del evento del gateway, que nadie vuelve a calcular (ADR-0008, punto 2).
PARTICION = r"^[0-9]{1,2}$"

# Lo que decide el clasificador de la entrada. Los cuatro primeros los da Claude; los demás, el worker:
#   rechazo     Claude rechazó el mensaje (`stop_reason: "refusal"`)
#   error       no hubo veredicto válido tras todos los intentos
#   sin_texto   el mensaje no trae texto que clasificar (una imagen sin pie, una ubicación...)
Motivo = Literal["ninguno", "inyeccion", "abuso", "otro", "rechazo", "error", "sin_texto"]
MOTIVOS_DE_CLAUDE = ("ninguno", "inyeccion", "abuso", "otro")

# La intención, entre unas pocas genéricas mientras el clasificador no lea los intents del bot. Ningún texto libre
# del modelo pasa de aquí (ADR-0009, punto 3).
Etiqueta = Literal["saludo", "pregunta", "pedido", "queja", "despedida", "otro"]
ETIQUETAS = ("saludo", "pregunta", "pedido", "queja", "despedida", "otro")


def subject_clasificado(particion: str, bot_id, contact_id) -> str:
    """Dónde publica el clasificador, en el stream MOTOR."""
    return f"motor.clasificado.{particion}.{bot_id}.{contact_id}"


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ContactoDelCanal(_Estricto):
    """
        A quién se responde: el contacto del gateway sin su nombre, que ningún paso necesita. Dato personal: va al
        notificador, nunca a Claude.
    """
    uuid: UUID
    waId: Optional[str] = None
    fbId: Optional[str] = None
    igsid: Optional[str] = None


class Entrada(_Estricto):
    """Lo que dijo la persona, saneado: el texto y el tipo de cada adjunto, nunca su dirección."""
    texto: str = Field(max_length=4096)
    adjuntos: list[str] = Field(default_factory=list, max_length=10)


class Entidad(_Estricto):
    """Un dato que el clasificador sacó del texto de la persona."""
    nombre: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    valor: str = Field(max_length=200)


class Clasificacion(_Estricto):
    """
        El veredicto del clasificador. Fail-closed (ADR-0005, que ADR-0009 mantiene): solo `permitido` deja seguir
        al mensaje, y solo cuando Claude no vio ningún motivo para pararlo.
    """
    permitido: bool
    motivo: Motivo
    etiqueta: Optional[Etiqueta] = None
    confianza: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    entidades: list[Entidad] = Field(default_factory=list, max_length=10)
    # El modelo que decidió, o None si no se le preguntó.
    modelo: Optional[str] = None

    @classmethod
    def sin_veredicto(cls, motivo: Literal["rechazo", "error", "sin_texto"],
                      modelo: Optional[str] = None) -> "Clasificacion":
        """Un mensaje que no sigue, sin que Claude lo haya clasificado."""
        return cls(permitido=False, motivo=motivo, modelo=modelo)


class _Sobre(_Estricto):
    schemaVersion: Literal[1]
    botId: UUID
    clientId: UUID
    messageId: str = Field(min_length=1)
    channel: Literal["whatsapp", "messenger", "instagram"]
    receivedAt: datetime
    orderKey: str = Field(min_length=1)
    contact: ContactoDelCanal


class MensajeClasificado(_Sobre):
    """Lo que publica el clasificador: el mensaje, lo que dijo la persona y el veredicto."""
    entrada: Entrada
    clasificacion: Clasificacion
