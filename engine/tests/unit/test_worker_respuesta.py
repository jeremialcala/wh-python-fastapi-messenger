# -*- coding: utf-8 -*-
"""
    El worker de respuesta con cada pedido (E5): qué contesta, dónde y con qué cabeceras, cuándo confirma, cuándo
    espera y cuándo descarta. Claude y Bifröst los sustituyen dobles; el de respuesta con Claude se prueba en
    test_redactor_claude.py y el worker contra un NATS de verdad en tests/integration.
"""
import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from shared import bus
from src.domain.models.sobre import Clasificacion, MensajeRespondido, Persona, Vuelta
from src.domain.ports.redactor import Redaccion, RedaccionFallida, Redactor
from src.workers.responder import TEXTOS_FIJOS, Responder, preparar
from src.workers.runtime import Resultado
from src.workers.settings import ResponderSettings

BOT, CLIENTE, CONTACTO = uuid4(), uuid4(), uuid4()
TRAZA = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
PERSONA = Persona(nombre="Mine", rol="Sales Assistant", tono="helpful", reglas=["Be kind"])
VUELTAS = [Vuelta(de="persona", texto="hola", enviadaEn=datetime(2026, 10, 20, 8, tzinfo=timezone.utc))]
PERMITIDO = Clasificacion(permitido=True, motivo="ninguno", etiqueta="pregunta", confianza=0.9,
                          modelo="claude-haiku-5-5")


def pedido(respuesta="claude", persona=PERSONA, vueltas=VUELTAS, **cambios) -> dict:
    return {"schemaVersion": 1, "botId": str(BOT), "clientId": str(CLIENTE), "messageId": "wamid.A",
            "channel": "whatsapp", "receivedAt": "2026-10-20T09:00:00+00:00", "orderKey": f"{BOT}.{CONTACTO}",
            "contact": {"uuid": str(CONTACTO), "waId": "12025550143"},
            "entrada": {"texto": "¿tienen zapatos rojos?", "adjuntos": []},
            "clasificacion": PERMITIDO.model_dump(),
            "pedido": {"respuesta": respuesta, "persona": persona.model_dump() if persona else None,
                       "vueltas": [v.model_dump(mode="json") for v in vueltas]}, **cambios}


class Mensaje:

    def __init__(self, datos, subject=None, entregas=1, headers=None):
        self.data = datos if isinstance(datos, bytes) else json.dumps(datos).encode()
        self.subject = subject or f"motor.pedido.7.{BOT}.{CONTACTO}"
        self.headers = {"traceparent": TRAZA} if headers is None else headers
        self.metadata = SimpleNamespace(num_delivered=entregas)


class Bifrost:

    def __init__(self, rechaza=False):
        self.publicado, self.rechaza = [], rechaza

    async def publish(self, subject, payload, message_id, headers=None):
        if self.rechaza:
            raise bus.BusUnavailable("TimeoutError")
        self.publicado.append(SimpleNamespace(subject=subject, sobre=json.loads(payload), message_id=message_id,
                                              headers=headers or {}))
        return bus.Published(stream="MOTOR", sequence=len(self.publicado), duplicate=False)

    async def close(self):
        pass


class Claude(Redactor):

    def __init__(self, respuesta=None):
        self.pedidos = []
        self._respuesta = respuesta or Redaccion(texto="Sí, tenemos zapatos rojos.", modelo="claude-opus-5-5")

    async def redactar(self, persona, vueltas, texto):
        self.pedidos.append((persona, vueltas, texto))
        if isinstance(self._respuesta, Exception):
            raise self._respuesta
        return self._respuesta


def atender(mensaje, claude=None, bifrost=None, max_deliver=4):
    claude, bifrost = claude or Claude(), bifrost or Bifrost()
    return asyncio.run(Responder(claude, bifrost, max_deliver)(mensaje)), claude, bifrost


def test_con_claude_escribe_la_respuesta_y_la_publica_para_el_notificador():
    resultado, claude, bifrost = atender(Mensaje(pedido()))

    assert resultado is Resultado.CONFIRMADO
    assert claude.pedidos == [(PERSONA, VUELTAS, "¿tienen zapatos rojos?")]
    (publicado,) = bifrost.publicado
    assert publicado.subject == f"motor.respuesta.7.{BOT}.{CONTACTO}"
    assert publicado.message_id == f"respuesta:{BOT}:wamid.A"
    sobre = MensajeRespondido.model_validate(publicado.sobre)
    assert sobre.respuesta.model_dump() == {"texto": "Sí, tenemos zapatos rojos.", "fuente": "claude",
                                            "modelo": "claude-opus-5-5"}
    assert sobre.contact.waId == "12025550143" and sobre.messageId == "wamid.A"


def test_el_sobre_para_el_notificador_no_lleva_la_persona_ni_las_vueltas():
    _, _, bifrost = atender(Mensaje(pedido()))

    sobre = bifrost.publicado[0].sobre
    assert "pedido" not in sobre and "Be kind" not in json.dumps(sobre)


def test_la_traza_sigue_el_hilo_del_mensaje():
    _, _, bifrost = atender(Mensaje(pedido()))

    assert bifrost.publicado[0].headers["traceparent"].split("-")[1] == TRAZA.split("-")[1]


