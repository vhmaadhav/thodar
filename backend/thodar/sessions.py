"""Clinic session days. Tamil Nadu PHCs run ANC clinics and routine immunisation on a fixed day
(Wednesday; NHM Tamil Nadu), so reminders propose that day instead of an arbitrary due date, and a
family with several things due is asked to come once for all of them."""

from datetime import date, timedelta

WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def parse_weekdays(spec: str) -> list[int]:
    days = [WEEKDAYS[d.strip().lower()[:3]] for d in spec.split(",") if d.strip()]
    return sorted(set(days)) or [2]


def next_session(on_or_after: date, weekdays: list[int]) -> date:
    for k in range(7):
        d = on_or_after + timedelta(days=k)
        if d.weekday() in weekdays:
            return d
    return on_or_after
