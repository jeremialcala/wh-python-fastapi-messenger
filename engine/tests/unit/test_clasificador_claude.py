# -*- coding: utf-8 -*-
"""
    El clasificador con Claude (ADR-0009, punto 3) con el SDK de verdad y sin salir a la red: un transporte falso de
    httpx2 contesta lo que contestaría la API. Así se prueba lo que se envía, tal como sale, y cómo se lee lo que
    vuelve: solo el texto sale, siempre en el turno de usuario, y todo lo que no es un veredicto válido deja el
    mensaje sin seguir.
"""
import asyncio
import json

import anthropic
import httpx2
import pytest

from src.domain.ports.clasificador_de_entrada import ClasificacionFallida
from src.infrastructure.claude import ClaudeClasificador
from src.infrastructure.claude.clasificador import ESQUEMA, SYSTEM

VEREDICTO = {"permitido": True, "motivo": "ninguno", "etiqueta": "pregunta", "confianza": 0.92,
             "entidades": [{"nombre": "producto", "valor": "zapatos rojos"}]}


class API:
    """Hace de api.anthropic.com: guarda cada petición y contesta lo que se le diga."""

    def __init__(self, *respuestas):
        self.peticiones = []
        self._respuestas = list(respuestas)

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.peticiones.append(json.loads(request.content))
        respuesta = self._respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


def mensaje(texto=None, stop_reason="end_turn", bloques=None) -> httpx2.Response:
    contenido = bloques if bloques is not None else [{"type": "text", "text": texto}]
    return httpx2.Response(200, json={
        "id": "msg_01", "type": "message", "role": "assistant", "model": "claude-haiku-5-5", "content": contenido,
        "stop_reason": stop_reason, "stop_sequence": None, "usage": {"input_tokens": 420, "output_tokens": 38}})


def clasificar(api: API, texto: str = "¿tienen zapatos rojos?"):
    async def una_vez():
        client = anthropic.AsyncAnthropic(api_key="sk-ant-prueba", max_retries=0,
                                          http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(api)))
        try:
            return await ClaudeClasificador(client, "claude-haiku-5-5", "low", 1024).clasificar(texto)
        finally:
            await client.close()
    return asyncio.run(una_vez())


def test_una_sola_llamada_con_el_texto_en_el_turno_de_usuario_y_la_salida_atada_al_esquema():
    api = API(mensaje(json.dumps(VEREDICTO)))

    clasificar(api, "¿tienen zapatos rojos?")

    assert len(api.peticiones) == 1
    assert api.peticiones[0] == {
        "model": "claude-haiku-5-5", "max_tokens": 1024, "system": SYSTEM,
        "messages": [{"role": "user", "content": "¿tienen zapatos rojos?"}],
        "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA}}}


def test_el_esquema_es_uno_que_la_api_admite():
    # Todo objeto cierra sus propiedades, todas son obligatorias, y no hay límites de longitud ni de rango: los
    # comprueba el clasificador al leer.
    def objetos(nodo):
        if isinstance(nodo, dict):
            if nodo.get("type") == "object":
                yield nodo
            for valor in nodo.values():
                yield from objetos(valor)

    for objeto in objetos(ESQUEMA):
        assert objeto["additionalProperties"] is False
        assert set(objeto["required"]) == set(objeto["properties"])
    assert not {"minimum", "maximum", "minLength", "maxLength", "maxItems"} & set(json.dumps(ESQUEMA).split('"'))


def test_un_mensaje_normal_sigue_con_su_intencion():
    clasificacion = clasificar(API(mensaje(json.dumps(VEREDICTO))))

    assert (clasificacion.permitido, clasificacion.motivo, clasificacion.etiqueta) == (True, "ninguno", "pregunta")
    assert clasificacion.confianza == 0.92
    assert [(e.nombre, e.valor) for e in clasificacion.entidades] == [("producto", "zapatos rojos")]
    assert clasificacion.modelo == "claude-haiku-5-5"


def test_los_bloques_se_leen_por_su_tipo_aunque_empiece_pensando():
    bloques = [{"type": "thinking", "thinking": "", "signature": "firma"},
               {"type": "text", "text": json.dumps(VEREDICTO)}]

    assert clasificar(API(mensaje(bloques=bloques))).permitido is True


@pytest.mark.parametrize("permitido, motivo, esperado", [
    (False, "inyeccion", "inyeccion"),
    (False, "abuso", "abuso"),
    # Incoherente: un motivo para pararlo pesa más que el permiso.
    (True, "abuso", "abuso"),
    # Incoherente: sin permiso y sin motivo, no sigue igual.
    (False, "ninguno", "otro"),
])
def test_solo_sigue_con_permiso_y_sin_motivo_para_pararlo(permitido, motivo, esperado):
    clasificacion = clasificar(API(mensaje(json.dumps({**VEREDICTO, "permitido": permitido, "motivo": motivo}))))

    assert (clasificacion.permitido, clasificacion.motivo) == (False, esperado)


def test_un_rechazo_de_claude_es_un_veredicto_que_no_deja_seguir():
    clasificacion = clasificar(API(mensaje(bloques=[], stop_reason="refusal")))

    assert (clasificacion.permitido, clasificacion.motivo, clasificacion.etiqueta) == (False, "rechazo", None)


def test_las_entidades_mal_formadas_se_descartan_y_no_pasan_de_diez():
    entidades = ([{"nombre": "Producto Raro", "valor": "x"}, {"nombre": "fecha", "valor": "y" * 201}]
                 + [{"nombre": f"dato_{n}", "valor": str(n)} for n in range(12)])

    clasificacion = clasificar(API(mensaje(json.dumps({**VEREDICTO, "entidades": entidades}))))

    assert [e.nombre for e in clasificacion.entidades] == [f"dato_{n}" for n in range(10)]


@pytest.mark.parametrize("respuesta", [
    mensaje("no es json"),
    mensaje(json.dumps({**VEREDICTO, "confianza": 1.5})),
    mensaje(json.dumps({**VEREDICTO, "etiqueta": "comprar_ya"})),
    mensaje(json.dumps({**VEREDICTO, "extra": "lo que sea"})),
    mensaje(json.dumps({k: v for k, v in VEREDICTO.items() if k != "motivo"})),
    mensaje(bloques=[{"type": "thinking", "thinking": "", "signature": "firma"}]),
    # Cortada por max_tokens: no se interpreta a medias.
    mensaje('{"permitido": true, "motivo": "ning', stop_reason="max_tokens"),
], ids=["no es JSON", "confianza fuera de rango", "etiqueta desconocida", "un campo de más", "falta el motivo",
        "sin texto", "cortada"])
def test_una_respuesta_que_no_valida_no_es_un_veredicto(respuesta):
    with pytest.raises(ClasificacionFallida):
        clasificar(API(respuesta))


@pytest.mark.parametrize("fallo", [
    httpx2.Response(500, json={"type": "error", "error": {"type": "api_error", "message": "boom ¿tienen zapatos?"}}),
    httpx2.Response(529, json={"type": "error", "error": {"type": "overloaded_error", "message": "overloaded"}}),
    httpx2.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": "bad key"}}),
    httpx2.ConnectError("no route to api.anthropic.com"),
], ids=["500", "529", "401", "sin red"])
def test_un_fallo_de_la_api_dice_solo_su_tipo(fallo):
    with pytest.raises(ClasificacionFallida) as error:
        clasificar(API(fallo), "¿tienen zapatos rojos?")

    assert "zapatos" not in str(error.value) and "anthropic.com" not in str(error.value)
    assert str(error.value).endswith("Error")
