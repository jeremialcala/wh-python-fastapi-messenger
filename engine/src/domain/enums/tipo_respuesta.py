# -*- coding: utf-8 -*-
"""
    Tipo de estrategia de respuesta según la matriz de clasificación del servicio.
"""
from enum import Enum


class TipoRespuesta(str, Enum):
    """
        Clasificación de la salida del pipeline:

            TEXTO   -> consulta común / flujo conversacional simple; se responde directo.
            ACTION  -> requiere lógica de negocio externa (ej: consultar stock).
            ADJUNTO -> recepción de archivos (imágenes, PDFs, audios, etc.).
    """
    TEXTO = "texto"
    ACTION = "action"
    ADJUNTO = "adjunto"
