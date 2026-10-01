"""The morning worklist and the actions a nurse can take on it.

Ordering uses only scheduling facts: days overdue, then failed contact attempts, then the nearest
due date. There is no clinical risk score anywhere in this module, by design.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from thodar.models import (
    Baby,
    Channel,
    ContactAttempt,
    ItemStatus,
    Mother,
    Outcome,
    ScheduleItem,
)

UNREACHABLE_AFTER = 2  # consecutive failed attempts
FAILED = {Outcome.no_answer, Outcome.wrong_number}


class Bucket(StrEnum):
    unreachable = "unreachable"
    overdue = "overdue"
    due_today = "due_today"
    due_soon = "due_soon"


@dataclass
class Row:
    item: ScheduleItem
    mother: Mother
    baby: Baby | None
    bucket: Bucket
    effective_due: date
    days_overdue: int
    failed_attempts: int
    last_attempt: ContactAttempt | None
    next_step: str

    @property
    def who(self) -> str:
        return self.baby.name if self.baby and self.baby.name else (
            f"Baby of {self.mother.name}" if self.baby else self.mother.name)


def effective_due(item: ScheduleItem) -> date:
    return item.rescheduled_to or item.due_date


def _failed_streak(attempts: list[ContactAttempt]) -> int:
    n = 0
    for a in sorted(attempts, key=lambda a: (a.at, a.id), reverse=True):
        if a.outcome not in FAILED:
            break
        n += 1
    return n


def suggest_next_step(item: ScheduleItem, failed: int, last: ContactAttempt | None, today: date) -> str:
    """Plain scheduling suggestion. Never clinical."""
    # A family's question or a bad number outranks any booking: a person must act first.
    if last and last.outcome is Outcome.needs_staff:
        return "Family asked a question: staff to call"
    if last and last.outcome is Outcome.wrong_number:
        return "Find correct number"
    if last and last.outcome is Outcome.moved:
        return "Moved away: update address or transfer"
    if item.status is ItemStatus.confirmed:
        return "Expect at OPD" if effective_due(item) <= today else f"Confirmed for {effective_due(item):%a %d %b}"
    if item.rescheduled_to and item.rescheduled_to >= today:
        return f"Booked {item.rescheduled_to:%a %d %b}"
    if last and last.outcome is Outcome.reschedule:
        return "Call to book a new date"
    if last and last.channel is Channel.visit:
        return f"VHN visit requested {last.at:%d %b}"
    if failed >= UNREACHABLE_AFTER:
        return "Ask VHN to visit"
    if failed == 1 or (last and last.channel is Channel.whatsapp and last.outcome is Outcome.sent):
        return "Voice call"
    return "Send WhatsApp reminder"


def _superseded(item: ScheduleItem, siblings: list[ScheduleItem]) -> bool:
    """A missed visit stops being actionable once a later one in the same schedule is done."""
    return any(
        s.schedule == item.schedule and s.baby_id == item.baby_id and s.status is ItemStatus.done
        and s.due_date > item.due_date
        for s in siblings
    )


def build_worklist(session: Session, today: date, owner: str | None = None,
                   horizon_days: int = 7, grace_days: int = 0) -> list[Row]:
    stmt = (
        select(ScheduleItem)
        .where(ScheduleItem.status.in_([ItemStatus.pending, ItemStatus.confirmed]))
        .options(selectinload(ScheduleItem.attempts))
    )
    if owner:
        stmt = stmt.where(ScheduleItem.owner == owner)
    open_items = list(session.scalars(stmt))
    if not open_items:
        return []

    pregnancy_ids = {i.pregnancy_id for i in open_items}
    siblings: dict[int, list[ScheduleItem]] = {}
    for s in session.scalars(select(ScheduleItem).where(ScheduleItem.pregnancy_id.in_(pregnancy_ids))):
        siblings.setdefault(s.pregnancy_id, []).append(s)

    rows: list[Row] = []
    for item in open_items:
        due = effective_due(item)
        if due > today + timedelta(days=horizon_days):
            continue
        if _superseded(item, siblings[item.pregnancy_id]):
            continue
        failed = _failed_streak(item.attempts)
        last = max(item.attempts, key=lambda a: (a.at, a.id), default=None)
        overdue = (today - due).days - grace_days

        if failed >= UNREACHABLE_AFTER:
            bucket = Bucket.unreachable
        elif overdue > 0:
            bucket = Bucket.overdue
        elif due == today:
            bucket = Bucket.due_today
        else:
            bucket = Bucket.due_soon

        mother = session.get(Mother, item.mother_id)
        baby = session.get(Baby, item.baby_id) if item.baby_id else None
        rows.append(Row(item, mother, baby, bucket, due, max(overdue, 0), failed, last,
                        suggest_next_step(item, failed, last, today)))

    # A family waiting for a person to call back comes first. This is a communication state
    # (they sent a message only staff may answer), not a judgement about their health.
    rows.sort(key=lambda r: (
        0 if r.last_attempt and r.last_attempt.outcome is Outcome.needs_staff else 1,
        -r.days_overdue, -r.failed_attempts, r.effective_due, r.item.id,
    ))
    return rows


class Action(StrEnum):
    confirm = "confirm"
    reschedule = "reschedule"
    done = "done"
    no_answer = "no_answer"
    wrong_number = "wrong_number"
    moved = "moved"
    request_visit = "request_visit"
    notify_doctor = "notify_doctor"
    reminder_sent = "reminder_sent"


def record_action(session: Session, item: ScheduleItem, action: Action, *, on: date | None = None,
                  note: str | None = None, actor: str = "staff",
                  channel: Channel = Channel.phone) -> ContactAttempt:
    """Applies a nurse's (or a family's) action to an item and logs it. Every change is an attempt row."""
    outcome = {
        Action.confirm: Outcome.confirmed,
        Action.reschedule: Outcome.reschedule,
        Action.done: Outcome.confirmed,
        Action.no_answer: Outcome.no_answer,
        Action.wrong_number: Outcome.wrong_number,
        Action.moved: Outcome.moved,
        Action.request_visit: Outcome.sent,
        Action.notify_doctor: Outcome.needs_staff,
        Action.reminder_sent: Outcome.sent,
    }[action]

    if action is Action.confirm:
        item.status = ItemStatus.confirmed
    elif action is Action.reschedule:
        if on is None:
            raise ValueError("reschedule needs a date")
        item.rescheduled_to = on
        item.status = ItemStatus.pending
    elif action is Action.done:
        item.status = ItemStatus.done
        item.completed_on = on or date.today()
    elif action is Action.request_visit:
        channel = Channel.visit

    attempt = ContactAttempt(item=item, channel=channel, outcome=outcome, note=note, actor=actor)
    session.add(attempt)
    return attempt
