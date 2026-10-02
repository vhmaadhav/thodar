import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from thodar import auth
from thodar.api.auth_routes import ensure_demo_staff
from thodar.api.main import app
from thodar.config import get_settings
from thodar.db import get_session, init_db

ANC = """RCH ID,Name,Mobile,Village,LMP,ANC1
331234567890,Meena K,9000000001,Melur,01-12-2025,28-01-2026
339999999999,Priya S,9000000002,Peraiyur,01-12-2025,28-01-2026
"""
DELIVERY = """Date,Mother name,Ph no,RCH no,Baby sex,Village
21-09-2026,K. Meena,9000000001,,F,Melur
21-09-2026,S. Priya,9000000002,,M,Peraiyur
"""
NURSE, DOCTOR, VHN, ADMIN = "9000100001", "9000100002", "9000100003", "9000100004"
PINS = {NURSE: "1111", DOCTOR: "2222", VHN: "3333", ADMIN: "4444"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("THODAR_AUTH_REQUIRED", "true")
    monkeypatch.setenv("THODAR_SECRET_KEY", "test-secret")
    get_settings.cache_clear()
    auth._failures.clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as s:
        ensure_demo_staff(s)

    def override():
        with Session() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def login(client, phone):
    r = client.post("/auth/login", json={"phone": phone, "pin": PINS[phone]})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_everything_needs_sign_in_except_health_and_webhooks(client):
    assert client.get("/worklist").status_code == 401
    assert client.get("/families").status_code == 401
    assert client.post("/reminders/run").status_code == 401
    assert client.get("/health").status_code == 200
    body = {"entry": [{"changes": [{"value": {"messages": []}}]}]}
    assert client.post("/webhooks/whatsapp", json=body).status_code == 200


def test_wrong_pin_and_lockout(client):
    for _ in range(5):
        assert client.post("/auth/login", json={"phone": NURSE, "pin": "0000"}).status_code == 401
    assert client.post("/auth/login", json={"phone": NURSE, "pin": "1111"}).status_code == 429


def test_tampered_or_expired_token_is_rejected(client):
    h = login(client, NURSE)
    token = h["Authorization"].removeprefix("Bearer ")
    staff_id, expiry, sig = token.split(".")
    forged = f"{int(staff_id) + 3}.{expiry}.{sig}"  # try to become the admin
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    assert auth.read_token(token, now=int(expiry) + 1) is None


def test_roles_and_audit_trail(client):
    nurse, doctor, admin = login(client, NURSE), login(client, DOCTOR), login(client, ADMIN)
    assert client.post("/import/anc", files={"file": ("anc.csv", ANC)}, headers=nurse).status_code == 200
    client.post("/import/delivery", files={"file": ("d.csv", DELIVERY)}, headers=nurse)

    # Only doctors/admins export or erase, and read the audit trail
    assert client.get("/mothers/1/export", headers=nurse).status_code == 403
    assert client.get("/mothers/1/export", headers=doctor).status_code == 200
    assert client.get("/audit", headers=nurse).status_code == 403
    events = client.get("/audit", headers=doctor).json()
    actions = [e["action"] for e in events]
    assert "register_imported" in actions and "family_exported" in actions and "sign_in" in actions
    assert any(e["staff"].startswith("Dr Sughapriya") for e in events if e["action"] == "family_exported")

    # Only admins manage staff
    new = {"name": "Kala", "phone": "9000100099", "role": "vhn", "pin": "5678", "villages": "Peraiyur"}
    assert client.post("/staff", json=new, headers=doctor).status_code == 403
    assert client.post("/staff", json=new, headers=admin).json()["villages"] == ["peraiyur"]


def test_vhn_field_mode_is_limited_to_her_villages(client):
    nurse, vhn = login(client, NURSE), login(client, VHN)
    client.post("/import/anc", files={"file": ("anc.csv", ANC)}, headers=nurse)
    client.post("/import/delivery", files={"file": ("d.csv", DELIVERY)}, headers=nurse)
    rows = client.get("/worklist", params={"today": "2026-10-01"}, headers=nurse).json()
    melur = next(r for r in rows if r["village"] == "Melur")
    peraiyur = next(r for r in rows if r["village"] == "Peraiyur")
    for r in (melur, peraiyur):  # nurse asks the VHN to visit both families
        client.post(f"/items/{r['item_id']}/actions", json={"action": "request_visit"}, headers=nurse)

    field = client.get("/field/visits", params={"today": "2026-10-01"}, headers=vhn).json()
    assert [v["village"] for v in field] == ["Melur"]  # Selvi covers Melur, not Peraiyur
    assert client.get("/worklist", headers=vhn).json() and all(
        r["village"] in ("Melur", "Vadipatti", "Usilampatti") for r in client.get("/worklist", headers=vhn).json())

    # She records what happened at the door; she cannot mark a clinical visit done or touch other villages
    ok = client.post(f"/items/{melur['item_id']}/actions",
                     json={"action": "reschedule", "on": "2026-10-07", "note": "met mother, will come Wednesday"},
                     headers=vhn)
    assert ok.status_code == 200 and ok.json()["attempts"][-1]["channel"] == "visit"
    assert client.post(f"/items/{melur['item_id']}/actions", json={"action": "done"}, headers=vhn).status_code == 403
    assert client.post(f"/items/{peraiyur['item_id']}/actions", json={"action": "no_answer"},
                       headers=vhn).status_code == 403
    assert client.get(f"/mothers/{peraiyur['mother_id']}/thread", headers=vhn).status_code == 404
    assert client.get("/field/visits", params={"today": "2026-10-01"}, headers=vhn).json() == []


def test_field_list_never_shows_visits_past_their_catch_up_period(client):
    nurse, vhn = login(client, NURSE), login(client, VHN)
    client.post("/import/anc", files={"file": ("anc.csv", ANC)}, headers=nurse)
    client.post("/import/delivery", files={"file": ("d.csv", DELIVERY)}, headers=nurse)
    rows = client.get("/worklist", params={"today": "2026-10-01"}, headers=nurse).json()
    melur = next(r for r in rows if r["village"] == "Melur" and r["label"] == "PNC day 7")
    client.post(f"/items/{melur['item_id']}/actions", json={"action": "request_visit"}, headers=nurse)
    assert client.get("/field/visits", params={"today": "2026-10-01"}, headers=vhn).json()
    # Months later the day-7 check can no longer happen: it is missed, not a home visit.
    assert client.get("/field/visits", params={"today": "2027-03-01"}, headers=vhn).json() == []
