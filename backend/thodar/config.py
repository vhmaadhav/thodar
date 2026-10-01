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

    # Speech-to-text for voice notes: sarvam (default) | indicconformer (self-hosted) | elevenlabs.
    stt_provider: str = "sarvam"
    indicconformer_url: str = "http://localhost:8001/transcribe"
    elevenlabs_api_key: str = ""
    # Health conversations must stay in India unless a clinic explicitly opts in (DPDP Act).
    allow_offshore_processing: bool = False

    # Shared secret the Sarvam voice agent sends when it calls Thodar's tool endpoints.
    voice_tool_key: str = "thodar-dev-tool-key"
    clinic_name: str = "the clinic"
    # Days the clinic runs ANC / immunisation sessions (TN PHCs: Wednesday). Comma-separated.
    session_days: str = "wed"
    # Send the day's reminders automatically at this time (IST), e.g. "09:00". Empty = manual only.
    auto_reminders_at: str = ""
    # Mention Tamil Nadu's Dr Muthulakshmi Reddy maternity-scheme instalments in reminders.
    mrmbs_enabled: bool = True

    # Days after a due date before an item counts as overdue.
    default_grace_days: int = 0


@lru_cache
def get_settings() -> Settings:
    return Settings()
