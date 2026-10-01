"""Sends the day's reminders automatically at a set time (THODAR_AUTO_REMINDERS_AT, e.g. "09:00", IST).

Safe to run more than once a day: an item that has been reminded moves to "Voice call" as its next
step, so a second run does not message the same family again. Also expires missed visits nightly.
"""

import asyncio
import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from thodar.config import get_settings
from thodar.db import SessionLocal
from thodar.messaging.service import run_reminders
from thodar.messaging.whatsapp import WhatsAppClient

log = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def parse_hhmm(value: str) -> time | None:
    try:
        h, m = value.strip().split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        return None


def seconds_until(at: time, now: datetime) -> float:
    target = now.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def run_once(wa: WhatsAppClient, today: date) -> dict:
    with SessionLocal() as session:
        run = run_reminders(session, today, wa, clinic=get_settings().clinic_name)
    log.info("auto reminders %s: %s sent", today, run.sent)
    return run.__dict__


async def daily_loop(wa: WhatsAppClient) -> None:
    at = parse_hhmm(get_settings().auto_reminders_at)
    if at is None:
        return
    log.info("auto reminders scheduled daily at %s IST", at.strftime("%H:%M"))
    while True:
        await asyncio.sleep(seconds_until(at, datetime.now(IST)))
        try:
            await asyncio.to_thread(run_once, wa, datetime.now(IST).date())
        except Exception:  # noqa: BLE001 - a bad day must not stop tomorrow's run
            log.exception("auto reminders failed")
