from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Required: the app refuses to start without a key for the management endpoints.
    admin_api_key: str = Field(min_length=32)
    # Meta App Secret used to verify webhook signatures; a bot's own appSecret overrides it.
    facebook_app_secret: str | None = None

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

    key_size: int
    private_key_filename: str
    public_key_filename: str

    environment: str
    version: str

    verify_token: str

    facebook_graph_url: str
    facebook_whatsapp_message: str
    facebook_graph_version: str

    # hide_input_in_errors: a rejected setting must not be echoed into the startup traceback.
    model_config = SettingsConfigDict(env_file="config.env", hide_input_in_errors=True)
