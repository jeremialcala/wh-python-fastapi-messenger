# -*- coding: utf-8 -*-
"""
    La configuración de los workers, del entorno del contenedor. Ningún secreto va en ella: la contraseña de
    Bifröst llega en el fichero de credenciales que el despliegue monta (repositorio `bifrost`), y la clave de la
    API de Anthropic se lee de Andvari al arrancar (ADR-0009, punto 6).
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    """Lo que necesita cualquier worker: Bifröst y, con su rol `motor-<worker>`, Andvari."""
    model_config = SettingsConfigDict(extra="ignore")

    # Bifröst: lo que deja credenciales/<worker>.env.
    nats_url: str = Field(min_length=7)
    nats_user: str | None = None
    nats_password: str | None = None
    nats_ca: str | None = None
    nats_inbox_prefix: str = "_INBOX"

    # Andvari, con el rol AppRole de este worker.
    andvari_addr: str = Field(min_length=8)
    andvari_ca_file: str | None = None
    engine_role_id: str = Field(min_length=1)
    engine_secret_id_file: str = Field(min_length=1)

    log_level: str = "INFO"


class ClassifierSettings(WorkerSettings):
    """El clasificador (ADR-0009, punto 2). Cambiar de modelo o de esfuerzo es cambiar esto, no el código."""
    classifier_model: str = "claude-haiku-5-5"
    classifier_effort: str = "low"
    # El pensamiento adaptativo de Haiku 5.5 también cuenta: con 256 una respuesta podía quedarse sin sitio
    # (ADR-0009, «Construido»).
    classifier_max_tokens: int = Field(default=1024, ge=256, le=4096)
    # Por intento. Con los 2 reintentos del SDK, el peor caso queda por debajo de los 30 s del ack_wait del
    # consumidor MENSAJES/classifier: si no, Bifröst lo entregaría otra vez mientras aún se clasifica.
    classifier_timeout: float = Field(default=7.0, gt=0, le=8.0)
    classifier_max_retries: int = Field(default=2, ge=0, le=2)


class CoordinatorSettings(WorkerSettings):
    """El coordinador: además, la API de gestión del gateway, con su clave para cada cliente."""
    # Lo mismo que necesita ops.engine_keys del gateway (docs/03-implementation/autenticacion.md).
    gateway_url: str = Field(min_length=8)
    gateway_audience: str = Field(min_length=8)
    gateway_public_keys_file: str = Field(min_length=1)
    gateway_ca_file: str | None = None
    # Por llamada. Son dos por mensaje, muy por debajo de los 30 s del ack_wait de MOTOR/coordinator.
    coordinator_timeout: float = Field(default=5.0, gt=0, le=10.0)


class ResponderSettings(WorkerSettings):
    """El de respuesta (ADR-0009, punto 2). Cambiar de modelo o de esfuerzo es cambiar esto, no el código."""
    responder_model: str = "claude-opus-5-5"
    responder_effort: str = "medium"
    # El pensamiento de Opus 5.5 no se puede apagar y cuenta en max_tokens: con 1024 una respuesta podía cortarse
    # (ADR-0009, «Construido»). A 20 dólares el millón de tokens de salida, 4096 son 8 céntimos en el peor caso.
    responder_max_tokens: int = Field(default=4096, ge=1024, le=16000)
    # Por intento. Con el reintento del SDK, el peor caso queda por debajo de los 120 s del ack_wait de
    # MOTOR/responder.
    responder_timeout: float = Field(default=50.0, gt=0, le=55.0)
    responder_max_retries: int = Field(default=1, ge=0, le=1)


class NotifierSettings(WorkerSettings):
    """El notificador: la API del gateway, para los tokens de Meta, y la Graph API de Meta."""
    gateway_url: str = Field(min_length=8)
    gateway_audience: str = Field(min_length=8)
    gateway_public_keys_file: str = Field(min_length=1)
    gateway_ca_file: str | None = None
    graph_url: str = "https://graph.facebook.com"
    # La más nueva el 2026-10-20. Meta retira cada versión a los dos años: subirla es cambiar esto.
    graph_version: str = Field(default="v26.0", pattern=r"^v[0-9]{2}[.]0$")
    # Por llamada, a Meta y al gateway. Las tres de un mensaje en el peor caso (el gateway dos veces tras un 401, y
    # Meta) quedan por debajo de los 30 s del ack_wait de MOTOR/notifier.
    notifier_timeout: float = Field(default=8.0, gt=0, le=9.0)
