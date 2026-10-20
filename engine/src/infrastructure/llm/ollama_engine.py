# -*- coding: utf-8 -*-
"""
    Motor de detección de intención basado en Ollama (instancia local).
    Implementa el puerto `IntentEngine`.
"""
import json
import logging

from ollama import Client
from pydantic import BaseModel, ValidationError, field_validator

from src.domain.enums import TipoRespuesta
from src.domain.models import Intencion, MensajeEntrante
from src.domain.ports import IntentEngine
from .prompts import SYSTEM_PROMPT, USER_TEMPLATE

log = logging.getLogger(__name__)

# Umbral por debajo del cual no confiamos en la clasificación del modelo.
CONFIANZA_MINIMA = 0.3


class _RespuestaLLM(BaseModel):
    """
        Esquema de validación de la salida cruda del LLM. Si el modelo devuelve
        algo fuera de contrato, la validación falla y caemos al fallback seguro.
    """
    etiqueta: str = "desconocida"
    tipo_respuesta: TipoRespuesta = TipoRespuesta.TEXTO
    confianza: float = 0.0
    entidades: dict = {}
    razonamiento: str = ""

    @field_validator("tipo_respuesta", mode="before")
    @classmethod
    def _normalizar_tipo(cls, v):
        """Acepta el valor en cualquier capitalización; desconocido -> TEXTO."""
        try:
            return TipoRespuesta(str(v).strip().lower())
        except ValueError:
            return TipoRespuesta.TEXTO

    @field_validator("confianza", mode="before")
    @classmethod
    def _acotar_confianza(cls, v):
        try:
            return max(0.0, min(1.0, float(v)))
        except (ValueError, TypeError):
            return 0.0


class OllamaIntentEngine(IntentEngine):
    """
        Detecta la intención llamando a un modelo servido por Ollama.

        No confía en la salida del modelo: valida el JSON y, ante cualquier
        fallo o baja confianza, retorna una intención de tipo TEXTO (fallback
        seguro). Si el mensaje trae adjuntos, clasifica como ADJUNTO sin invocar
        al LLM.
    """

    def __init__(self, host: str, model: str, client: Client | None = None,
                 system_prompt: str | None = None, user_template: str | None = None,
                 timeout_s: float = 15):
        self._model = model
        # El timeout se fija en el cliente (ollama lo propaga a httpx) para
        # evitar que una llamada colgada bloquee el hilo de procesamiento.
        self._client = client or Client(host=host, timeout=timeout_s)
        self._system_prompt = system_prompt or SYSTEM_PROMPT
        self._user_template = user_template or USER_TEMPLATE

    def detectar(self, mensaje: MensajeEntrante) -> Intencion:
        """
        :param mensaje: mensaje normalizado a clasificar.
        :return: la intención detectada (o fallback seguro).
        """
        if mensaje.tiene_adjuntos:
            return Intencion(
                etiqueta="adjunto_recibido",
                tipo_respuesta=TipoRespuesta.ADJUNTO,
                confianza=1.0,
                razonamiento="El mensaje contiene adjuntos.",
            )

        if not mensaje.texto:
            return self._fallback("mensaje vacío")

        try:
            contenido = self._invocar(mensaje.texto)
            datos = _RespuestaLLM.model_validate(json.loads(contenido))
        except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
            log.warning("Respuesta de Ollama no válida: %s", exc)
            return self._fallback("respuesta del modelo no válida")
        except Exception as exc:  # pylint: disable=broad-except
            log.warning("Fallo invocando a Ollama: %s", exc)
            return self._fallback("error de comunicación con el modelo")

        if datos.confianza < CONFIANZA_MINIMA:
            return self._fallback(f"confianza baja ({datos.confianza:.2f})")

        return Intencion(
            etiqueta=datos.etiqueta,
            tipo_respuesta=datos.tipo_respuesta,
            confianza=datos.confianza,
            entidades=datos.entidades,
            razonamiento=datos.razonamiento,
        )

    def _invocar(self, texto: str) -> str:
        """
            Llama al chat de Ollama pidiendo salida JSON.
        :return: el contenido textual (JSON) de la respuesta del modelo.
        """
        respuesta = self._client.chat(
            model=self._model,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": self._user_template.format(texto=texto)},
            ],
            format="json",
        )
        return respuesta["message"]["content"]

    @staticmethod
    def _fallback(motivo: str) -> Intencion:
        """Intención segura por defecto cuando no se puede clasificar."""
        return Intencion(
            etiqueta="desconocida",
            tipo_respuesta=TipoRespuesta.TEXTO,
            confianza=0.0,
            razonamiento=f"fallback: {motivo}",
        )
