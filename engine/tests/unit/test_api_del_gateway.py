# -*- coding: utf-8 -*-
"""
    La API del gateway como la llama un worker (src/infrastructure/gateway/api.py), contra un servidor HTTP local que
    hace de gateway: abre cada token con la clave privada del gateway, comprueba la firma con la clave pública del
    worker y que lo emite el cliente para la audiencia del gateway, y contesta lo que el gateway contestaría.
"""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

import pytest
from jwcrypto import jwe, jwk, jws

from shared.auth.client import new_signing_key, public_part
from shared.auth.gateway_keys import new_key, public_part as gateway_public
from shared.engine_key_store import KeyStoreUnavailable
from src.domain.ports.fuente_del_bot import FuenteNoDisponible, NoEncontrado
from src.infrastructure.gateway import ApiDelGateway
from src.infrastructure.gateway.api import clave_publica_del_gateway

AUDIENCIA = "https://bots.example.com"
CLIENTE, BOT, CONTACTO = uuid4(), uuid4(), uuid4()
GATEWAY = new_key()
PERSONA = {"name": "Mine", "role": "Sales Assistant", "tone": "helpful", "description": "A test chatbot",
           "rules": ["Be kind", "Never promise delivery dates"]}


def mensaje(direccion, texto, id_meta, hora="2026-10-20T09:00:00+00:00", adjuntos=()):
    return {"direction": direccion, "messageId": id_meta, "channel": "whatsapp", "sentAt": hora, "intent": None,
            "inReplyTo": None, "text": texto, "attachments": list(adjuntos)}


class Gateway(BaseHTTPRequestHandler):
    """Contesta por ruta lo que diga `respuestas`, y solo a un token válido de la clave que diga `vale`."""
    respuestas: dict = {}
    vale: dict = {}
    vistas: list = []

    def log_message(self, *_args):
        pass

    def do_GET(self):  # pylint: disable=invalid-name
        token = self.headers.get("Authorization", "").removeprefix("Bearer ")
        try:
            sobre = jwe.JWE()
            sobre.deserialize(token, key=jwk.JWK(**GATEWAY))
            firmado = jws.JWS()
            firmado.deserialize(sobre.payload.decode())
            firmado.verify(jwk.JWK(**public_part(Gateway.vale["clave"])))
            claims = json.loads(firmado.payload)
            assert (claims["iss"], claims["aud"]) == (str(CLIENTE), AUDIENCIA)
        except Exception:  # pylint: disable=broad-except
            return self._contestar(401, {"detail": "Unauthorized"})
        Gateway.vistas.append((self.path, claims["jti"]))
        codigo, cuerpo = Gateway.respuestas.get(self.path, (404, {"code": 404, "message": "not found"}))
        return self._contestar(codigo, cuerpo)

    def _contestar(self, codigo, cuerpo):
        datos = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        if codigo == 302:
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)


