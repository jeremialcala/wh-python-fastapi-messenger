from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    client_id: str
    national_id_url: str

    db_name: str
    db_host: str
    db_username: str
    db_password: str

    sender_email: str
    sender_password: str

    gmail_server_url: str
    gmail_server_port: int

    expiration_time: int
    activation_code_length: int
    password_length: int

    qms_server: str
    qms_user: str
    qms_password: str

    jwe_key_size: int

    environment: str
    version: str

    verify_token: str

    facebook_graph_url: str
    facebook_graph_version: str

    model_config = SettingsConfigDict(env_file="config.env")
