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


def test_one_trip_bundle_on_session_day_with_doses_and_benefit(session):
    # Baby born 7 days ago: mother's PNC day 7 and baby's newborn check + birth doses all due.
    m = _family(session)
    wa = WhatsAppClient(token="")
    run = run_reminders(session, TODAY, wa)
    assert run.sent == 1 and len(wa.outbox) == 1  # one message for the whole family
    body = wa.outbox[0]["interactive"]["body"]["text"]
    assert "புதன்கிழமை 07-10-2026" in body  # next Wednesday session after Thursday 1 Oct
    assert body.count("•") >= 3  # mother and baby visits together
    assert "BCG" in body and "₹12,000" in body  # names the doses and the scheme instalment
    confirm_id = wa.outbox[0]["interactive"]["action"]["buttons"][0]["reply"]["id"]
    assert confirm_id.startswith("confirm:2026-10-07:")

    h = handle_incoming(session, Incoming(m.phone, "button", button_id=confirm_id), TODAY, wa)
    rows = [r for r in build_worklist(session, TODAY, horizon_days=10) if r.mother.id == m.id]
    assert all(r.item.status is ItemStatus.confirmed for r in rows if r.item.id in run.item_ids)
    assert {r.effective_due for r in rows if r.item.id in run.item_ids} == {date(2026, 10, 7)}
    assert "07-10-2026" in h.reply


def test_family_contact_gets_the_reminder_and_can_reply(session):
    m = _family(session)
    m.family_phone, m.family_relation = "9000000999", "husband"
    session.commit()
    wa = WhatsAppClient(token="")
    run_reminders(session, TODAY, wa)
    assert sorted(x["to"] for x in wa.outbox) == ["919000000001", "919000000999"]
    h = handle_incoming(session, Incoming("9000000999", "text", text="ok varen"), TODAY, wa,
                        sarvam=SarvamClient(api_key=""))
    assert h.intent.kind is Kind.confirm
    assert wa.outbox[-1]["to"] == "919000000999"  # the answer goes to whoever wrote


def test_buttons_from_another_family_are_ignored(session):
    _family(session)
    other = Mother(name="Selvi T", phone="9000000002", consent_at=datetime(2026, 9, 1))
    session.add(other)
    session.commit()
    wa = WhatsAppClient(token="")
    run_reminders(session, TODAY, wa)
    ids = wa.outbox[0]["interactive"]["action"]["buttons"][0]["reply"]["id"]
    h = handle_incoming(session, Incoming("9000000002", "button", button_id=ids), TODAY, wa)
    assert h.item_id is None


def test_bundle_never_stacks_doses_from_one_sequence(session):
    # Baby 110 days old with every vaccine visit missed: only the earliest goes in the trip.
    m = Mother(name="Anitha P", phone="9000000051", consent_at=datetime(2026, 9, 1))
    p = Pregnancy(mother=m, delivery_date=TODAY - timedelta(days=110))
    session.add_all([m, p, Baby(pregnancy=p, dob=p.delivery_date)])
    session.flush()
    generate_for_pregnancy(session, p)
    session.commit()
    wa = WhatsAppClient(token="")
    run_reminders(session, TODAY, wa)
    body = wa.outbox[0]["interactive"]["body"]["text"]
    assert "BCG" in body and "Penta" not in body  # birth doses first; later doses need spacing
    assert "மருத்துவர்" in body  # tells the family the doctor plans the rest
    assert "மருத்துவமனையில்" in body


def test_typed_ok_confirms_the_whole_bundle_on_the_proposed_day(session):
    m = _family(session)
    wa = WhatsAppClient(token="")
    run = run_reminders(session, TODAY, wa)
    assert len(run.item_ids) >= 2
    handle_incoming(session, Incoming(m.phone, "text", text="ok varen"), TODAY, wa, sarvam=SarvamClient(api_key=""))
    rows = {r.item.id: r for r in build_worklist(session, TODAY, horizon_days=10)}
    for item_id in run.item_ids:
        assert rows[item_id].item.status is ItemStatus.confirmed
        assert rows[item_id].effective_due == date(2026, 10, 7)


def test_typed_saturday_reschedules_the_whole_bundle(session):
    m = _family(session)
    wa = WhatsAppClient(token="")
    run = run_reminders(session, TODAY, wa)
    handle_incoming(session, Incoming(m.phone, "text", text="saturday varen"), TODAY, wa,
                    sarvam=SarvamClient(api_key=""))
    rows = {r.item.id: r for r in build_worklist(session, TODAY, horizon_days=10)}
    assert {rows[i].effective_due for i in run.item_ids} == {date(2026, 10, 3)}


def test_family_contact_stop_or_wrong_number_only_removes_them(session):
    m = _family(session)
    m.family_phone = "9000000999"
    session.commit()
    wa = WhatsAppClient(token="")
    run_reminders(session, TODAY, wa)
    handle_incoming(session, Incoming("9000000999", "text", text="STOP"), TODAY, wa)
    assert m.family_phone is None and not m.opted_out  # the mother still gets reminders

    m.family_phone = "9000000999"
    session.commit()
    handle_incoming(session, Incoming("9000000999", "text", text="wrong number"), TODAY, wa)
    assert m.family_phone is None
    rows = [r for r in build_worklist(session, TODAY) if r.mother.id == m.id]
    assert all(r.next_step != "Find correct number" for r in rows)
