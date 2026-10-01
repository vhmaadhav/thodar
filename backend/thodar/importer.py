"""Imports the registers a clinic already keeps (CSV or Excel) into one thread per mother–baby pair.

Three sources, each with the column names clinics actually use:
- ANC register: RCH ID, Name, Mobile, Village, LMP, ANC1..ANC4 (dates attended)
- Delivery register: Date, Mother name, Ph no, RCH no, Baby sex, Village, optional PNC/newborn visit dates
- Immunisation register: Child name, DOB, Mother mobile, then one column per visit (Birth, 6 wk, ...)
"""

import json
from dataclasses import dataclass, field
from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from thodar import normalize
from thodar.linking import Candidate, best_link
from thodar.models import Baby, ItemStatus, LinkReview, Mother, Pregnancy, ScheduleItem
from thodar.schedule_engine import cancel_remaining_anc, generate_for_pregnancy

PNC_COLUMNS = {  # delivery-register column -> (code, belongs to baby)
    "pnc 48h": ("pnc-48h", False),
    "pnc d3": ("pnc-d3", False),
    "pnc d7": ("pnc-d7", False),
    "pnc 6wk": ("pnc-d42", False),
    "newborn 48h": ("nb-48h", True),
    "newborn d7": ("nb-d7", True),
}

UIP_COLUMNS = {
    "birth": "uip-birth",
    "6 wk": "uip-6w",
    "10 wk": "uip-10w",
    "14 wk": "uip-14w",
    "9 mo": "uip-9m",
    "16 mo": "uip-16m",
}


@dataclass
class ImportReport:
    source: str
    rows: int = 0
    created: int = 0
    linked: int = 0
    sent_to_review: int = 0
    skipped: list[str] = field(default_factory=list)


