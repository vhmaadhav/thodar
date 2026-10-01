"""Sends reminders and turns families' replies into worklist updates."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from thodar.ai.stt import STT, OffshoreNotAllowed, get_stt
from thodar.messaging import templates
from thodar.messaging.intents import Intent, Kind, classify, from_button
from thodar.messaging.sarvam import SarvamClient
from thodar.messaging.whatsapp import Incoming, WhatsAppClient
from thodar.models import (
    Baby,
    Channel,
    ContactAttempt,
    ItemStatus,
    Mother,
    Outcome,
    ScheduleItem,
)
from thodar.benefits import benefit_for
from thodar.config import get_settings
from thodar.schedule_engine import doses_for, expire_items
from thodar.sessions import next_session, parse_weekdays
from thodar.worklist import Action, build_worklist, effective_due, record_action

CLINIC_NAME = "the clinic"


@dataclass
class ReminderRun:
    sent: int = 0
    skipped_no_consent: int = 0
    skipped_opted_out: int = 0
    skipped_no_phone: int = 0
    item_ids: list[int] = field(default_factory=list)


def run_reminders(session: Session, today: date, wa: WhatsAppClient, clinic: str = CLINIC_NAME,
                  horizon_days: int = 7) -> ReminderRun:
    """One WhatsApp message per family per run, bundling everything the mother and baby have due
    (overdue, or due within `horizon_days`) into a single trip on the clinic's next session day."""
    run = ReminderRun()
    expire_items(session, today)
    weekdays = parse_weekdays(get_settings().session_days)
    families: dict[int, list] = {}
    for row in build_worklist(session, today, horizon_days=horizon_days):
        if row.next_step == "Send WhatsApp reminder":
            families.setdefault(row.mother.id, []).append(row)
    for family_rows in families.values():
        # One trip can only hold the NEXT visit of each sequence (the mother's ANC/PNC, the baby's checks,
        # the baby's vaccines). Later doses need spacing after earlier ones, and planning a catch-up
        # schedule is the doctor's call, so the rest wait and the message says so.
        rows, held_back = [], False
        seen: set[tuple] = set()
        for r in sorted(family_rows, key=lambda r: r.item.due_date):
            key = (r.item.schedule, r.item.baby_id, r.item.code.split("-")[0])
            if key in seen:
                held_back = True
                continue
            seen.add(key)
            rows.append(r)
        m = rows[0].mother
        if not m.phone:
            run.skipped_no_phone += 1
            continue
        if m.opted_out:
            run.skipped_opted_out += 1
            continue
        if not m.consent_at:
            run.skipped_no_consent += 1
            continue
        target = max(today + timedelta(days=1), min(r.effective_due for r in rows))
        day = next_session(target, weekdays)
        lines = [templates.visit_line(r.item, m.language, doses_for(r.item.code)) for r in rows]
        benefits = [getattr(b, m.language.value) for r in rows if (b := benefit_for(r.item.code))]
        body = templates.bundle_reminder(lines, benefits, m.name.split()[0], day, clinic, m.language,
                                         more_to_plan=held_back)
        ids = ",".join(str(r.item.id) for r in rows)
        yes, change = templates.BUTTONS[m.language]
        buttons = [(f"confirm:{day.isoformat()}:{ids}", yes), (f"reschedule:{ids}", change)]
        for phone in filter(None, [m.phone, m.family_phone]):
            wa.send_buttons(phone, body, buttons)
        for r in rows:
            record_action(session, r.item, Action.reminder_sent, actor="thodar", channel=Channel.whatsapp,
                          note=f"proposed {day.isoformat()}")
            run.item_ids.append(r.item.id)
        run.sent += 1
    session.commit()
    return run


def _latest_reminded(session: Session, mother: Mother) -> tuple[list[ScheduleItem], date | None]:
    """What a free-text reply refers to: every open item in the family's most recent reminder (one
    bundle), plus the session day that reminder proposed."""
    stmt = (
        select(ContactAttempt)
        .join(ScheduleItem)
        .where(ScheduleItem.mother_id == mother.id,
               ScheduleItem.status.in_([ItemStatus.pending, ItemStatus.confirmed]),
               ContactAttempt.outcome == Outcome.sent,
               ContactAttempt.channel.in_([Channel.whatsapp, Channel.voice]))
        .order_by(ContactAttempt.at.desc(), ContactAttempt.id.desc())
    )
    attempts = list(session.scalars(stmt))
    if not attempts:
        return [], None
    latest = attempts[0]
    # Items reminded in the same run share the note and were logged within a minute of each other.
    same = [a for a in attempts
            if a.note == latest.note and abs((latest.at - a.at).total_seconds()) < 60]
    items = list({a.item_id: a.item for a in same}.values())
    proposed = None
    if latest.note and latest.note.startswith("proposed "):
        try:
            proposed = date.fromisoformat(latest.note.removeprefix("proposed "))
        except ValueError:
            proposed = None
    return items, proposed


