"""Thin Sarvam AI client (https://docs.sarvam.ai). Without an API key every call returns None,
so the rest of Thodar runs offline and falls back to rules or a human."""

import json
import logging
import time

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


# Register columns Sarvam Vision should read off a photographed page, by register type.
# Keys are schema field names; values are the importer's column names.
REGISTER_FIELDS: dict[str, dict[str, tuple[str, str]]] = {
    "anc": {
        "rch_id": ("RCH ID", "12-digit RCH ID, if written"),
        "name": ("Name", "Mother's name as written"),
        "mobile": ("Mobile", "Mobile number"),
        "village": ("Village", "Village or area"),
        "lmp": ("LMP", "Last menstrual period date, DD-MM-YYYY"),
        "anc1": ("ANC1", "Date of 1st antenatal visit, DD-MM-YYYY, empty if blank"),
        "anc2": ("ANC2", "Date of 2nd antenatal visit, DD-MM-YYYY, empty if blank"),
        "anc3": ("ANC3", "Date of 3rd antenatal visit, DD-MM-YYYY, empty if blank"),
        "anc4": ("ANC4", "Date of 4th antenatal visit, DD-MM-YYYY, empty if blank"),
    },
    "delivery": {
        "date": ("Date", "Date of delivery, DD-MM-YYYY"),
        "mother_name": ("Mother name", "Mother's name as written"),
        "phone": ("Ph no", "Phone number"),
        "rch_no": ("RCH no", "12-digit RCH number, if written"),
        "baby_sex": ("Baby sex", "M or F"),
        "village": ("Village", "Village or area"),
    },
    "immunisation": {
        "child_name": ("Child name", "Child's name, often 'Baby of <mother>'"),
        "dob": ("DOB", "Child's date of birth, DD-MM-YYYY"),
        "mother_mobile": ("Mother mobile", "Mother's mobile number"),
        "birth": ("Birth", "Date birth doses given, DD-MM-YYYY, empty if blank"),
        "w6": ("6 wk", "Date 6-week vaccines given, empty if blank"),
        "w10": ("10 wk", "Date 10-week vaccines given, empty if blank"),
        "w14": ("14 wk", "Date 14-week vaccines given, empty if blank"),
        "m9": ("9 mo", "Date 9-month vaccines given, empty if blank"),
        "m16": ("16 mo", "Date 16-24 month vaccines given, empty if blank"),
    },
}


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

    def extract_register(self, page: bytes, filename: str, register: str, language: str = "ta-IN",
                         timeout_s: int = 120) -> list[dict] | None:
        """Sarvam Vision (Document AI Extract): a photographed register page -> rows keyed by importer
        column names. Rows are a draft: a nurse verifies them before anything is saved."""
        if not self.enabled:
            return None
        fields = REGISTER_FIELDS[register]
        schema = {
            "type": "object",
            "properties": {
                "rows": {
                    "type": "array",
                    "description": "One entry per filled row of the register table, top to bottom",
                    "items": {
                        "type": "object",
                        "properties": {k: {"type": "string", "description": d} for k, (_, d) in fields.items()},
                    },
                }
            },
        }
        r = httpx.post(f"{self.base_url}/doc-ai/v1/job/extract", headers=self._headers(),
                       files={"file": (filename, page)},
                       data={"schema": json.dumps(schema), "language": language, "output_format": "json"},
                       timeout=60)
        r.raise_for_status()
        job_id = r.json()["job_id"]
        deadline = time.monotonic() + timeout_s
        while True:
            st = httpx.get(f"{self.base_url}/doc-ai/v1/job/{job_id}/status", headers=self._headers(), timeout=30)
            st.raise_for_status()
            status = st.json()["status"].lower()
            if status in ("completed", "partially_completed"):
                break
            if status in ("failed", "rejected") or time.monotonic() > deadline:
                raise RuntimeError(f"Sarvam Vision job {job_id} ended as {status}")
            time.sleep(3)
        res = httpx.get(f"{self.base_url}/doc-ai/v1/job/{job_id}/results", headers=self._headers(), timeout=30)
        res.raise_for_status()
        result = res.json().get("result") or {}
        rows = result.get("rows", []) if isinstance(result, dict) else []
        return [{col: (row.get(k) or None) for k, (col, _) in fields.items()} for row in rows]

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
