# -*- coding: utf-8 -*-
"""
    El worker clasificador con cada mensaje de MENSAJES (E3): lo que publica, dónde y con qué cabeceras, cuándo
    confirma, cuándo espera y cuándo descarta. Claude y Bifröst los sustituyen dobles; el clasificador con Claude se
    prueba en test_clasificador_claude.py y el worker contra un NATS de verdad en tests/integration.
"""
import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from shared import bus
from src.domain.models.sobre import Clasificacion, Entidad, MensajeClasificado
from src.domain.ports.clasificador_de_entrada import ClasificacionFallida, ClasificadorDeEntrada
from src.workers.classifier import Clasificar, preparar
from src.workers.runtime import Resultado
from src.workers.settings import ClassifierSettings

BOT, CLIENTE, CONTACTO = uuid4(), uuid4(), uuid4()
TRAZA = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
NUMERO = "12025550143"


def whatsapp(cuerpo: dict) -> dict:
    return {"messaging_product": "whatsapp",
            "contacts": [{"profile": {"name": "Ana"}, "wa_id": NUMERO}],
            "messages": [{"from": NUMERO, "id": "wamid.A", "timestamp": "1760950000", **cuerpo}]}


def evento(mensaje: dict | None = None, **cambios) -> dict:
    return {"schemaVersion": 2, "botId": str(BOT), "clientId": str(CLIENTE), "messageId": "wamid.A",
            "message": mensaje or whatsapp({"type": "text", "text": {"body": "¿tienen zapatos rojos?"}}),
            "channel": "whatsapp", "receivedAt": "2026-10-20T09:00:00+00:00", "orderKey": f"{BOT}.{CONTACTO}",
            "contact": {"uuid": str(CONTACTO), "name": "Ana", "waId": NUMERO}, **cambios}


class Mensaje:
    """Hace de un mensaje de JetStream: guarda si se confirmó o se terminó."""

    def __init__(self, datos, subject=None, entregas=1, headers=None):
        self.data = datos if isinstance(datos, bytes) else json.dumps(datos).encode()
        self.subject = subject or f"gateway.message.7.{BOT}.{CONTACTO}"
        self.headers = {"traceparent": TRAZA} if headers is None else headers
        self.metadata = SimpleNamespace(num_delivered=entregas)
        self.hecho = None

    async def ack(self):
        self.hecho = "ack"

    async def term(self):
        self.hecho = "term"


class Bifrost:
    """Hace de Bifröst: guarda lo que se publica, o lo rechaza."""

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


class Claude(ClasificadorDeEntrada):
    """Hace del clasificador con Claude: guarda lo que se le pasa y contesta lo que se le diga."""

    def __init__(self, respuesta=None):
        self.textos = []
        self._respuesta = respuesta or Clasificacion(
            permitido=True, motivo="ninguno", etiqueta="pregunta", confianza=0.9,
            entidades=[Entidad(nombre="producto", valor="zapatos rojos")], modelo="claude-haiku-5-5")

    async def clasificar(self, texto):
        self.textos.append(texto)
        if isinstance(self._respuesta, Exception):
            raise self._respuesta
        return self._respuesta


def atender(mensaje, claude=None, bifrost=None, max_deliver=4):
    claude, bifrost = claude or Claude(), bifrost or Bifrost()

    async def una_vez():
        resultado = await Clasificar(claude, bifrost, max_deliver)(mensaje)
        # Lo que haría el bucle del worker con el resultado (runtime.resolver).
        if resultado is Resultado.CONFIRMADO:
            await mensaje.ack()
        elif resultado is Resultado.DESCARTADO:
            await mensaje.term()
        return resultado

    return asyncio.run(una_vez()), claude, bifrost


def test_un_mensaje_sale_clasificado_en_su_particion_y_se_confirma():
    mensaje = Mensaje(evento())

    resultado, claude, bifrost = atender(mensaje)

    assert resultado is Resultado.CONFIRMADO and mensaje.hecho == "ack"
    (publicado,) = bifrost.publicado
    assert publicado.subject == f"motor.clasificado.7.{BOT}.{CONTACTO}"
    assert publicado.message_id == f"clasificado:{BOT}:wamid.A"
    sobre = MensajeClasificado.model_validate(publicado.sobre)
    assert (sobre.botId, sobre.clientId, sobre.contact.uuid, sobre.contact.waId) == (BOT, CLIENTE, CONTACTO, NUMERO)
    assert sobre.entrada.texto == "¿tienen zapatos rojos?" and sobre.entrada.adjuntos == []
    assert (sobre.clasificacion.permitido, sobre.clasificacion.etiqueta) == (True, "pregunta")


