from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="THODAR_", extra="ignore")

    # SQLite for local development; set to a postgresql+psycopg:// URL in production.
    database_url: str = "sqlite:///./thodar.db"

    # Sarvam AI (https://docs.sarvam.ai). Empty key = offline stubs, used in tests and demos.
    sarvam_api_key: str = ""
    sarvam_base_url: str = "https://api.sarvam.ai"

    # WhatsApp Cloud API (Meta). Empty token = messages are logged, not sent.
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "thodar-dev"

    # Shared secret the Sarvam voice agent sends when it calls Thodar's tool endpoints.
    voice_tool_key: str = "thodar-dev-tool-key"
    clinic_name: str = "the clinic"

    # Days after a due date before an item counts as overdue.
    default_grace_days: int = 0


@lru_cache
def get_settings() -> Settings:
    return Settings()
