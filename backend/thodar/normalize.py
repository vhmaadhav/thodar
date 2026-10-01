"""Cleaning helpers for identifiers as they appear in real registers."""

import re

_INITIALS = re.compile(r"\b[a-z]\b\.?")
_NON_ALPHA = re.compile(r"[^a-z ]+")
_BABY_OF = re.compile(r"^\s*(baby|b/o|bo)\s*(of)?\s*", re.IGNORECASE)


def phone(value: object) -> str | None:
    """Last 10 digits of an Indian mobile number, or None."""
    if value is None:
        return None
    text = str(value).strip()
    if text.endswith(".0"):  # pandas reads numeric phone columns as floats
        text = text[:-2]
    digits = re.sub(r"\D", "", text)
    if len(digits) < 10:
        return None
    digits = digits[-10:]
    return digits if digits[0] in "6789" else None


def name(value: object) -> str:
    """Lower-case name without initials, punctuation or 'Baby of' prefix. 'R. Kavitha' -> 'kavitha'."""
    if value is None:
        return ""
    text = _BABY_OF.sub("", str(value)).lower()
    text = _NON_ALPHA.sub(" ", text)
    text = _INITIALS.sub(" ", text)
    return " ".join(text.split())


def rch_id(value: object) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits if len(digits) == 12 else None


def abha(value: object) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits if len(digits) == 14 else None
