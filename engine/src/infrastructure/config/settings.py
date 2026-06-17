"""
    This is a Pydantic Settings file, we use it for config files and some other variables.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
        Each variable of this class represents a variable on a file config.env
    """
    national_id_url: str
    service_name: str
    db_name: str
    db_host: str
    db_username: str
    db_password: str

    qms_server: str
    qms_port: str

    qms_user: str
    qms_password: str

    queue_name: str

    amqp_exchange: str
    amqp_routing_key: str

    # --- Salida: cola donde se publica el ResultadoClasificado ---
    output_queue_name: str = "meta-classified"
    output_routing_key: str = "meta.classified"

    # --- Ollama (detección de intención) ---
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # --- NeMo Guardrails ---
    guardrails_config_path: str = "src/infrastructure/guardrails/config"

    key_size: int
    private_key_filename: str
    public_key_filename: str

    environment: str
    version: str

    entity_schema: str
    entity_jwk: str
    dto_schema: str
    dto_message: str

    model_config = SettingsConfigDict(env_file="./config.env", extra="ignore")
