# -*- coding: utf-8 -*-
"""
    Origen (plataforma) de un mensaje entrante de Meta.
"""
from enum import Enum


class Origen(str, Enum):
    """
        Plataforma de Meta de la que proviene el mensaje.

            MESSENGER   -> webhook con object == "page"
            WHATSAPP    -> webhook con object == "whatsapp_business_account"
            INSTAGRAM   -> webhook con object == "instagram"
            DESCONOCIDO -> no se pudo identificar el origen
    """
    MESSENGER = "messenger"
    WHATSAPP = "whatsapp"
    INSTAGRAM = "instagram"
    DESCONOCIDO = "desconocido"