def test_a_claude_solo_le_llega_el_texto():
    _, claude, _ = atender(Mensaje(evento()))

    assert claude.textos == ["¿tienen zapatos rojos?"]


def test_el_sobre_no_lleva_el_nombre_ni_el_mensaje_de_meta():
    _, _, bifrost = atender(Mensaje(evento()))

    sobre = bifrost.publicado[0].sobre
    assert "name" not in sobre["contact"] and "message" not in sobre
    assert "Ana" not in json.dumps(sobre)


def test_la_traza_sigue_el_hilo_del_mensaje():
    _, _, bifrost = atender(Mensaje(evento()))

    saliente = bifrost.publicado[0].headers["traceparent"]
    assert saliente.split("-")[1] == TRAZA.split("-")[1]
    assert saliente.split("-")[2] != TRAZA.split("-")[2]


def test_el_texto_se_sanea_antes_de_salir():
    mensaje = Mensaje(evento(whatsapp({"type": "text", "text": {"body": "  hola\x00\x07 ﬁn  "}})))

    _, claude, bifrost = atender(mensaje)

    assert claude.textos == ["hola fin"]
    assert bifrost.publicado[0].sobre["entrada"]["texto"] == "hola fin"


def test_un_mensaje_de_messenger_tambien_se_lee():
    contenido = {"sender": {"id": "6789"}, "recipient": {"id": "1"}, "timestamp": 1760950000000,
                 "message": {"mid": "m_1", "text": "buenas tardes"}}
    mensaje = Mensaje(evento(contenido, channel="messenger", messageId="m_1",
                             contact={"uuid": str(CONTACTO), "fbId": "6789"}))

    _, claude, bifrost = atender(mensaje)

    assert claude.textos == ["buenas tardes"]
    assert bifrost.publicado[0].sobre["contact"]["fbId"] == "6789"


def test_un_mensaje_sin_texto_no_llega_a_claude_y_sale_sin_seguir():
    mensaje = Mensaje(evento(whatsapp({"type": "image", "image": {"id": "media-1", "mime_type": "image/jpeg"}})))

    resultado, claude, bifrost = atender(mensaje)

    assert resultado is Resultado.CONFIRMADO and claude.textos == []
    sobre = bifrost.publicado[0].sobre
    assert sobre["entrada"] == {"texto": "", "adjuntos": ["image"]}
    assert sobre["clasificacion"]["permitido"] is False and sobre["clasificacion"]["motivo"] == "sin_texto"
    assert "media-1" not in json.dumps(sobre)


def test_un_rechazo_sale_sin_seguir_a_la_primera():
    claude = Claude(Clasificacion.sin_veredicto("rechazo", modelo="claude-haiku-5-5"))

    resultado, _, bifrost = atender(Mensaje(evento()), claude=claude)

    assert resultado is Resultado.CONFIRMADO
    assert bifrost.publicado[0].sobre["clasificacion"]["motivo"] == "rechazo"


@pytest.mark.parametrize("entrega", [1, 2, 3])
def test_sin_veredicto_se_espera_mientras_queden_entregas(entrega):
    mensaje = Mensaje(evento(), entregas=entrega)

    resultado, _, bifrost = atender(mensaje, claude=Claude(ClasificacionFallida("APITimeoutError")))

    assert resultado is Resultado.EN_ESPERA and mensaje.hecho is None and bifrost.publicado == []


def test_sin_veredicto_en_la_ultima_entrega_sale_sin_seguir():
    mensaje = Mensaje(evento(), entregas=4)

    resultado, _, bifrost = atender(mensaje, claude=Claude(ClasificacionFallida("APITimeoutError")))

    assert resultado is Resultado.CONFIRMADO and mensaje.hecho == "ack"
    clasificacion = bifrost.publicado[0].sobre["clasificacion"]
    assert (clasificacion["permitido"], clasificacion["motivo"], clasificacion["modelo"]) == (False, "error", None)


