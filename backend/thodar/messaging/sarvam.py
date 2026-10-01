"""Thin Sarvam AI client (https://docs.sarvam.ai). Without an API key every call returns None,
so the rest of Thodar runs offline and falls back to rules or a human."""

import json
import logging

import httpx

from thodar.config import get_settings
from thodar.messaging.intents import Kind

log = logging.getLogger(__name__)

LABELS = [k.value for k in Kind]
CLASSIFY_PROMPT = (
    "You label a family's reply to a clinic appointment reminder. Choose exactly one label: "
    "confirm (they will come), reschedule (they want another day; give the date if stated), "
    "moved (they live elsewhere now), wrong_number, stop (no more messages), or needs_staff "
    "(anything else, and ALWAYS for any mention of health, symptoms, medicine or the baby's condition). "
    "Never give advice. Today is {today}. Reply as JSON."
)


class SarvamClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        s = get_settings()
        self.api_key = api_key if api_key is not None else s.sarvam_api_key
        self.base_url = (base_url or s.sarvam_base_url).rstrip("/")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {"api-subscription-key": self.api_key}

    def transcribe(self, audio: bytes, filename: str = "voice.ogg", language: str = "unknown") -> str | None:
        """Saaras v3 speech-to-text; codemix keeps English words in English inside Tamil speech."""
        if not self.enabled:
            return None
        r = httpx.post(
            f"{self.base_url}/speech-to-text",
            headers=self._headers(),
            files={"file": (filename, audio)},
            data={"model": "saaras:v3", "mode": "codemix", "language_code": language},
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("transcript")

    def speak(self, text: str, language: str = "ta-IN", speaker: str = "kavitha") -> str | None:
        """Bulbul v3 text-to-speech. Returns base64 WAV (used for voice reminders)."""
        if not self.enabled:
            return None
        r = httpx.post(
            f"{self.base_url}/text-to-speech",
            headers=self._headers(),
            json={"text": text, "language_code": language, "speaker": speaker, "model": "bulbul:v3"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["audios"][0]

    def classify(self, text: str, today: str) -> tuple[Kind, str | None] | None:
        """Sarvam-105B fallback for replies the rules can't place. Output is constrained to our labels."""
        if not self.enabled:
            return None
        schema = {
            "type": "object",
            "properties": {
                "label": {"type": "string", "enum": LABELS},
                "date": {"type": ["string", "null"], "description": "YYYY-MM-DD if a day is named"},
            },
            "required": ["label", "date"],
            "additionalProperties": False,
        }
        try:
            r = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json={
                    "model": "sarvam-105b",
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": CLASSIFY_PROMPT.format(today=today)},
                        {"role": "user", "content": text},
                    ],
                    "response_format": {"type": "json_schema",
                                        "json_schema": {"name": "reply_label", "schema": schema}},
                },
                timeout=30,
            )
            r.raise_for_status()
            out = json.loads(r.json()["choices"][0]["message"]["content"])
            return Kind(out["label"]), out.get("date")
        except (httpx.HTTPError, KeyError, ValueError) as e:
            log.warning("sarvam classify failed: %s", e)
            return None