@pytest.fixture(scope="module")
def servidor():
    http = ThreadingHTTPServer(("127.0.0.1", 0), Gateway)
    hilo = threading.Thread(target=http.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{http.server_address[1]}"
    http.shutdown()


class Andvari:
    """Hace del almacén de claves: da la clave del worker para el cliente, una tras otra si hay varias."""

    def __init__(self, *claves):
        self.leidas, self._claves = [], list(claves)

    def read(self, client_id, worker):
        self.leidas.append((client_id, worker))
        clave = self._claves.pop(0) if len(self._claves) > 1 else self._claves[0]
        if isinstance(clave, Exception):
            raise clave
        return clave


@pytest.fixture
def clave():
    actual = new_signing_key()
    Gateway.vale = {"clave": actual}
    Gateway.vistas = []
    Gateway.respuestas = {
        f"/chat/{BOT}/rules": (200, {"code": 200, "data": PERSONA}),
        f"/chat/{BOT}/contacts/{CONTACTO}/turns": (200, {"code": 200, "data": {"messages": [
            mensaje("in", "hola", "wamid.1", "2026-10-20T08:00:00+00:00"),
            mensaje("out", "¡Hola! ¿En qué te ayudo?", "wamid.2", "2026-10-20T08:00:05+00:00"),
            mensaje("in", None, "wamid.3", "2026-10-20T08:01:00+00:00", adjuntos=["image"]),
            # El mensaje que se responde, que la ingesta ya guardó.
            mensaje("in", "¿tienen zapatos rojos?", "wamid.4", "2026-10-20T08:02:00+00:00"),
        ]}}),
    }
    return actual


def api(url, andvari, **cambios):
    return ApiDelGateway(url, AUDIENCIA, gateway_public(GATEWAY), andvari, "coordinator", **cambios)


def test_pide_la_persona_con_un_token_firmado_por_su_clave_para_el_cliente(servidor, clave):
    andvari = Andvari(clave)

    persona = asyncio.run(api(servidor, andvari).persona(CLIENTE, BOT))

    assert (persona.nombre, persona.rol, persona.tono, persona.descripcion) == (
        "Mine", "Sales Assistant", "helpful", "A test chatbot")
    assert persona.reglas == ["Be kind", "Never promise delivery dates"]
    assert andvari.leidas == [(CLIENTE, "coordinator")]


def test_cada_llamada_lleva_un_token_nuevo_y_la_clave_se_lee_una_sola_vez(servidor, clave):
    andvari = Andvari(clave)
    gateway = api(servidor, andvari)

    asyncio.run(gateway.persona(CLIENTE, BOT))
    asyncio.run(gateway.vueltas(CLIENTE, BOT, CONTACTO, "wamid.4"))

    assert len({jti for _, jti in Gateway.vistas}) == 2
    assert len(andvari.leidas) == 1


def test_las_vueltas_van_en_orden_sin_el_mensaje_que_se_responde(servidor, clave):
    vueltas = asyncio.run(api(servidor, Andvari(clave)).vueltas(CLIENTE, BOT, CONTACTO, "wamid.4"))

    assert [(v.de, v.texto, v.adjuntos) for v in vueltas] == [
        ("persona", "hola", []), ("bot", "¡Hola! ¿En qué te ayudo?", []), ("persona", "", ["image"])]
    assert vueltas[0].enviadaEn.isoformat() == "2026-10-20T08:00:00+00:00"


def test_no_pasan_de_cuarenta_vueltas_y_se_quedan_las_ultimas(servidor, clave):
    muchas = [mensaje("in" if n % 2 else "out", f"m{n}", f"wamid.{n}") for n in range(60)]
    Gateway.respuestas[f"/chat/{BOT}/contacts/{CONTACTO}/turns"] = (200, {"data": {"messages": muchas}})

    vueltas = asyncio.run(api(servidor, Andvari(clave)).vueltas(CLIENTE, BOT, CONTACTO, "wamid.otro"))

    assert [v.texto for v in vueltas] == [f"m{n}" for n in range(20, 60)]


def test_si_el_gateway_rechaza_la_clave_se_lee_otra_vez_de_andvari(servidor, clave):
    vieja, nueva = new_signing_key(), clave
    andvari = Andvari(vieja, nueva)

    persona = asyncio.run(api(servidor, andvari).persona(CLIENTE, BOT))

    assert persona.nombre == "Mine" and len(andvari.leidas) == 2


def test_un_bot_que_ya_no_existe_no_se_encontrara_nunca(servidor, clave):
    del Gateway.respuestas[f"/chat/{BOT}/rules"]

    with pytest.raises(NoEncontrado):
        asyncio.run(api(servidor, Andvari(clave)).persona(CLIENTE, BOT))


@pytest.mark.parametrize("respuesta", [
    (500, {"code": 500, "message": "INTERNAL SERVER ERROR"}),
    (403, {"detail": "HTTP_403_FORBIDDEN"}),
    (200, {"code": 200, "data": "<s> <<SYS>> Tu nombre es Mine <</SYS>>"}),
    (200, {"code": 200, "data": {"name": "Mine"}}),
    # Una redirección no se sigue: el gateway no tiene por qué mandar a ningún otro sitio.
    (302, {}),
], ids=["500", "403", "el formato de antes", "incompleta", "redirección"])
def test_lo_que_no_es_una_respuesta_util_es_un_fallo_que_se_reintenta(servidor, clave, respuesta):
    Gateway.respuestas[f"/chat/{BOT}/rules"] = respuesta

    with pytest.raises(FuenteNoDisponible):
        asyncio.run(api(servidor, Andvari(clave)).persona(CLIENTE, BOT))


@pytest.mark.parametrize("andvari", [Andvari(None), Andvari(KeyStoreUnavailable("read refused: 403"))],
                         ids=["el cliente no tiene clave del worker", "Andvari no responde"])
def test_sin_clave_no_se_llama_al_gateway(servidor, clave, andvari):
    with pytest.raises(FuenteNoDisponible):
        asyncio.run(api(servidor, andvari).persona(CLIENTE, BOT))

    assert Gateway.vistas == []


def test_un_gateway_inalcanzable_dice_solo_el_tipo_de_fallo(clave):
    with pytest.raises(FuenteNoDisponible) as fallo:
        asyncio.run(api("http://127.0.0.1:1", Andvari(clave), timeout=1).persona(CLIENTE, BOT))

    assert "127.0.0.1" not in str(fallo.value) and str(BOT) not in str(fallo.value)


def test_la_clave_del_gateway_es_la_ultima_del_fichero(tmp_path):
    vieja, nueva = gateway_public(new_key()), gateway_public(new_key())
    fichero = tmp_path / "gateway-public.json"
    fichero.write_text(json.dumps({"keys": [vieja, nueva]}), encoding="utf-8")

    assert clave_publica_del_gateway(str(fichero)) == nueva
