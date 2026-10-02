"""Sign-in, staff accounts, the audit trail and the VHN field list."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from thodar import normalize
from thodar.auth import (
    ALL_ROLES,
    SENIOR,
    Actor,
    audit,
    check_lock,
    clear_failures,
    current_actor,
    hash_pin,
    make_token,
    record_failure,
    require,
    verify_pin,
)
from thodar.config import get_settings
from thodar.db import get_session
from thodar.models import AuditEvent, Channel, ItemStatus, Mother, Outcome, Role, ScheduleItem, Staff
from thodar.schedule_engine import expire_items
from thodar.worklist import effective_due

router = APIRouter()

# Demo accounts created by scripts/seed_demo.py. Shown on the sign-in page only in demo mode.
DEMO_ACCOUNTS = [
    {"name": "Revathi (nurse)", "phone": "9000100001", "pin": "1111", "role": Role.nurse, "villages": None},
    {"name": "Dr Sughapriya (doctor)", "phone": "9000100002", "pin": "2222", "role": Role.doctor, "villages": None},
    {"name": "Selvi (village health nurse)", "phone": "9000100003", "pin": "3333", "role": Role.vhn,
     "villages": "Melur,Vadipatti,Usilampatti"},
    {"name": "Clinic admin", "phone": "9000100004", "pin": "4444", "role": Role.admin, "villages": None},
]


def _staff_out(s: Staff) -> dict:
    return {"id": s.id, "name": s.name, "phone": s.phone, "role": s.role, "villages": s.village_list,
            "active": s.active}


class LoginIn(BaseModel):
    phone: str
    pin: str


@router.post("/auth/login")
def login(body: LoginIn, session: Session = Depends(get_session)):
    phone = normalize.phone(body.phone) or body.phone
    check_lock(phone)
    staff = session.scalars(select(Staff).where(Staff.phone == phone)).first()
    if staff is None or not staff.active or not verify_pin(body.pin, staff.pin_hash):
        record_failure(phone)
        raise HTTPException(401, "Phone number or PIN is wrong")
    clear_failures(phone)
    actor = Actor(staff.id, staff.name, staff.role, staff.village_list)
    audit(session, actor, "sign_in", "staff", staff.id)
    session.commit()
    return {"token": make_token(staff.id), "staff": _staff_out(staff)}


@router.get("/auth/me")
def me(actor: Actor = Depends(current_actor)):
    return {"id": actor.id, "name": actor.name, "role": actor.role, "villages": actor.villages,
            "auth_required": get_settings().auth_required}


@router.get("/auth/demo-accounts")
def demo_accounts():
    if not get_settings().demo_mode:
        return []
    return [{k: a[k] for k in ("name", "phone", "pin", "role")} for a in DEMO_ACCOUNTS]


def ensure_demo_staff(session: Session) -> None:
    for a in DEMO_ACCOUNTS:
        if not session.scalars(select(Staff).where(Staff.phone == a["phone"])).first():
            session.add(Staff(name=a["name"], phone=a["phone"], role=a["role"], villages=a["villages"],
                              pin_hash=hash_pin(a["pin"])))
    session.commit()


class StaffIn(BaseModel):
    name: str
    phone: str
    role: Role
    pin: str
    villages: str | None = None


@router.get("/staff")
def list_staff(_: Actor = Depends(require(Role.admin)), session: Session = Depends(get_session)):
    return [_staff_out(s) for s in session.scalars(select(Staff).order_by(Staff.name))]


@router.post("/staff")
def create_staff(body: StaffIn, actor: Actor = Depends(require(Role.admin)), session: Session = Depends(get_session)):
    phone = normalize.phone(body.phone)
    if not phone:
        raise HTTPException(422, "not a valid Indian mobile number")
    if len(body.pin) < 4 or not body.pin.isdigit():
        raise HTTPException(422, "PIN must be at least 4 digits")
    if session.scalars(select(Staff).where(Staff.phone == phone)).first():
        raise HTTPException(409, "a staff member already uses this number")
    s = Staff(name=body.name.strip(), phone=phone, role=body.role, villages=body.villages, pin_hash=hash_pin(body.pin))
    session.add(s)
    session.flush()
    audit(session, actor, "staff_created", "staff", s.id, role=body.role)
    session.commit()
    return _staff_out(s)


@router.post("/staff/{staff_id}/deactivate")
def deactivate_staff(staff_id: int, actor: Actor = Depends(require(Role.admin)),
                     session: Session = Depends(get_session)):
    s = session.get(Staff, staff_id)
    if s is None:
        raise HTTPException(404, "staff not found")
    s.active = False
    audit(session, actor, "staff_deactivated", "staff", s.id)
    session.commit()
    return _staff_out(s)


@router.get("/audit")
def audit_trail(limit: int = 200, action: str | None = None, target_type: str | None = None,
                target_id: int | None = None, _: Actor = Depends(require(*SENIOR)),
                session: Session = Depends(get_session)):
    stmt = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(min(limit, 1000))
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    if target_type:
        stmt = stmt.where(AuditEvent.target_type == target_type)
    if target_id is not None:
        stmt = stmt.where(AuditEvent.target_id == target_id)
    return [{"at": e.at, "staff": e.staff_name, "action": e.action, "target_type": e.target_type,
             "target_id": e.target_id, "detail": e.detail} for e in session.scalars(stmt)]


@router.get("/field/visits")
def field_visits(today: date | None = None, actor: Actor = Depends(require(*ALL_ROLES)),
                 session: Session = Depends(get_session)):
    """Home visits a nurse has asked a VHN to make, still open. A VHN sees only her villages."""
    today = today or date.today()
    expire_items(session, today)  # a visit past its catch-up period is missed, not a home visit
    session.commit()
    out = []
    for item in session.scalars(select(ScheduleItem).where(
            ScheduleItem.status.in_([ItemStatus.pending, ItemStatus.confirmed]))):
        if not item.attempts:
            continue
        last = max(item.attempts, key=lambda a: (a.at, a.id))
        if not (last.channel is Channel.visit and last.outcome is Outcome.sent):
            continue
        mother = session.get(Mother, item.mother_id)
        if not actor.can_see_village(mother.village):
            continue
        due = effective_due(item)
        out.append({
            "item_id": item.id, "mother_id": mother.id, "mother": mother.name, "phone": mother.phone,
            "family_phone": mother.family_phone, "village": mother.village or "Village unknown",
            "label": item.label, "for_baby": item.baby_id is not None, "due": due,
            "days_overdue": max((today - due).days, 0), "requested_at": last.at, "requested_by": last.actor,
        })
    out.sort(key=lambda v: (v["village"], v["mother"], -v["days_overdue"]))
    return out
