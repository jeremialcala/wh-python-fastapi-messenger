# -*- coding: utf-8 -*-
"""
    La Cloud API de WhatsApp para enviar un texto:

        POST {graph}/{versión}/{phone_number_id}/messages
        {"messaging_product": "whatsapp", "recipient_type": "individual", "to": <número>, "type": "text",
         "text": {"body": <texto>, "preview_url": false}}

    Solo texto, sin vista previa de enlaces (ADR-0009, punto 5), y sin citar el mensaje de la persona (decisión de
    Jeremi del 2026-10-20). Lo que hace con cada error lo dice el `code` de Meta, como pide su documentación de
    errores (developers.facebook.com, consultada el 2026-10-20): los que se arreglan solos se reintentan, el del token
    se reintenta con uno nuevo, y los demás no irán nunca así.

    Ni el log ni las excepciones llevan el texto, el número ni el token. Del error de Meta solo se guarda el código:
    su `message` y sus `details` pueden llevar el número.
"""
import asyncio

import requests

from src.domain.ports.envio import CanalDeMeta, EnvioFallido, EnvioRechazado, TokenRechazado

GRAPH = "https://graph.facebook.com"
VERSION = "v26.0"   # la más nueva el 2026-10-20 (julio de 2026); Meta retira cada versión a los dos años
TIMEOUT = 10        # segundos

# Los que, según Meta, se arreglan solos o esperando.
REINTENTABLES = {1, 2, 4, 130429, 131000, 131016, 131056, 80007}
# Los del token: con uno nuevo del gateway puede ir. 10 y 131005 son permisos, que se arreglan en Meta, no aquí,
# pero dan tiempo a que el operador lo vea mientras Bifröst reintenta.
DEL_TOKEN = {0, 190}
PERMISOS = {10, 131005}


class WhatsAppCloud(CanalDeMeta):
    """La Cloud API de WhatsApp."""

    def __init__(self, url: str = GRAPH, version: str = VERSION, timeout: float = TIMEOUT):
        self._url = url.rstrip("/")
        self._version = version
        self._timeout = timeout

    def _enviar(self, token: str, cuenta: str, destinatario: str, texto: str) -> str:
        cuerpo = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": destinatario,
                  "type": "text", "text": {"body": texto, "preview_url": False}}
        try:
            respuesta = requests.post(f"{self._url}/{self._version}/{cuenta}/messages", json=cuerpo,
                                      headers={"Authorization": f"Bearer {token}"}, timeout=self._timeout,
                                      allow_redirects=False)
        except (requests.RequestException, OSError) as e:
            # Solo el tipo: el texto de estas excepciones lleva la dirección y más.
            raise EnvioFallido(type(e).__name__) from None
        if respuesta.status_code == 200:
            try:
                return respuesta.json()["messages"][0]["id"]
            except (ValueError, KeyError, IndexError, TypeError):
                # Meta dijo que sí sin decir con qué id: no se reintenta, que llegaría dos veces.
                raise EnvioRechazado("aceptado sin id") from None
        codigo = self._codigo(respuesta)
        if codigo in DEL_TOKEN:
            raise TokenRechazado(f"Meta {codigo}")
        motivo = f"Meta {codigo if codigo is not None else respuesta.status_code}"
        if self._se_reintenta(codigo, respuesta.status_code):
            raise EnvioFallido(motivo)
        raise EnvioRechazado(motivo)

    @staticmethod
    def _se_reintenta(codigo: int | None, estado: int) -> bool:
        """Si puede ir más tarde. Sin código de Meta, lo dice el estado HTTP: saturado o caído."""
        if codigo is None:
            return estado >= 500 or estado == 429
        return codigo in REINTENTABLES or codigo in PERMISOS

    @staticmethod
    def _codigo(respuesta: requests.Response) -> int | None:
        try:
            codigo = respuesta.json()["error"]["code"]
        except (ValueError, KeyError, TypeError):
            return None
        return codigo if isinstance(codigo, int) and not isinstance(codigo, bool) else None

    async def enviar_texto(self, token: str, cuenta: str, destinatario: str, texto: str) -> str:
        return await asyncio.to_thread(self._enviar, token, cuenta, destinatario, texto)