def read_table(path_or_buffer, filename: str = "") -> pd.DataFrame:
    name = filename or str(path_or_buffer)
    if name.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(path_or_buffer, dtype=str)
    else:
        df = pd.read_csv(path_or_buffer, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    return df.where(df.notna(), None)


def _date(value) -> date | None:
    if not value:
        return None
    parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def _col(row: dict, *names: str):
    lowered = {k.lower(): v for k, v in row.items()}
    for n in names:
        if n.lower() in lowered and lowered[n.lower()] not in (None, ""):
            return lowered[n.lower()]
    return None


def _known(session: Session) -> list[Candidate]:
    out = []
    for m in session.scalars(select(Mother)):
        lmp = next((p.lmp for p in m.pregnancies if p.delivery_date is None and p.lmp), None)
        out.append(Candidate(m.id, m.name, m.phone, m.rch_id, m.abha, m.village, lmp))
    return out


def _resolve_mother(session: Session, row: dict, cand: Candidate, source: str,
                    report: ImportReport, event_date: date | None = None) -> Mother | None:
    """Returns the matched or newly created mother; None when the row went to review."""
    link = best_link(cand, _known(session), event_date)
    if link and link.decision == "match":
        mother = session.get(Mother, link.key)
        # Fill identifiers the earlier register did not have.
        mother.rch_id = mother.rch_id or cand.rch_id
        mother.phone = mother.phone or cand.phone
        mother.abha = mother.abha or cand.abha
        report.linked += 1
        return mother
    if link and link.decision == "review":
        session.add(LinkReview(source=source, row=json.dumps(row, default=str),
                               candidate_mother_id=link.key, score=link.score, reason=link.reason))
        report.sent_to_review += 1
        return None
    mother = Mother(name=cand.name.strip(), phone=cand.phone, rch_id=cand.rch_id,
                    abha=cand.abha, village=cand.village)
    session.add(mother)
    session.flush()
    report.created += 1
    return mother


def _mark_done(session: Session, pregnancy_id: int, code: str, on: date, baby_id: int | None = None) -> None:
    stmt = select(ScheduleItem).where(ScheduleItem.pregnancy_id == pregnancy_id, ScheduleItem.code == code)
    stmt = stmt.where(ScheduleItem.baby_id == baby_id) if baby_id else stmt.where(ScheduleItem.baby_id.is_(None))
    item = session.scalars(stmt).first()
    if item and item.status is not ItemStatus.done:
        item.status = ItemStatus.done
        item.completed_on = on


def _open_pregnancy(mother: Mother) -> Pregnancy | None:
    return next((p for p in mother.pregnancies if p.delivery_date is None), None)


def import_anc_register(session: Session, df: pd.DataFrame) -> ImportReport:
    report = ImportReport("anc_register")
    for row in df.to_dict("records"):
        report.rows += 1
        name = _col(row, "Name", "Mother name")
        lmp = _date(_col(row, "LMP"))
        if not name or not lmp:
            report.skipped.append(f"row {report.rows}: missing name or LMP")
            continue
        cand = Candidate(0, name, normalize.phone(_col(row, "Mobile", "Phone", "Ph no")),
                         normalize.rch_id(_col(row, "RCH ID", "RCH no")), normalize.abha(_col(row, "ABHA")),
                         _col(row, "Village"))
        mother = _resolve_mother(session, row, cand, report.source, report)
        if mother is None:
            continue
        pregnancy = _open_pregnancy(mother)
        if pregnancy is None:
            pregnancy = Pregnancy(mother=mother, lmp=lmp)
            session.add(pregnancy)
            session.flush()
        pregnancy.lmp = pregnancy.lmp or lmp
        generate_for_pregnancy(session, pregnancy)
        session.flush()
        for n in range(1, 5):
            attended = _date(_col(row, f"ANC{n}", f"ANC {n}"))
            if attended:
                _mark_done(session, pregnancy.id, f"anc-{n}", attended)
    session.commit()
    return report


def import_delivery_register(session: Session, df: pd.DataFrame) -> ImportReport:
    report = ImportReport("delivery_register")
    for row in df.to_dict("records"):
        report.rows += 1
        name = _col(row, "Mother name", "Name")
        delivered = _date(_col(row, "Date", "Delivery date"))
        if not name or not delivered:
            report.skipped.append(f"row {report.rows}: missing name or date")
            continue
        cand = Candidate(0, name, normalize.phone(_col(row, "Ph no", "Mobile", "Phone")),
                         normalize.rch_id(_col(row, "RCH no", "RCH ID")), normalize.abha(_col(row, "ABHA")),
                         _col(row, "Village"))
        mother = _resolve_mother(session, row, cand, report.source, report, event_date=delivered)
        if mother is None:
            continue
        pregnancy = _open_pregnancy(mother) or Pregnancy(mother=mother)
        pregnancy.delivery_date = delivered
        session.add(pregnancy)
        session.flush()
        cancel_remaining_anc(session, pregnancy)
        if not pregnancy.babies:
            session.add(Baby(pregnancy=pregnancy, name=f"Baby of {mother.name}", dob=delivered,
                             sex=(_col(row, "Baby sex", "Sex") or "")[:1].upper() or None))
            session.flush()
        generate_for_pregnancy(session, pregnancy)
        session.flush()
        baby = pregnancy.babies[0] if pregnancy.babies else None
        for column, (code, for_baby) in PNC_COLUMNS.items():
            seen = _date(_col(row, column))
            if seen and (baby or not for_baby):
                _mark_done(session, pregnancy.id, code, seen, baby_id=baby.id if for_baby else None)
    session.commit()
    return report


def import_immunisation_register(session: Session, df: pd.DataFrame) -> ImportReport:
    report = ImportReport("immunisation_register")
    for row in df.to_dict("records"):
        report.rows += 1
        child = _col(row, "Child name", "Name")
        dob = _date(_col(row, "DOB", "Date of birth"))
        if not child or not dob:
            report.skipped.append(f"row {report.rows}: missing child name or DOB")
            continue
        # Registers name the child "Baby of <mother>"; link on the mother.
        cand = Candidate(0, child, normalize.phone(_col(row, "Mother mobile", "Mobile")), None, None)
        link = best_link(cand, _known(session))
        if not link or link.decision != "match":
            if link:
                session.add(LinkReview(source=report.source, row=json.dumps(row, default=str),
                                       candidate_mother_id=link.key, score=link.score, reason=link.reason))
                report.sent_to_review += 1
            else:
                report.skipped.append(f"row {report.rows}: no delivery on record for {child}")
            continue
        mother = session.get(Mother, link.key)
        baby = next((b for p in mother.pregnancies for b in p.babies if b.dob == dob), None)
        if baby is None:
            report.skipped.append(f"row {report.rows}: {child} not in delivery register")
            continue
        report.linked += 1
        for column, code in UIP_COLUMNS.items():
            given = _date(_col(row, column))
            if given:
                _mark_done(session, baby.pregnancy_id, code, given, baby_id=baby.id)
    session.commit()
    return report