@pytest.mark.parametrize("respuesta", ["no_puedo", "solo_texto", "no_disponible"])
def test_un_texto_fijo_se_contesta_sin_llamar_a_claude(respuesta):
    resultado, claude, bifrost = atender(Mensaje(pedido(respuesta, persona=None, vueltas=[])))

    assert resultado is Resultado.CONFIRMADO and claude.pedidos == []
    assert bifrost.publicado[0].sobre["respuesta"] == {"texto": TEXTOS_FIJOS[respuesta], "fuente": "fijo",
                                                       "modelo": None}


def test_si_claude_rechaza_se_contesta_el_texto_de_no_puedo():
    resultado, _, bifrost = atender(Mensaje(pedido()), claude=Claude(Redaccion(texto=None, modelo="claude-opus-4-8")))

    assert resultado is Resultado.CONFIRMADO
    assert bifrost.publicado[0].sobre["respuesta"]["texto"] == TEXTOS_FIJOS["no_puedo"]


@pytest.mark.parametrize("entrega", [1, 2, 3])
def test_sin_respuesta_de_claude_se_espera_mientras_queden_entregas(entrega):
    resultado, _, bifrost = atender(Mensaje(pedido(), entregas=entrega),
                                    claude=Claude(RedaccionFallida("APITimeoutError")))

    assert resultado is Resultado.EN_ESPERA and bifrost.publicado == []


def test_sin_respuesta_de_claude_en_la_ultima_entrega_se_contesta_no_disponible():
    resultado, _, bifrost = atender(Mensaje(pedido(), entregas=4), claude=Claude(RedaccionFallida("APITimeoutError")))

    assert resultado is Resultado.CONFIRMADO
    assert bifrost.publicado[0].sobre["respuesta"]["texto"] == TEXTOS_FIJOS["no_disponible"]


def test_un_pedido_con_claude_sin_persona_se_contesta_en_vez_de_callar():
    resultado, claude, bifrost = atender(Mensaje(pedido(persona=None)))

    assert resultado is Resultado.CONFIRMADO and claude.pedidos == []
    assert bifrost.publicado[0].sobre["respuesta"]["texto"] == TEXTOS_FIJOS["no_disponible"]


def test_si_bifrost_no_lo_guarda_se_espera():
    resultado, _, _ = atender(Mensaje(pedido()), bifrost=Bifrost(rechaza=True))

    assert resultado is Resultado.EN_ESPERA


@pytest.mark.parametrize("datos, subject", [
    (b"no es json", None),
    (pedido(schemaVersion=2), None),
    ({k: v for k, v in pedido().items() if k != "pedido"}, None),
    (pedido(), f"motor.pedido.7.{uuid4()}.{CONTACTO}"),
    (pedido(), f"motor.clasificado.7.{BOT}.{CONTACTO}"),
], ids=["no JSON", "otra versión", "sin pedido", "otro bot", "otro paso"])
def test_lo_que_nunca_se_podra_responder_se_descarta_sin_llamar_a_claude(datos, subject):
    resultado, claude, bifrost = atender(Mensaje(datos, subject=subject))

    assert resultado is Resultado.DESCARTADO and claude.pedidos == [] and bifrost.publicado == []


def test_el_log_no_lleva_el_texto_ni_el_numero_ni_la_respuesta(caplog):
    caplog.set_level("DEBUG")

    atender(Mensaje(pedido()))
    atender(Mensaje(pedido()), claude=Claude(RedaccionFallida("APITimeoutError")))

    assert caplog.records
    for prohibido in ("zapatos", "12025550143", "wamid", "Be kind"):
        assert prohibido not in caplog.text


class Andvari:

    def __init__(self, clave):
        self.pedidas, self._clave = [], clave

    def api_key(self, worker):
        self.pedidas.append(worker)
        return self._clave


def ajustes(**cambios):
    return ResponderSettings(nats_url="tls://bifrost:4222", andvari_addr="https://andvari:8200",
                             engine_role_id="rol", engine_secret_id_file="/run/andvari/secret-id", **cambios)


def test_al_arrancar_lee_su_propia_clave_y_configura_opus_como_dice_su_configuracion():
    andvari = Andvari("sk-ant-prueba")

    async def arrancar():
        atender_, cerrar = await preparar(ajustes(), 4, andvari)
        redactor = atender_._redactor
        try:
            return (redactor._model, redactor._effort, redactor._max_tokens, redactor._client.timeout,
                    redactor._client.max_retries)
        finally:
            await cerrar()

    assert asyncio.run(arrancar()) == ("claude-opus-5-5", "medium", 4096, 50.0, 1)
    assert andvari.pedidas == ["responder"]


def test_sin_clave_en_andvari_no_arranca():
    with pytest.raises(SystemExit, match="motor/anthropic/responder"):
        asyncio.run(preparar(ajustes(), 4, Andvari(None)))


@pytest.mark.parametrize("cambio", [{"responder_max_tokens": 512}, {"responder_timeout": 90.0},
                                    {"responder_max_retries": 2}])
def test_la_configuracion_no_deja_pasar_limites_que_romperian_el_ack_wait_o_la_respuesta(cambio):
    with pytest.raises(ValueError):
        ajustes(**cambio)
