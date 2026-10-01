"""Endpoints for WhatsApp (webhook + reminder runs) and for the Sarvam voice agent's tool calls."""

import base64
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from thodar import normalize
from thodar.config import get_settings
from thodar.db import get_session
from thodar.messaging import templates
from thodar.messaging.service import handle_incoming, run_reminders
from thodar.messaging.sarvam import SarvamClient
from thodar.messaging.whatsapp import Incoming, WhatsAppClient, parse_webhook
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


_voice_cache: dict[str, bytes] = {}


@router.get("/items/{item_id}/voice-preview")
def voice_preview(item_id: int, today: date | None = None, session: Session = Depends(get_session)):
    """The reminder exactly as the voice call will speak it (Bulbul v3), so staff can hear it first."""
    item = session.get(ScheduleItem, item_id)
    if item is None:
        raise HTTPException(404, "item not found")
    mother = session.get(Mother, item.mother_id)
    on = max(effective_due(item), today or date.today())
    text = templates.reminder(item, mother.name.split()[0], on, get_settings().clinic_name, mother.language)
    text = text.split("?")[0] + "?"  # spoken version: drop the 'tap a button' line
    if text not in _voice_cache:
        audio = SarvamClient().speak(text, "ta-IN" if mother.language.value == "ta" else "en-IN", speaker="kavitha")
        if audio is None:
            raise HTTPException(501, "Voice preview needs THODAR_SARVAM_API_KEY.")
        _voice_cache[text] = base64.b64decode(audio)
    return Response(_voice_cache[text], media_type="audio/wav", headers={"X-Reminder-Text": quote(text)})


@router.post("/demo/voice-note")
async def demo_voice_note(file: UploadFile, phone: str = Form(...), today: date | None = None,
                          session: Session = Depends(get_session), wa: WhatsAppClient = Depends(whatsapp)):
    """Demo stand-in for a WhatsApp voice note: same path as the webhook, audio uploaded directly."""
    p = normalize.phone(phone)
    if not p:
        raise HTTPException(422, "invalid phone")
    h = handle_incoming(session, Incoming(p, "audio"), today or date.today(), wa, audio=await file.read())
    return {"item_id": h.item_id, "intent": h.intent.kind, "reason": h.intent.reason, "transcript": h.transcript}


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
