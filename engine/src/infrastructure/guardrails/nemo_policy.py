# -*- coding: utf-8 -*-
"""
    Capa de seguridad de IA con NVIDIA NeMo Guardrails. Implementa el puerto
    `GuardrailsPolicy` aplicando input rails (jailbreak / off-topic) sobre el
    texto antes de la detección de intención.

    `nemoguardrails` se importa de forma diferida: el resto del servicio y los
    tests unitarios (que mockean este puerto) no requieren tenerlo instalado.
"""
import logging
import os
from pathlib import Path

from src.domain.models import ResultadoGuardrail
from src.domain.ports import GuardrailsPolicy

log = logging.getLogger(__name__)

# Desactiva la telemetría anónima de NeMo/Chroma por defecto (SOC2/privacidad).
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

# Sentinel emitido por el bot (rails.co) cuando la entrada es bloqueada.
SENTINEL_BLOQUEO = "GUARDRAIL_BLOQUEADO"


class NeMoGuardrailsPolicy(GuardrailsPolicy):
    """
        Política de guardrails basada en NeMo. Carga la configuración del
        directorio `config_path`, inyectando el modelo y el host de Ollama.
    """

    def __init__(self, config_path: str, ollama_model: str, ollama_base_url: str):
        self._config_path = config_path
        self._ollama_model = ollama_model
        self._ollama_base_url = ollama_base_url
        self._rails = None  # carga perezosa

    def _ensure_rails(self):
        """
            Construye (una sola vez) el motor LLMRails a partir de la config,
            sustituyendo los marcadores ${OLLAMA_MODEL}/${OLLAMA_BASE_URL}.
        """
        if self._rails is not None:
            return self._rails

        # import diferido: nemoguardrails solo se requiere en ejecución real.
        from nemoguardrails import LLMRails, RailsConfig  # pylint: disable=import-outside-toplevel

        base = Path(self._config_path)
        yaml_content = (base / "config.yml").read_text(encoding="utf-8")
        yaml_content = (
            yaml_content
            .replace("${OLLAMA_MODEL}", self._ollama_model)
            .replace("${OLLAMA_BASE_URL}", self._ollama_base_url)
        )
        colang_content = (base / "rails.co").read_text(encoding="utf-8")

        config = RailsConfig.from_content(
            yaml_content=yaml_content,
            colang_content=colang_content,
        )
        self._rails = LLMRails(config)
        return self._rails

    def evaluar(self, texto: str) -> ResultadoGuardrail:
        """
        :param texto: contenido del mensaje a evaluar.
        :return: veredicto permitido/motivo.
        """
        if not texto:
            return ResultadoGuardrail(permitido=True)

        try:
            rails = self._ensure_rails()
            respuesta = rails.generate(messages=[{"role": "user", "content": texto}])
            contenido = self._extraer_contenido(respuesta)
        except Exception as exc:  # pylint: disable=broad-except
            # Fail-closed: ante un fallo de la capa de seguridad, bloqueamos.
            log.error("Fallo evaluando guardrails: %s", exc)
            return ResultadoGuardrail(permitido=False, motivo="error en la capa de seguridad")

        if SENTINEL_BLOQUEO in contenido:
            return ResultadoGuardrail(permitido=False, motivo="entrada bloqueada por guardrails")
        return ResultadoGuardrail(permitido=True)

    @staticmethod
    def _extraer_contenido(respuesta) -> str:
        """
            Normaliza la respuesta de `LLMRails.generate` (dict o GenerationResponse)
            a una cadena de texto.
        """
        if isinstance(respuesta, dict):
            return str(respuesta.get("content", ""))
        contenido = getattr(respuesta, "response", respuesta)
        if isinstance(contenido, list) and contenido:
            primero = contenido[0]
            if isinstance(primero, dict):
                return str(primero.get("content", ""))
            return str(primero)
        return str(contenido)
