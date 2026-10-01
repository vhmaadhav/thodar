"""Understands a family's reply well enough to update the schedule, and nothing more.

Rules first, in Tamil, English and Tanglish. Anything that mentions health, or that the rules
can't place, goes to a person (needs_staff). An optional Sarvam-105B call may only choose
between the same non-clinical labels, and can never override a health flag.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum


class Kind(StrEnum):
    confirm = "confirm"
    reschedule = "reschedule"
    moved = "moved"
    wrong_number = "wrong_number"
    stop = "stop"
    needs_staff = "needs_staff"


@dataclass(frozen=True)
class Intent:
    kind: Kind
    on: date | None = None
    reason: str = ""


# Checked first. A family describing symptoms must reach a person, never an automated reply.
HEALTH_WORDS = [
    "pain", "fever", "bleed", "blood", "vomit", "sick", "cough", "rash", "fits", "seizure", "swelling",
    "not feeding", "not drinking", "medicine", "tablet", "emergency", "unwell", "breath",
    "வலி", "காய்ச்சல்", "ரத்த", "இரத்த", "வாந்தி", "மருந்து", "மாத்திரை", "உடம்பு சரியில்ல",
    "இருமல்", "வீக்கம்", "வலிப்பு", "பால் குடிக்க", "மூச்சு",
    # Tanglish, as families actually type it
    "vali", "kaaichal", "kaichal", "kaichel", "jaram", "juram", "udambu", "sari illa", "sariyilla",
    "seriyilla", "vomiting", "loose motion", "motion", "blood", "bleeding", "maruthu", "mathirai",
]
STOP_WORDS = ["stop", "unsubscribe", "நிறுத்து", "niruthu"]
WRONG_NUMBER = ["wrong number", "rong number", "தவறான எண்", "தப்பான நம்பர்", "thappana number"]
MOVED = ["moved", "shifted", "went to native", "ஊருக்கு போய்", "வேறு ஊர்", "ஊர் மாறி", "oorukku poi"]
CANT = ["can't", "cant", "cannot", "not today", "not able", "later", "busy", "change date",
        "முடியாது", "முடியல", "அப்புறம்", "தேதி மாற்று", "mudiyathu", "mudiyala", "appuram"]
YES = ["yes", "ok", "okay", "sure", "coming", "will come", "i'll come", "confirm",
       "சரி", "ஆமா", "ஆம்", "வருகிறேன்", "வரேன்", "வருவேன்", "வந்துடுவேன்", "sari", "varen", "varuven", "aama"]

WEEKDAYS = {
    0: ["monday", "திங்கள்", "thingal"],
    1: ["tuesday", "செவ்வாய்", "sevvai"],
    2: ["wednesday", "புதன்", "budhan", "puthan"],
    3: ["thursday", "வியாழன்", "viyazhan", "viyalan"],
    4: ["friday", "வெள்ளி", "velli"],
    5: ["saturday", "சனி", "sani"],
    6: ["sunday", "ஞாயிறு", "gnayiru", "nyayiru"],
}
DATE_RE = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?\b")


def _has(text: str, words: list[str]) -> str | None:
    """First word found. Latin words must start at a word boundary ('ok' must not match 'book')."""
    for w in words:
        if w.isascii():
            if re.search(r"(?<![a-z])" + re.escape(w), text):
                return w
        elif w in text:
            return w
    return None


def find_date(text: str, today: date) -> date | None:
    """A future date mentioned in the reply: 'saturday', 'நாளை', '12/10', 'day after tomorrow'."""
    if _has(text, ["day after tomorrow", "நாளை மறுநாள்", "naalai marunaal"]):
        return today + timedelta(days=2)
    if _has(text, ["tomorrow", "நாளை", "naalai", "nalaikku", "நாளைக்கு"]):
        return today + timedelta(days=1)
    if _has(text, ["next week", "அடுத்த வாரம்", "adutha vaaram"]):
        return today + timedelta(days=7)
    for weekday, words in WEEKDAYS.items():
        if _has(text, words):
            ahead = (weekday - today.weekday()) % 7 or 7
            return today + timedelta(days=ahead)
    m = DATE_RE.search(text)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else today.year
        year = year + 2000 if year < 100 else year
        try:
            d = date(year, month, day)
        except ValueError:
            return None
        if d < today and not m.group(3):
            d = date(year + 1, month, day)
        return d if d >= today else None
    return None


def classify(text: str, today: date) -> Intent:
    t = " ".join(text.lower().split())
    if not t:
        return Intent(Kind.needs_staff, reason="empty reply")
    if w := _has(t, HEALTH_WORDS):
        return Intent(Kind.needs_staff, reason=f"mentions '{w}'")
    if w := _has(t, STOP_WORDS):
        return Intent(Kind.stop, reason=f"'{w}'")
    if w := _has(t, WRONG_NUMBER):
        return Intent(Kind.wrong_number, reason=f"'{w}'")
    if w := _has(t, MOVED):
        return Intent(Kind.moved, reason=f"'{w}'")

    on = find_date(t, today)
    if on and on != today:
        return Intent(Kind.reschedule, on=on, reason="names another day")
    if w := _has(t, CANT):
        return Intent(Kind.reschedule, reason=f"'{w}'")
    if w := _has(t, YES):
        return Intent(Kind.confirm, reason=f"'{w}'")
    return Intent(Kind.needs_staff, reason="not understood by rules")


def from_button(payload: str) -> tuple[Kind, list[int], date | None] | None:
    """Quick-reply ids: 'confirm:2026-10-08:41,42' (come on that session day for items 41 and 42),
    'reschedule:41,42', or the older single-item 'confirm:42'."""
    parts = payload.split(":")
    if len(parts) < 2 or parts[0] not in (Kind.confirm, Kind.reschedule):
        return None
    day = None
    if len(parts) == 3:
        try:
            day = date.fromisoformat(parts[1])
        except ValueError:
            return None
    ids = parts[-1].split(",")
    if not ids or not all(i.isdigit() for i in ids):
        return None
    return Kind(parts[0]), [int(i) for i in ids], day
