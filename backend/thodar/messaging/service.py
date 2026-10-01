"""Sends reminders and turns families' replies into worklist updates."""

from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

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
from thodar.schedule_engine import expire_items
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
                  horizon_days: int = 1) -> ReminderRun:
    """At most one WhatsApp reminder per family per run, for its most overdue item awaiting one."""
    run = ReminderRun()
    expire_items(session, today)
    seen: set[int] = set()
    for row in build_worklist(session, today, horizon_days=horizon_days):
        if row.next_step != "Send WhatsApp reminder" or row.mother.id in seen:
            continue
        seen.add(row.mother.id)
        m = row.mother
        if not m.phone:
            run.skipped_no_phone += 1
            continue
        if m.opted_out:
            run.skipped_opted_out += 1
            continue
        if not m.consent_at:
            run.skipped_no_consent += 1
            continue
        name = m.name.split()[0]
        body = templates.reminder(row.item, name, max(row.effective_due, today), clinic, m.language)
        yes, change = templates.BUTTONS[m.language]
        wa.send_buttons(m.phone, body, [(f"confirm:{row.item.id}", yes), (f"reschedule:{row.item.id}", change)])
        record_action(session, row.item, Action.reminder_sent, actor="thodar", channel=Channel.whatsapp)
        run.sent += 1
        run.item_ids.append(row.item.id)
    session.commit()
    return run


def _latest_reminded_item(session: Session, mother: Mother) -> ScheduleItem | None:
    """The open item we most recently reminded this family about: what a free-text reply refers to."""
    stmt = (
        select(ScheduleItem)
        .join(ContactAttempt)
        .where(ScheduleItem.mother_id == mother.id,
               ScheduleItem.status.in_([ItemStatus.pending, ItemStatus.confirmed]),
               ContactAttempt.outcome == Outcome.sent,
               ContactAttempt.channel.in_([Channel.whatsapp, Channel.voice]))
        .order_by(ContactAttempt.at.desc(), ContactAttempt.id.desc())
    )
    return session.scalars(stmt).first()


@dataclass
class Handled:
    item_id: int | None
    intent: Intent
    reply: str | None
    transcript: str | None = None


def handle_incoming(session: Session, msg: Incoming, today: date, wa: WhatsAppClient,
                    sarvam: SarvamClient | None = None) -> Handled:
    sarvam = sarvam or SarvamClient()
    mother = session.scalars(select(Mother).where(Mother.phone == msg.phone)).first()
    if mother is None:
        return Handled(None, Intent(Kind.needs_staff, reason="unknown number"), None)
    lang = mother.language

    item: ScheduleItem | None = None
    transcript = None
    if msg.kind == "button" and msg.button_id and (parsed := from_button(msg.button_id)):
        kind, item_id = parsed
        item = session.get(ScheduleItem, item_id)
        if item is not None and item.mother_id != mother.id:
            item = None  # a button from someone else's message: ignore the id
        intent = Intent(kind, reason="button")
    else:
        text = msg.text
        if msg.kind == "audio" and msg.media_id:
            audio = wa.download_media(msg.media_id)
            transcript = sarvam.transcribe(audio) if audio else None
            text = transcript
        intent = classify(text or "", today)
        if intent.kind is Kind.needs_staff and text and intent.reason == "not understood by rules":
            # Only for replies the rules couldn't place; a health mention never reaches the model.
            if guess := sarvam.classify(text, today.isoformat()):
                kind, on = guess
                intent = Intent(kind, date.fromisoformat(on) if on else None, reason="sarvam-105b")
        item = _latest_reminded_item(session, mother)

    note = transcript or msg.text
    reply: str | None
    if intent.kind is Kind.stop:
        mother.opted_out = True
        reply = templates.ack_stop(lang)
    elif item is None:
        reply = templates.ack_staff(lang)
    elif intent.kind is Kind.confirm:
        record_action(session, item, Action.confirm, note=note, actor="family", channel=Channel.whatsapp)
        reply = templates.ack_confirm(max(effective_due(item), today), lang)
    elif intent.kind is Kind.reschedule and intent.on:
        record_action(session, item, Action.reschedule, on=intent.on, note=note, actor="family",
                      channel=Channel.whatsapp)
        reply = templates.ack_reschedule(intent.on, lang)
    elif intent.kind is Kind.reschedule:
        session.add(ContactAttempt(item=item, channel=Channel.whatsapp, outcome=Outcome.reschedule,
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
    if reply and mother.phone:
        wa.send_text(mother.phone, reply)
    return Handled(item.id if item else None, intent, reply, transcript)


def baby_or_mother_name(session: Session, item: ScheduleItem) -> str:
    if item.baby_id:
        baby = session.get(Baby, item.baby_id)
        return baby.name or "Baby"
    return session.get(Mother, item.mother_id).name