def second_lock(rules: Intent, model: tuple[Kind, str | None] | None) -> Intent:
    """Two locks on safety: rules AND the model read every free-text reply. If either sees something a
    person must handle, a person handles it. The model can escalate, or fill in a reply the rules could
    not place, but it can never overrule a rule that already sent the message to staff."""
    if model is None:
        return rules
    kind, on = model
    if kind is Kind.needs_staff:
        if rules.kind is Kind.needs_staff:
            return rules
        return Intent(Kind.needs_staff, reason=f"model flagged it (rules said {rules.kind})")
    if rules.kind is Kind.needs_staff and rules.reason == "not understood by rules":
        return Intent(kind, date.fromisoformat(on) if on else None, reason="sarvam-105b")
    return rules


@dataclass
class Handled:
    item_id: int | None
    intent: Intent
    reply: str | None
    transcript: str | None = None


def handle_incoming(session: Session, msg: Incoming, today: date, wa: WhatsAppClient,
                    sarvam: SarvamClient | None = None, stt: "STT | None" = None,
                    audio: bytes | None = None) -> Handled:
    """`audio` lets a caller pass voice-note bytes directly (demo upload) instead of a WhatsApp media id."""
    sarvam = sarvam or SarvamClient()
    mother = session.scalars(select(Mother).where(
        (Mother.phone == msg.phone) | (Mother.family_phone == msg.phone))).first()
    if mother is None:
        return Handled(None, Intent(Kind.needs_staff, reason="unknown number"), None)
    lang = mother.language

    item: ScheduleItem | None = None
    bundle: list[ScheduleItem] = []
    transcript = None
    if msg.kind == "button" and msg.button_id and (parsed := from_button(msg.button_id)):
        kind, item_ids, session_day = parsed
        # Ignore ids that are not this family's (a forwarded or tampered button).
        bundle = [i for i in (session.get(ScheduleItem, x) for x in item_ids) if i and i.mother_id == mother.id]
        item = bundle[0] if bundle else None
        intent = Intent(kind, on=session_day, reason="button")
    else:
        text = msg.text
        if msg.kind == "audio":
            audio = audio or (wa.download_media(msg.media_id) if msg.media_id else None)
            if audio:
                try:
                    transcript = (stt or get_stt()).transcribe(audio, "voice.ogg", mother.language.value)
                except OffshoreNotAllowed:
                    transcript = None  # misconfigured provider: a person listens instead
            text = transcript
        intent = classify(text or "", today)
        if text and not (intent.kind is Kind.needs_staff and intent.reason.startswith("mentions")):
            intent = second_lock(intent, sarvam.classify(text, today.isoformat()))
        bundle, proposed = _latest_reminded(session, mother)
        item = bundle[0] if bundle else None
        if intent.kind is Kind.confirm and intent.on is None:
            intent = Intent(Kind.confirm, on=proposed, reason=intent.reason)

    note = transcript or msg.text
    reply: str | None
    from_family_contact = bool(mother.family_phone) and msg.phone == mother.family_phone and msg.phone != mother.phone
    if from_family_contact and intent.kind in (Kind.stop, Kind.wrong_number):
        # A family contact can take themselves off reminders; they cannot opt the mother out
        # or mark her number wrong.
        mother.family_phone = None
        mother.family_relation = None
        session.commit()
        reply = templates.ack_stop(lang) if intent.kind is Kind.stop else None
        if reply:
            wa.send_text(msg.phone, reply)
        return Handled(None, intent, reply, transcript)
    if intent.kind is Kind.stop:
        mother.opted_out = True
        reply = templates.ack_stop(lang)
    elif item is None:
        reply = templates.ack_staff(lang)
    elif intent.kind is Kind.confirm:
        for it in bundle or [item]:
            if intent.on and effective_due(it) != intent.on:
                it.rescheduled_to = intent.on  # they agreed to come on the proposed session day
            record_action(session, it, Action.confirm, note=note, actor="family", channel=Channel.whatsapp)
        reply = templates.ack_confirm(intent.on or max(effective_due(item), today), lang)
    elif intent.kind is Kind.reschedule and intent.on and msg.kind != "button":
        for it in bundle or [item]:
            record_action(session, it, Action.reschedule, on=intent.on, note=note, actor="family",
                          channel=Channel.whatsapp)
        reply = templates.ack_reschedule(intent.on, lang)
    elif intent.kind is Kind.reschedule:
        for it in bundle or [item]:
            session.add(ContactAttempt(item=it, channel=Channel.whatsapp, outcome=Outcome.reschedule,
                                       note=note or "asked to change the date", actor="family", at=datetime.now()))
        reply = templates.ack_reschedule(None, lang)
    elif intent.kind is Kind.moved:
        record_action(session, item, Action.moved, note=note, actor="family", channel=Channel.whatsapp)
        reply = templates.ack_staff(lang)
    elif intent.kind is Kind.wrong_number:
        record_action(session, item, Action.wrong_number, note=note, actor="family", channel=Channel.whatsapp)
        reply = None
    else:
        session.add(ContactAttempt(item=item, channel=Channel.whatsapp, outcome=Outcome.needs_staff,
                                   note=note, actor="family", at=datetime.now()))
        reply = templates.ack_staff(lang)

    session.commit()
    if reply:
        wa.send_text(msg.phone, reply)  # answer whoever wrote: the mother or the family contact
    return Handled(item.id if item else None, intent, reply, transcript)


def baby_or_mother_name(session: Session, item: ScheduleItem) -> str:
    if item.baby_id:
        baby = session.get(Baby, item.baby_id)
        return baby.name or "Baby"
    return session.get(Mother, item.mother_id).name
