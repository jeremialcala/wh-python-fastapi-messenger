# -*- coding: utf-8 -*-
"""
    Utilidades generales transversales.
"""


def documenting_parameter(*sub):
    """
        This method only replace a value of another functions docstring.
    :param sub:
    :return:
    """
    def dec(obj):
        """
        :param obj:
        :return:
        """
        obj.__doc__ = obj.__doc__.format(*sub)
        return obj
    return dec


def enmascarar(valor: str, visibles: int = 4) -> str:
    """
        Enmascara un identificador/PII para logs de auditoría (OWASP / SOC2),
        dejando visibles solo los últimos `visibles` caracteres.

    :param valor: cadena a enmascarar (teléfono, PSID, wa_id, etc.).
    :param visibles: número de caracteres finales que se conservan.
    :return: cadena enmascarada (ej: "****1226").
    """
    if not valor:
        return ""
    texto = str(valor)
    if len(texto) <= visibles:
        return "*" * len(texto)
    return "*" * (len(texto) - visibles) + texto[-visibles:]
