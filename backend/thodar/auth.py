"""Staff sign-in, roles and the audit trail.

- PINs are stored as salted PBKDF2-SHA256 hashes, never in clear.
- Tokens are `staff_id.expiry.signature` signed with HMAC-SHA256 over THODAR_SECRET_KEY.
- Five wrong PINs lock an account for 10 minutes.
- Every change to family data is written to `audit_events` with the staff member who made it.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from thodar.config import get_settings
from thodar.db import get_session
from thodar.models import AuditEvent, Role, Staff

ALL_ROLES = (Role.nurse, Role.doctor, Role.vhn, Role.admin)
OFFICE = (Role.nurse, Role.doctor, Role.admin)  # clinic-based staff
SENIOR = (Role.doctor, Role.admin)
LOCK_AFTER = 5
LOCK_SECONDS = 600

_failures: dict[str, tuple[int, float]] = {}


def hash_pin(pin: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 200_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    try:
        salt_hex, _ = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hash_pin(pin, bytes.fromhex(salt_hex)), stored)


def _sign(msg: str) -> str:
    key = get_settings().secret_key.encode()
    return base64.urlsafe_b64encode(hmac.new(key, msg.encode(), hashlib.sha256).digest()).decode().rstrip("=")


def make_token(staff_id: int, now: float | None = None) -> str:
    expiry = int((now or time.time()) + get_settings().token_hours * 3600)
    msg = f"{staff_id}.{expiry}"
    return f"{msg}.{_sign(msg)}"


def read_token(token: str, now: float | None = None) -> int | None:
    try:
        staff_id, expiry, sig = token.split(".")
        msg = f"{staff_id}.{expiry}"
        if not hmac.compare_digest(sig, _sign(msg)) or int(expiry) < (now or time.time()):
            return None
        return int(staff_id)
    except (ValueError, AttributeError):
        return None


def check_lock(phone: str) -> None:
    fails, since = _failures.get(phone, (0, 0.0))
    if fails >= LOCK_AFTER and time.time() - since < LOCK_SECONDS:
        raise HTTPException(429, "Too many wrong PINs. Try again in 10 minutes.")


def record_failure(phone: str) -> None:
    fails, since = _failures.get(phone, (0, time.time()))
    if time.time() - since > LOCK_SECONDS:
        fails, since = 0, time.time()
    _failures[phone] = (fails + 1, since)


def clear_failures(phone: str) -> None:
    _failures.pop(phone, None)


@dataclass
class Actor:
    """The signed-in staff member (or the system user when sign-in is switched off)."""

    id: int | None
    name: str
    role: Role
    villages: list[str]

    def can_see_village(self, village: str | None) -> bool:
        return self.role is not Role.vhn or not self.villages or (village or "").lower() in self.villages


SYSTEM = Actor(None, "system", Role.admin, [])


def current_actor(authorization: str = Header(default=""), session: Session = Depends(get_session)) -> Actor:
    if not get_settings().auth_required:
        return SYSTEM
    token = authorization.removeprefix("Bearer ").strip()
    staff_id = read_token(token) if token else None
    staff = session.get(Staff, staff_id) if staff_id else None
    if staff is None or not staff.active:
        raise HTTPException(401, "Sign in required")
    return Actor(staff.id, staff.name, staff.role, staff.village_list)


def require(*roles: Role):
    """Dependency: the signed-in actor, who must hold one of `roles`."""

    def dep(actor: Actor = Depends(current_actor)) -> Actor:
        if actor.role not in roles:
            raise HTTPException(403, f"Not allowed for role '{actor.role}'")
        return actor

    return dep


def audit(session: Session, actor: Actor, action: str, target_type: str | None = None,
          target_id: int | None = None, **detail) -> None:
    session.add(AuditEvent(staff_id=actor.id, staff_name=actor.name, action=action, target_type=target_type,
                           target_id=target_id,
                           detail=json.dumps(detail, ensure_ascii=False, default=str) if detail else None))
