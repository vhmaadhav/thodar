from datetime import date, timedelta

from thodar.models import Baby, ItemStatus, Mother, Pregnancy, Subject
from thodar.schedule_engine import cancel_remaining_anc, generate_for_pregnancy


def _pregnancy(session, **kw):
    m = Mother(name="Kavitha R", phone="9800000001")
    p = Pregnancy(mother=m, **kw)
    session.add_all([m, p])
    session.flush()
    return p


def test_anc_items_from_lmp(session):
    lmp = date(2026, 3, 1)
    p = _pregnancy(session, lmp=lmp)
    items = generate_for_pregnancy(session, p)
    assert [i.code for i in items] == ["anc-1", "anc-2", "anc-3", "anc-4"]
    assert items[2].due_date == lmp + timedelta(days=196)
    assert all(i.subject is Subject.mother and i.owner == "obstetrics" for i in items)


def test_generation_is_idempotent(session):
    p = _pregnancy(session, lmp=date(2026, 3, 1))
    generate_for_pregnancy(session, p)
    session.flush()
    assert generate_for_pregnancy(session, p) == []


def test_delivery_creates_baby_schedule_next_to_mother_pnc(session):
    dob = date(2026, 9, 1)
    p = _pregnancy(session, lmp=date(2025, 12, 1), delivery_date=dob)
    baby = Baby(pregnancy=p, name="Baby of Kavitha R", dob=dob)
    session.add(baby)
    session.flush()

    items = generate_for_pregnancy(session, p)
    mother_pnc = [i for i in items if i.schedule == "pnc" and i.subject is Subject.mother]
    baby_items = [i for i in items if i.subject is Subject.baby]

    assert {i.code for i in mother_pnc} == {"pnc-48h", "pnc-d3", "pnc-d7", "pnc-d42"}
    assert "uip-10w" in {i.code for i in baby_items}
    assert all(i.owner == "paediatrics" and i.baby_id == baby.id for i in baby_items)
    tenweek = next(i for i in baby_items if i.code == "uip-10w")
    assert tenweek.due_date == dob + timedelta(days=70)


def test_anc_after_preterm_birth_is_not_generated_or_is_cancelled(session):
    lmp = date(2026, 1, 1)
    p = _pregnancy(session, lmp=lmp)
    generate_for_pregnancy(session, p)
    session.flush()

    p.delivery_date = lmp + timedelta(days=240)  # ~34 weeks
    cancelled = cancel_remaining_anc(session, p)
    assert cancelled == 1  # anc-4 at 36 weeks no longer applies


def test_doctor_set_interval_overrides_spacing(session):
    p = _pregnancy(session, lmp=date(2026, 3, 1), doctor_anc_interval_days=28)
    items = generate_for_pregnancy(session, p)
    gaps = {(b.due_date - a.due_date).days for a, b in zip(items, items[1:])}
    assert gaps == {28}
    assert len(items) > 4
    assert all(i.status is ItemStatus.pending for i in items)
