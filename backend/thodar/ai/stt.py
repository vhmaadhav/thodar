"""Speech-to-text for families' voice notes.

Providers (pick with THODAR_STT_PROVIDER):
- sarvam: Saaras v3, the event partner's API, hosted in India. Default.
- indicconformer: AI4Bharat IndicConformer 600M (MIT, open weights), self-hosted in India via
  scripts/indicconformer_server.py. Led the independent Vimarsha benchmark (2026) on both splits.
- elevenlabs: Scribe v2. Lowest WER on the independent BRIDGE benchmark (2026), but audio leaves
  India, so it is refused unless THODAR_ALLOW_OFFSHORE_PROCESSING is set.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from thodar.config import Settings, get_settings
from thodar.messaging.sarvam import SarvamClient

log = logging.getLogger(__name__)


class STT(Protocol):
    name: str
    processes_in: str  # where the audio is processed

    def transcribe(self, audio: bytes, filename: str = "voice.ogg", language: str = "ta") -> str | None: ...


@dataclass
class SarvamSTT:
    client: SarvamClient
    name: str = "Sarvam Saaras v3"
    processes_in: str = "India (Sarvam)"

    def transcribe(self, audio: bytes, filename: str = "voice.ogg", language: str = "ta") -> str | None:
        return self.client.transcribe(audio, filename, language="unknown" if language == "auto" else f"{language}-IN")


@dataclass
class IndicConformerSTT:
    url: str
    name: str = "AI4Bharat IndicConformer (self-hosted)"
    processes_in: str = "India (our own server)"

    def transcribe(self, audio: bytes, filename: str = "voice.ogg", language: str = "ta") -> str | None:
        try:
            r = httpx.post(self.url, files={"file": (filename, audio)}, data={"language": language}, timeout=60)
            r.raise_for_status()
            return r.json().get("text")
        except httpx.HTTPError as e:
            log.warning("indicconformer failed: %s", e)
            return None


@dataclass
class ElevenLabsSTT:
    api_key: str
    name: str = "ElevenLabs Scribe v2"
    processes_in: str = "Outside India (ElevenLabs)"

    def transcribe(self, audio: bytes, filename: str = "voice.ogg", language: str = "ta") -> str | None:
        if not self.api_key:
            return None
        lang = {"ta": "tam", "en": "eng"}.get(language, language)
        r = httpx.post("https://api.elevenlabs.io/v1/speech-to-text", headers={"xi-api-key": self.api_key},
                       files={"file": (filename, audio)}, data={"model_id": "scribe_v2", "language_code": lang},
                       timeout=60)
        r.raise_for_status()
        return r.json().get("text")


class OffshoreNotAllowed(RuntimeError):
    pass


def get_stt(settings: Settings | None = None, provider: str | None = None) -> STT:
    s = settings or get_settings()
    choice = (provider or s.stt_provider).lower()
    if choice == "indicconformer":
        return IndicConformerSTT(s.indicconformer_url)
    if choice == "elevenlabs":
        if not s.allow_offshore_processing:
            raise OffshoreNotAllowed(
                "ElevenLabs processes audio outside India. Set THODAR_ALLOW_OFFSHORE_PROCESSING=true only if the "
                "clinic has consent and a lawful basis for cross-border processing.")
        return ElevenLabsSTT(s.elevenlabs_api_key)
    return SarvamSTT(SarvamClient())