def test_sin_limite_de_entregas_se_espera_siempre():
    resultado, _, _ = atender(Mensaje(evento(), entregas=50), claude=Claude(ClasificacionFallida("x")),
                              max_deliver=-1)

    assert resultado is Resultado.EN_ESPERA


def test_si_bifrost_no_lo_guarda_se_espera_y_no_se_confirma():
    mensaje = Mensaje(evento())

    resultado, _, _ = atender(mensaje, bifrost=Bifrost(rechaza=True))

    assert resultado is Resultado.EN_ESPERA and mensaje.hecho is None


@pytest.mark.parametrize("datos, subject", [
    (b"no es json", None),
    (b"\xff\xfe", None),
    (evento(schemaVersion=1), None),
    (evento(botId="no-es-un-uuid"), None),
    (evento(contact={"uuid": str(CONTACTO), "phone": NUMERO}), None),
    (evento(), f"gateway.message.7.{uuid4()}.{CONTACTO}"),
    (evento(), f"gateway.message.7.{BOT}.{uuid4()}"),
    (evento(), f"gateway.message.siete.{BOT}.{CONTACTO}"),
    (evento(), f"otra.cosa.7.{BOT}.{CONTACTO}"),
], ids=["no JSON", "no UTF-8", "otra versión", "bot inválido", "campo desconocido", "otro bot", "otro contacto",
        "partición inválida", "otro sujeto"])
def test_lo_que_nunca_se_podra_clasificar_se_descarta_sin_llegar_a_claude(datos, subject):
    mensaje = Mensaje(datos, subject=subject)

    resultado, claude, bifrost = atender(mensaje)

    assert resultado is Resultado.DESCARTADO and mensaje.hecho == "term"
    assert claude.textos == [] and bifrost.publicado == []


def test_el_log_no_lleva_el_texto_ni_el_numero_ni_el_id_del_mensaje(caplog):
    caplog.set_level("DEBUG")

    atender(Mensaje(evento()))
    atender(Mensaje(evento(), entregas=1), claude=Claude(ClasificacionFallida("APITimeoutError")))
    atender(Mensaje(evento(contact={"uuid": str(CONTACTO), "phone": NUMERO})))

    assert caplog.records
    for prohibido in ("zapatos", NUMERO, "wamid", "Ana"):
        assert prohibido not in caplog.text


def test_un_mensaje_sin_traza_empieza_una():
    _, _, bifrost = atender(Mensaje(evento(), headers={}))

    assert bifrost.publicado[0].headers["traceparent"].startswith("00-")


class Andvari:
    """Hace del almacén de claves de Andvari: dice la clave de Anthropic de cada worker."""

    def __init__(self, clave):
        self.pedidas, self._clave = [], clave

    def api_key(self, worker):
        self.pedidas.append(worker)
        return self._clave


def ajustes(**cambios):
    return ClassifierSettings(nats_url="tls://bifrost:4222", andvari_addr="https://andvari:8200",
                              engine_role_id="rol", engine_secret_id_file="/run/andvari/secret-id", **cambios)


def test_al_arrancar_lee_su_propia_clave_y_configura_claude_como_dice_su_configuracion():
    andvari = Andvari("sk-ant-prueba")

    async def arrancar():
        atender, cerrar = await preparar(ajustes(classifier_timeout=5.0, classifier_model="claude-haiku-5-5"), 4,
                                         andvari)
        claude = atender._clasificador
        try:
            return claude._model, claude._client.timeout, claude._client.max_retries, atender._max_deliver
        finally:
            await cerrar()

    assert asyncio.run(arrancar()) == ("claude-haiku-5-5", 5.0, 2, 4)
    assert andvari.pedidas == ["classifier"]


def test_sin_clave_en_andvari_no_arranca():
    with pytest.raises(SystemExit, match="motor/anthropic/classifier"):
        asyncio.run(preparar(ajustes(), 4, Andvari(None)))


@pytest.mark.parametrize("cambio", [{"classifier_max_tokens": 128}, {"classifier_timeout": 20.0},
                                    {"classifier_max_retries": 5}])
def test_la_configuracion_no_deja_pasar_limites_que_romperian_el_ack_wait_o_el_veredicto(cambio):
    with pytest.raises(ValueError):
        ajustes(**cambio)
