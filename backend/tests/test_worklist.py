from datetime import date, timedelta

import pytest

from thodar.models import Baby, Channel, ItemStatus, Mother, Outcome, Pregnancy
from thodar.schedule_engine import generate_for_pregnancy
from thodar.worklist import Action, Bucket, build_worklist, record_action

TODAY = date(2026, 10, 1)


def _delivered(session, name, days_ago, phone):
    m = Mother(name=name, phone=phone)
    p = Pregnancy(mother=m, delivery_date=TODAY - timedelta(days=days_ago))
    b = Baby(pregnancy=p, dob=p.delivery_date)
    session.add_all([m, p, b])
    session.flush()
    generate_for_pregnancy(session, p)
    session.flush()
    return m, p, b


def test_sorted_by_days_overdue_only(session):
    _delivered(session, "Meena K", 10, "9000000001")  # PNC day 7 is 3 days overdue
    _delivered(session, "Priya S", 70, "9000000002")  # 10-week vaccines due today
    rows = build_worklist(session, TODAY)
    assert rows[0].days_overdue >= rows[-1].days_overdue
    tenweek = next(r for r in rows if r.item.code == "uip-10w")
    assert tenweek.bucket is Bucket.due_today and tenweek.who == "Baby of Priya S"


def test_two_failed_calls_make_a_row_unreachable_and_suggest_a_visit(session):
    _delivered(session, "Kavitha R", 10, "9000000003")
    row = next(r for r in build_worklist(session, TODAY) if r.item.code == "pnc-d7")
    assert row.next_step == "Send WhatsApp reminder"

    record_action(session, row.item, Action.no_answer, channel=Channel.voice)
    record_action(session, row.item, Action.no_answer, channel=Channel.voice)
    session.flush()
    row = next(r for r in build_worklist(session, TODAY) if r.item.code == "pnc-d7")
    assert row.bucket is Bucket.unreachable and row.next_step == "Ask VHN to visit"


def test_reschedule_moves_the_item_and_shows_the_booking(session):
    _delivered(session, "Meena K", 10, "9000000001")
    row = next(r for r in build_worklist(session, TODAY) if r.item.code == "pnc-d7")
    record_action(session, row.item, Action.reschedule, on=TODAY + timedelta(days=3),
                  note="will come Saturday", actor="family", channel=Channel.whatsapp)
    session.flush()
    row = next(r for r in build_worklist(session, TODAY) if r.item.code == "pnc-d7")
    assert row.days_overdue == 0 and row.next_step.startswith("Booked")
    assert row.last_attempt.outcome is Outcome.reschedule


def test_done_items_leave_the_list_and_supersede_earlier_misses(session):
    m, p, b = _delivered(session, "Anitha M", 20, "9000000004")
    rows = {r.item.code: r for r in build_worklist(session, TODAY)}
    assert "pnc-d7" in rows and "pnc-d3" in rows
    record_action(session, rows["pnc-d7"].item, Action.done, on=TODAY)
    session.flush()
    codes = {r.item.code for r in build_worklist(session, TODAY)}
    assert "pnc-d7" not in codes and "pnc-d3" not in codes  # d3 superseded by a later completed visit
    assert rows["pnc-d7"].item.status is ItemStatus.done


def test_reschedule_requires_a_date(session):
    _delivered(session, "Selvi T", 10, "9000000005")
    row = build_worklist(session, TODAY)[0]
    with pytest.raises(ValueError):
        record_action(session, row.item, Action.reschedule)


def test_family_waiting_for_staff_goes_first(session):
    _delivered(session, "Selvi T", 60, "9000000006")  # older, more overdue items
    _, p, _ = _delivered(session, "Meena K", 10, "9000000001")
    meena_item = next(r for r in build_worklist(session, TODAY) if r.mother.name == "Meena K").item
    record_action(session, meena_item, Action.notify_doctor, note="family asked a question", actor="family")
    session.flush()
    assert build_worklist(session, TODAY)[0].mother.name == "Meena K"
