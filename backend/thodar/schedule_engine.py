"""Turns YAML schedules into dated ScheduleItems.

Deterministic on purpose: the same inputs always give the same due dates, and every rule lives
in a versioned YAML file a clinician can read. No model decides anything here.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from thodar.models import Baby, ItemStatus, Pregnancy, ScheduleItem, Subject

SCHEDULE_DIR = Path(__file__).parent / "schedules"


@dataclass(frozen=True)
class Rule:
    schedule: str
    code: str
    label: str
    subject: Subject
    owner: str
    due_offset_days: int
    window_end_days: int
    expires_after_days: int = 0
    includes: tuple[str, ...] = ()


@lru_cache
def load_rules(name: str) -> tuple[Rule, ...]:
    doc = yaml.safe_load((SCHEDULE_DIR / f"{name}.yaml").read_text(encoding="utf-8"))
    rules = []
    for item in doc["items"]:
        rules.append(
            Rule(
                schedule=doc["name"],
                code=item["code"],
                label=item["label"],
                subject=Subject(item.get("subject", doc.get("subject"))),
                owner=item.get("owner", doc.get("owner")),
                due_offset_days=item["due_offset_days"],
                window_end_days=item["window_end_days"],
                expires_after_days=item.get("expires_after_days", doc.get("expires_after_days", 0)),
                includes=tuple(item.get("includes", ())),
            )
        )
    return tuple(rules)


def doses_for(code: str) -> tuple[str, ...]:
    """The vaccines given at a UIP visit, e.g. ('OPV-2', 'Penta-2', 'RVV-2'); empty for other visits."""
    return next((r.includes for r in load_rules("uip") if r.code == code), ())


def _anc_rules(pregnancy: Pregnancy) -> list[Rule]:
    """ANC rules, re-spaced to the doctor's interval when the doctor has set one."""
    rules = list(load_rules("anc"))
    step = pregnancy.doctor_anc_interval_days
    if not step:
        return rules
    first = rules[0]
    respaced = []
    offset = first.due_offset_days
    n = 1
    while offset <= rules[-1].window_end_days:
        respaced.append(
            Rule("anc", f"anc-{n}", f"ANC visit {n} (doctor-set interval)", Subject.mother,
                 first.owner, offset, offset + min(step, 14), first.expires_after_days)
        )
        offset += step
        n += 1
    return respaced


def _existing_codes(session: Session, pregnancy_id: int, baby_id: int | None) -> set[str]:
    stmt = select(ScheduleItem.code).where(ScheduleItem.pregnancy_id == pregnancy_id)
    stmt = stmt.where(ScheduleItem.baby_id == baby_id) if baby_id else stmt.where(ScheduleItem.baby_id.is_(None))
    return set(session.scalars(stmt))


def _make(rule: Rule, anchor: date, pregnancy: Pregnancy, baby: Baby | None) -> ScheduleItem:
    return ScheduleItem(
        subject=rule.subject,
        mother_id=pregnancy.mother_id,
        baby_id=baby.id if baby else None,
        pregnancy_id=pregnancy.id,
        schedule=rule.schedule,
        code=rule.code,
        label=rule.label,
        due_date=anchor + timedelta(days=rule.due_offset_days),
        window_end=anchor + timedelta(days=rule.window_end_days),
        actionable_until=anchor + timedelta(days=rule.window_end_days + rule.expires_after_days),
        owner=rule.owner,
        status=ItemStatus.pending,
    )


def generate_for_pregnancy(session: Session, pregnancy: Pregnancy) -> list[ScheduleItem]:
    """Creates any missing items for a pregnancy. Safe to call repeatedly (idempotent)."""
    created: list[ScheduleItem] = []

    if pregnancy.lmp:
        have = _existing_codes(session, pregnancy.id, None)
        for rule in _anc_rules(pregnancy):
            anc_due = pregnancy.lmp + timedelta(days=rule.due_offset_days)
            # Once delivered, ANC visits that fall after the birth no longer apply.
            if pregnancy.delivery_date and anc_due > pregnancy.delivery_date:
                continue
            if rule.code not in have:
                created.append(_make(rule, pregnancy.lmp, pregnancy, None))

    if pregnancy.delivery_date:
        have_mother = _existing_codes(session, pregnancy.id, None)
        for rule in load_rules("pnc"):
            if rule.subject is Subject.mother and rule.code not in have_mother:
                created.append(_make(rule, pregnancy.delivery_date, pregnancy, None))
        for baby in pregnancy.babies:
            created.extend(generate_for_baby(session, pregnancy, baby))

    session.add_all(created)
    return created


def generate_for_baby(session: Session, pregnancy: Pregnancy, baby: Baby) -> list[ScheduleItem]:
    """The delivery handover: newborn checks and UIP visits start the day the baby is born."""
    have = _existing_codes(session, pregnancy.id, baby.id) if baby.id else set()
    rules = [r for r in load_rules("pnc") if r.subject is Subject.baby] + list(load_rules("uip"))
    return [_make(r, baby.dob, pregnancy, baby) for r in rules if r.code not in have]


def cancel_remaining_anc(session: Session, pregnancy: Pregnancy) -> int:
    """At delivery, open ANC items close: ones dated after the birth no longer apply (cancelled);
    earlier ones that never happened are recorded as missed."""
    n = 0
    stmt = select(ScheduleItem).where(
        ScheduleItem.pregnancy_id == pregnancy.id,
        ScheduleItem.schedule == "anc",
        ScheduleItem.status.in_([ItemStatus.pending, ItemStatus.confirmed]),
    )
    for item in session.scalars(stmt):
        if not pregnancy.delivery_date:
            continue
        item.status = ItemStatus.cancelled if item.due_date > pregnancy.delivery_date else ItemStatus.missed
        n += 1
    return n


def expire_items(session: Session, today: date) -> int:
    """Marks open items whose catch-up period has passed as missed. Run daily (and before the worklist)."""
    stmt = select(ScheduleItem).where(
        ScheduleItem.status.in_([ItemStatus.pending, ItemStatus.confirmed]),
        ScheduleItem.actionable_until < today,
    )
    n = 0
    for item in session.scalars(stmt):
        if item.rescheduled_to and item.rescheduled_to >= today:
            continue  # a booked catch-up date keeps it alive
        item.status = ItemStatus.missed
        n += 1
    return n
