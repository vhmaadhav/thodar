"""A daily cap on paid AI calls from user-facing endpoints, so a public demo cannot drain credit."""

import threading
from datetime import date

from fastapi import HTTPException

from thodar.config import get_settings

_lock = threading.Lock()
_day: date | None = None
_used = 0


def spend(what: str) -> None:
    global _day, _used
    with _lock:
        today = date.today()
        if _day != today:
            _day, _used = today, 0
        if _used >= get_settings().ai_daily_budget:
            raise HTTPException(429, f"Daily AI budget reached ({what}). Try again tomorrow.")
        _used += 1


def reset() -> None:
    global _day, _used
    with _lock:
        _day, _used = None, 0
