# -*- coding: utf-8 -*-
"""
    Sanitización de entradas (OWASP). Limpia el texto y valida identificadores
    antes de que entren al pipeline.
"""
import re
import unicodedata

# Longitud máxima razonable para un mensaje de chat; recorta entradas abusivas.
MAX_TEXTO = 4096

# Identificadores de Meta: PSID/wa_id/IGSID/mid. Conjunto conservador.
_ID_PERMITIDO = re.compile(r"[^A-Za-z0-9_.:=\-]")
# Caracteres de control (excepto tab/newline) que no deben llegar al LLM.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitizar_texto(texto: object, max_len: int = MAX_TEXTO) -> str:
    """
        Normaliza Unicode (NFKC), elimina caracteres de control, recorta espacios
        y limita la longitud. Mitiga inyección de control y entradas desbordadas.

    :param texto: valor crudo (puede no ser str).
    :param max_len: longitud máxima permitida.
    :return: texto sanitizado.
    """
    if texto is None:
        return ""
    valor = unicodedata.normalize("NFKC", str(texto))
    valor = _CONTROL.sub("", valor)
    valor = valor.strip()
    return valor[:max_len]


def sanitizar_id(valor: object, max_len: int = 128) -> str:
    """
        Valida/limpia un identificador, descartando caracteres no permitidos.
        Mitiga inyección a través de IDs (logs, claves, downstream).

    :param valor: identificador crudo.
    :param max_len: longitud máxima permitida.
    :return: identificador saneado (puede quedar vacío si era inválido).
    """
    if valor is None:
        return ""
    return _ID_PERMITIDO.sub("", str(valor))[:max_len]
