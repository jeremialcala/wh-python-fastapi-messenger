# -*- coding: utf-8 -*-
"""
    La API de gestión del gateway para un worker del motor. Cada llamada lleva un token nuevo, firmado con la clave
    que ese worker tiene para el cliente dueño del bot y cifrado para el gateway (`shared.auth.client`,
    docs/03-implementation/autenticacion.md del gateway). Qué rutas alcanza lo decide el gateway por el worker de la
    clave: al coordinador le deja las reglas, las herramientas y las vueltas.

    La clave privada de cada cliente se lee de Andvari la primera vez que hace falta y se guarda en memoria. Si el
    gateway la rechaza (401), se vuelve a leer una vez: puede haber cambiado.

    Nada de lo que se envía ni de lo que vuelve llega al log ni a una excepción: solo el tipo de fallo y el código.
"""
import asyncio
import json
from datetime import datetime
from uuid import UUID

import requests
from pydantic import ValidationError

from shared.auth.client import build_token
from shared.engine_key_store import EngineKeyStore, KeyStoreUnavailable
from src.domain.models.sobre import MAX_VUELTAS, Persona, Vuelta
from src.domain.ports.fuente_del_bot import FuenteDelBot, FuenteNoDisponible, NoEncontrado

TIMEOUT = 5  # segundos por llamada


def clave_publica_del_gateway(path: str) -> dict:
    """
        La clave a la que se cifran los tokens: la última del fichero, que es la más nueva mientras el gateway rota
        la suya (`python -m ops.gateway_key show`).
    """
    with open(path, "r", encoding="utf-8") as file:
        claves = json.load(file)["keys"]
    if not claves:
        raise ValueError("el fichero de claves del gateway no tiene ninguna")
    return claves[-1]


class ApiDelGateway(FuenteDelBot):
    """La API de gestión del gateway con la clave de un worker, para los clientes que haga falta."""

    def __init__(self, url: str, audience: str, gateway_key: dict, store: EngineKeyStore, worker: str,
                 ca_file: str | None = None, timeout: float = TIMEOUT):
        self._url = url.rstrip("/")
        self._audience = audience
        self._gateway_key = gateway_key
        self._store = store
        self._worker = worker
        self._verify = ca_file or True
        self._timeout = timeout
        self._claves: dict[UUID, dict] = {}

    def _clave(self, client_id: UUID, otra_vez: bool = False) -> dict:
        if otra_vez or client_id not in self._claves:
            try:
                clave = self._store.read(client_id, self._worker)
            except KeyStoreUnavailable as e:
                raise FuenteNoDisponible(f"Andvari: {e}") from None
            if clave is None:
                # El cliente no tiene claves del motor: las da de alta ops.engine_keys del gateway.
                raise FuenteNoDisponible("sin clave del worker para el cliente")
            self._claves[client_id] = clave
        return self._claves[client_id]

    def _get(self, client_id: UUID, path: str) -> dict:
        respuesta = self._llamar(client_id, path, self._clave(client_id))
        if respuesta.status_code == 401:
            respuesta = self._llamar(client_id, path, self._clave(client_id, otra_vez=True))
        if respuesta.status_code == 404:
            raise NoEncontrado(path.rsplit("/", 1)[-1])
        if respuesta.status_code != 200:
            raise FuenteNoDisponible(f"el gateway respondió {respuesta.status_code}")
        try:
            return respuesta.json()["data"]
        except (ValueError, KeyError, TypeError):
            raise FuenteNoDisponible("respuesta inesperada") from None

    def _llamar(self, client_id: UUID, path: str, clave: dict) -> requests.Response:
        try:
            token = build_token(clave, client_id, self._audience, self._gateway_key)
        except Exception as e:  # pylint: disable=broad-except
            # Una clave mal formada en Andvari: jwcrypto lo dice con varios tipos de error.
            raise FuenteNoDisponible(f"no se pudo firmar: {type(e).__name__}") from None
        try:
            return requests.get(f"{self._url}{path}", headers={"Authorization": f"Bearer {token}"},
                                timeout=self._timeout, verify=self._verify, allow_redirects=False)
        except (requests.RequestException, OSError) as e:
            # Solo el tipo: el texto de estas excepciones lleva la dirección y más.
            raise FuenteNoDisponible(type(e).__name__) from None

    async def persona(self, client_id: UUID, bot_id: UUID) -> Persona:
        datos = await asyncio.to_thread(self._get, client_id, f"/chat/{bot_id}/rules")
        try:
            return Persona(nombre=datos["name"], rol=datos["role"], tono=datos["tone"],
                           descripcion=datos.get("description") or "",
                           reglas=[regla for regla in datos.get("rules") or [] if isinstance(regla, str)])
        except (KeyError, TypeError, AttributeError, ValidationError):
            raise FuenteNoDisponible("reglas inesperadas") from None

    async def vueltas(self, client_id: UUID, bot_id: UUID, contact_id: UUID, sin: str) -> list[Vuelta]:
        datos = await asyncio.to_thread(self._get, client_id, f"/chat/{bot_id}/contacts/{contact_id}/turns")
        try:
            vueltas = [Vuelta(de="persona" if mensaje["direction"] == "in" else "bot",
                              texto=(mensaje.get("text") or "")[:4096],
                              adjuntos=[str(tipo) for tipo in mensaje.get("attachments") or []][:10],
                              enviadaEn=datetime.fromisoformat(mensaje["sentAt"]),
                              ) for mensaje in datos["messages"]
                       # La ingesta guarda el mensaje justo después de publicarlo: puede estar ya en el historial.
                       if not (mensaje["direction"] == "in" and mensaje.get("messageId") == sin)]
        except (KeyError, TypeError, ValueError, AttributeError):
            # ValidationError es un ValueError.
            raise FuenteNoDisponible("vueltas inesperadas") from None
        return vueltas[-MAX_VUELTAS:]
