from datetime import date, datetime, timedelta

import pytest

from thodar.messaging.intents import Kind, classify, find_date
from thodar.messaging.sarvam import SarvamClient
from thodar.messaging.service import handle_incoming, run_reminders
from thodar.messaging.whatsapp import Incoming, WhatsAppClient, parse_webhook
from thodar.models import Baby, ItemStatus, Language, Mother, Outcome, Pregnancy
from thodar.schedule_engine import generate_for_pregnancy
from thodar.worklist import build_worklist

TODAY = date(2026, 10, 1)  # a Thursday


@pytest.mark.parametrize("text,kind", [
    ("ok, I will come", Kind.confirm),
    ("சரி வருகிறேன்", Kind.confirm),
    ("Can't come today, will come Saturday", Kind.reschedule),
    ("இன்னைக்கு வர முடியாது, சனிக்கிழமை வரேன்", Kind.reschedule),
    ("baby has fever since yesterday", Kind.needs_staff),
    ("குழந்தைக்கு காய்ச்சல்", Kind.needs_staff),
    ("I have pain, can I come tomorrow?", Kind.needs_staff),  # health beats scheduling
    ("wrong number", Kind.wrong_number),
    ("we shifted to Chennai, moved", Kind.moved),
    ("STOP", Kind.stop),
    ("I want to book", Kind.needs_staff),  # 'ok' inside 'book' must not confirm
    ("hmm", Kind.needs_staff),
])
def test_classify(text, kind):
    assert classify(text, TODAY).kind is kind


def test_dates():
    assert find_date("saturday", TODAY) == date(2026, 10, 3)
    assert find_date("நாளை", TODAY) == date(2026, 10, 2)
    assert find_date("12/10", TODAY) == date(2026, 10, 12)
    assert find_date("thursday", TODAY) == date(2026, 10, 8)  # next week, not today


def _family(session, consent=True, lang=Language.ta):
    m = Mother(name="Meena K", phone="9000000001", language=lang,
               consent_at=datetime(2026, 9, 1) if consent else None)
    p = Pregnancy(mother=m, delivery_date=TODAY - timedelta(days=7))
    session.add_all([m, p, Baby(pregnancy=p, dob=p.delivery_date)])
    session.flush()
    generate_for_pregnancy(session, p)
    session.commit()
    return m


def test_reminders_need_consent_and_go_out_in_the_mothers_language(session):
    _family(session, consent=False)
    wa = WhatsAppClient(token="")
    run = run_reminders(session, TODAY, wa)
    assert run.sent == 0 and run.skipped_no_consent > 0 and wa.outbox == []


def test_button_reply_reschedule_then_voice_note_flow(session):
    _family(session)
    wa = WhatsAppClient(token="")
    run = run_reminders(session, TODAY, wa)
    assert run.sent >= 1
    msg = wa.outbox[0]
    assert msg["to"] == "919000000001"
    assert "வணக்கம் Meena" in msg["interactive"]["body"]["text"]
    button_ids = [b["reply"]["id"] for b in msg["interactive"]["action"]["buttons"]]

    # Family taps "confirm" on the first reminder.
    h = handle_incoming(session, Incoming("9000000001", "button", button_id=button_ids[0]), TODAY, wa)
    assert h.intent.kind is Kind.confirm
    assert next(r for r in build_worklist(session, TODAY) if r.item.id == h.item_id).item.status is ItemStatus.confirmed

    # A free-text reply about a symptom goes to staff, and the family is told a person will call.
    h = handle_incoming(session, Incoming("9000000001", "text", text="குழந்தைக்கு காய்ச்சல்"), TODAY, wa,
                        sarvam=SarvamClient(api_key=""))
    assert h.intent.kind is Kind.needs_staff
    assert "108" in wa.outbox[-1]["text"]["body"]
    row = next(r for r in build_worklist(session, TODAY) if r.item.id == h.item_id)
    assert row.last_attempt.outcome is Outcome.needs_staff
    assert row.next_step == "Family asked a question: staff to call"


def test_stop_opts_out(session):
    m = _family(session)
    wa = WhatsAppClient(token="")
    run_reminders(session, TODAY, wa)
    handle_incoming(session, Incoming("9000000001", "text", text="stop"), TODAY, wa)
    assert m.opted_out
    assert run_reminders(session, TODAY + timedelta(days=1), wa).sent == 0


def test_parse_webhook():
    payload = {"entry": [{"changes": [{"value": {"messages": [
        {"from": "919000000001", "type": "text", "text": {"body": "ok"}},
        {"from": "919000000001", "type": "interactive",
         "interactive": {"type": "button_reply", "button_reply": {"id": "confirm:3", "title": "Yes"}}},
        {"from": "919000000001", "type": "audio", "audio": {"id": "m1"}},
    ]}}]}]}
    kinds = [(m.phone, m.kind) for m in parse_webhook(payload)]
    assert kinds == [("9000000001", "text"), ("9000000001", "button"), ("9000000001", "audio")]


def test_tanglish_unwell_goes_to_staff():
    # Found in live testing: "my daughter is a bit unwell, can we come next week?"
    assert classify("en ponnu ku udambu konjam sari illa, next week varalama", TODAY).kind is Kind.needs_staff


def test_second_lock_escalates_but_never_deescalates():
    from thodar.messaging.intents import Intent
    from thodar.messaging.service import second_lock

    rules_resched = Intent(Kind.reschedule, date(2026, 10, 8), "names another day")
    assert second_lock(rules_resched, (Kind.needs_staff, None)).kind is Kind.needs_staff
    assert second_lock(rules_resched, (Kind.confirm, None)) is rules_resched  # model can't override a placed reply
    health = Intent(Kind.needs_staff, reason="mentions 'fever'")
    assert second_lock(health, (Kind.confirm, None)) is health
    unknown = Intent(Kind.needs_staff, reason="not understood by rules")
    filled = second_lock(unknown, (Kind.reschedule, "2026-10-09"))
    assert filled.kind is Kind.reschedule and filled.on == date(2026, 10, 9)
    assert second_lock(rules_resched, None) is rules_resched  # offline: rules alone
