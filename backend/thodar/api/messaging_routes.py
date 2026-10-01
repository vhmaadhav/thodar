"""Endpoints for WhatsApp (webhook + reminder runs) and for the Sarvam voice agent's tool calls."""

from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from thodar import normalize
from thodar.config import get_settings
from thodar.db import get_session
from thodar.messaging import templates
from thodar.messaging.service import handle_incoming, run_reminders
from thodar.messaging.whatsapp import WhatsAppClient, parse_webhook
from thodar.models import Channel, ContactAttempt, Mother, Outcome, ScheduleItem
from thodar.worklist import Action, build_worklist, effective_due, record_action

router = APIRouter()
_wa = WhatsAppClient()


def whatsapp() -> WhatsAppClient:
    return _wa


@router.post("/reminders/run")
def reminders_run(today: date | None = None, session: Session = Depends(get_session),
                  wa: WhatsAppClient = Depends(whatsapp)):
    run = run_reminders(session, today or date.today(), wa, clinic=get_settings().clinic_name)
    return {**run.__dict__, "dry_run": not wa.enabled}


@router.get("/outbox")
def outbox(wa: WhatsAppClient = Depends(whatsapp)):
    """Messages that would have been sent (dry-run mode only). Used by the demo UI."""
    return wa.outbox[-50:]


@router.get("/webhooks/whatsapp", response_class=PlainTextResponse)
def verify(mode: str = Query(alias="hub.mode"), token: str = Query(alias="hub.verify_token"),
           challenge: str = Query(alias="hub.challenge")):
    if mode == "subscribe" and token == get_settings().whatsapp_verify_token:
        return challenge
    raise HTTPException(403, "verification failed")


@router.post("/webhooks/whatsapp")
async def receive(request: Request, today: date | None = None, session: Session = Depends(get_session),
                  wa: WhatsAppClient = Depends(whatsapp)):
    handled = []
    for msg in parse_webhook(await request.json()):
        h = handle_incoming(session, msg, today or date.today(), wa)
        handled.append({"item_id": h.item_id, "intent": h.intent.kind, "reason": h.intent.reason,
                        "transcript": h.transcript})
    return {"handled": handled}


# --- Sarvam Voice Agent tools ------------------------------------------------------------------
# The agent may only look up what is due and record a scheduling outcome. It cannot read or
# write anything clinical, and every call is logged as a contact attempt.

def _tool_auth(x_thodar_tool_key: str = Header(default="")) -> None:
    if x_thodar_tool_key != get_settings().voice_tool_key:
        raise HTTPException(401, "bad tool key")


class LookupIn(BaseModel):
    phone: str
    today: date | None = None


class UpdateIn(BaseModel):
    item_id: int
    outcome: Outcome
    new_date: date | None = None
    note: str | None = None


@router.post("/voice/tools/lookup", dependencies=[Depends(_tool_auth)])
def voice_lookup(body: LookupIn, session: Session = Depends(get_session)):
    phone = normalize.phone(body.phone)
    mother = session.scalars(select(Mother).where(Mother.phone == phone)).first() if phone else None
    if mother is None:
        return {"found": False}
    today = body.today or date.today()
    rows = [r for r in build_worklist(session, today) if r.mother.id == mother.id]
    if not rows:
        return {"found": True, "due": None}
    r = rows[0]
    kind = "nb" if r.item.code.startswith("nb-") else r.item.schedule
    return {
        "found": True,
        "name": mother.name.split()[0],
        "language": mother.language,
        "due": {
            "item_id": r.item.id,
            "what": templates.WHAT[mother.language][kind],
            "date": max(effective_due(r.item), today).isoformat(),
        },
    }


@router.post("/voice/tools/update", dependencies=[Depends(_tool_auth)])
def voice_update(body: UpdateIn, session: Session = Depends(get_session)):
    item = session.get(ScheduleItem, body.item_id)
    if item is None:
        raise HTTPException(404, "item not found")
    if body.outcome is Outcome.confirmed:
        record_action(session, item, Action.confirm, note=body.note, actor="voice-agent", channel=Channel.voice)
    elif body.outcome is Outcome.reschedule and body.new_date:
        record_action(session, item, Action.reschedule, on=body.new_date, note=body.note, actor="voice-agent",
                      channel=Channel.voice)
    else:
        session.add(ContactAttempt(item=item, channel=Channel.voice, outcome=body.outcome,
                                   note=body.note, actor="voice-agent"))
    session.commit()
    return {"ok": True}
