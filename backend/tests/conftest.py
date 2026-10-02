import pytest

from thodar.config import get_settings
from sqlalchemy.orm import sessionmaker

from thodar.db import init_db, make_engine


@pytest.fixture
def session():
    engine = make_engine("sqlite://")
    init_db(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        yield s


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Tests never call real Sarvam / WhatsApp / ElevenLabs, even if backend/.env holds live keys."""
    for var in ("THODAR_SARVAM_API_KEY", "THODAR_WHATSAPP_TOKEN", "THODAR_ELEVENLABS_API_KEY"):
        monkeypatch.setenv(var, "")
    # Most tests exercise behaviour, not sign-in; tests/test_auth.py switches it back on.
    monkeypatch.setenv("THODAR_AUTH_REQUIRED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
