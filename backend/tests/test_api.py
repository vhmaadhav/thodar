from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

from thodar.api.main import app
from thodar.db import get_session, init_db

TODAY = date(2026, 10, 1)

ANC = """RCH ID,Name,Mobile,Village,LMP,ANC1,ANC2,ANC3,ANC4
331234567890,Meena K,9000000001,Melur,01-12-2025,28-01-2026,12-03-2026,,
"""
DELIVERY = """Date,Mother name,Ph no,RCH no,Baby sex,Village
21-09-2026,K. Meena,+91 90000 00001,,F,Melur
"""


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        with Session() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_import_worklist_act_and_thread(client):
    assert client.post("/import/anc", files={"file": ("anc.csv", ANC)}).json()["created"] == 1
    assert client.post("/import/delivery", files={"file": ("del.csv", DELIVERY)}).json()["linked"] == 1

    rows = client.get("/worklist", params={"today": TODAY}).json()
    pnc7 = next(r for r in rows if r["label"] == "PNC day 7")
    assert pnc7["bucket"] == "overdue" and pnc7["days_overdue"] == 3
    assert pnc7["next_step"] == "Send WhatsApp reminder"

    sat = TODAY + timedelta(days=3)
    out = client.post(f"/items/{pnc7['item_id']}/actions",
                      json={"action": "reschedule", "on": sat.isoformat(), "note": "will come Saturday"}).json()
    assert out["rescheduled_to"] == sat.isoformat()

    thread = client.get(f"/mothers/{pnc7['mother_id']}/thread").json()
    preg = thread["pregnancies"][0]
    assert preg["delivery_date"] == "2026-09-21"
    assert any(i["code"] == "uip-6w" for i in preg["babies"][0]["items"])

    m = client.get("/metrics", params={"today": TODAY}).json()
    assert m["open_items"] >= 1


def test_unknown_import_source(client):
    assert client.post("/import/lab", files={"file": ("x.csv", "a\n1\n")}).status_code == 404


def test_whatsapp_webhook_and_voice_tools(client):
    client.post("/import/anc", files={"file": ("anc.csv", ANC)})
    client.post("/import/delivery", files={"file": ("del.csv", DELIVERY)})

    # Verification handshake
    r = client.get("/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "thodar-dev",
                                                 "hub.challenge": "42"})
    assert r.text == "42"

    # Voice agent: no key, no access
    assert client.post("/voice/tools/lookup", json={"phone": "9000000001"}).status_code == 401
    h = {"X-Thodar-Tool-Key": "thodar-dev-tool-key"}
    due = client.post("/voice/tools/lookup", json={"phone": "+91 90000 00001", "today": str(TODAY)},
                      headers=h).json()
    assert due["found"] and due["due"]["item_id"]
    sat = (TODAY + timedelta(days=2)).isoformat()
    assert client.post("/voice/tools/update", json={"item_id": due["due"]["item_id"], "outcome": "reschedule",
                                                    "new_date": sat, "note": "will come Saturday"},
                       headers=h).json()["ok"]

    # Family texts in with a symptom: routed to staff
    body = {"entry": [{"changes": [{"value": {"messages": [
        {"from": "919000000001", "type": "text", "text": {"body": "baby has fever"}}]}}]}]}
    handled = client.post("/webhooks/whatsapp", params={"today": str(TODAY)}, json=body).json()["handled"]
    assert handled[0]["intent"] == "needs_staff"


def test_photo_import_needs_sarvam_key_and_rows_import_works(client, monkeypatch):
    monkeypatch.setattr("thodar.messaging.sarvam.get_settings", lambda: type("S", (), {
        "sarvam_api_key": "", "sarvam_base_url": "https://api.sarvam.ai"})())
    r = client.post("/import/anc/photo", files={"file": ("page.jpg", b"fake")})
    assert r.status_code == 501

    rows = [{"RCH ID": None, "Name": "Revathi S", "Mobile": "9000000099", "Village": "Melur", "LMP": "01-06-2026"}]
    assert client.post("/import/anc/rows", json=rows).json()["created"] == 1


def test_consent_language_and_phone(client):
    client.post("/import/anc", files={"file": ("anc.csv", ANC)})
    assert client.get("/mothers/1/thread").json()["consent_at"] is None
    out = client.patch("/mothers/1", json={"consent": True, "language": "en", "phone": "+91 98400 12345"}).json()
    assert out["consent_at"] and out["language"] == "en" and out["phone"] == "9840012345"
    out = client.patch("/mothers/1", json={"consent": False}).json()
    assert out["opted_out"] and out["consent_at"] is None
    assert client.patch("/mothers/1", json={"phone": "123"}).status_code == 422


def test_family_contact_can_be_set_and_cleared(client):
    client.post("/import/anc", files={"file": ("anc.csv", ANC)})
    out = client.patch("/mothers/1", json={"family_phone": "90000 00999", "family_relation": "husband"}).json()
    assert out["family_phone"] == "9000000999" and out["family_relation"] == "husband"
    assert client.get("/mothers/1/thread").json()["family_relation"] == "husband"
    assert client.patch("/mothers/1", json={"family_phone": ""}).json()["family_phone"] is None


def test_unknown_number_lands_in_inbox_and_can_be_attached(client):
    client.post("/import/anc", files={"file": ("anc.csv", ANC)})
    body = {"entry": [{"changes": [{"value": {"messages": [
        {"from": "919000000777", "type": "text", "text": {"body": "this is Meena's husband, new number"}}]}}]}]}
    assert client.post("/webhooks/whatsapp", json=body).json()["handled"][0]["reason"] == "unknown number"
    inbox = client.get("/inbox").json()
    assert inbox[0]["phone"] == "9000000777" and "husband" in inbox[0]["text"]

    out = client.post(f"/inbox/{inbox[0]['id']}/attach", json={"mother_id": 1, "as": "family"}).json()
    assert out["family_phone"] == "9000000777"
    assert client.get("/inbox").json() == []
    # The next message from that number is now understood as this family's.
    body["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"] = "STOP"
    assert client.post("/webhooks/whatsapp", json=body).json()["handled"][0]["intent"] == "stop"


def test_brought_back_into_care_metric(client):
    client.post("/import/anc", files={"file": ("anc.csv", ANC)})
    client.post("/import/delivery", files={"file": ("del.csv", DELIVERY)})
    row = next(r for r in client.get("/worklist", params={"today": TODAY}).json() if r["label"] == "PNC day 7")
    client.post(f"/items/{row['item_id']}/actions", json={"action": "request_visit"})  # Thodar follows up
    # ...then it happens. Use the real date: the follow-up above is timestamped with the real clock.
    client.post(f"/items/{row['item_id']}/actions", json={"action": "done", "on": str(date.today())})
    m = client.get("/metrics", params={"today": date.today()}).json()
    assert m["brought_back_visits"] == 1 and m["brought_back_families"] == 1


def test_export_and_erasure(client):
    client.post("/import/anc", files={"file": ("anc.csv", ANC)})
    client.post("/import/delivery", files={"file": ("del.csv", DELIVERY)})
    data = client.get("/mothers/1/export").json()
    assert data["mother"]["name"] == "Meena K" and data["visits"] and data["pregnancies"][0]["babies"]

    assert client.post("/mothers/1/erase", json={"confirm_name": "wrong"}).status_code == 422
    out = client.post("/mothers/1/erase", json={"confirm_name": "meena k"}).json()
    assert out["erased"] and out["records_deleted"] > 10
    assert client.get("/mothers/1/thread").status_code == 404
    assert client.get("/worklist", params={"today": TODAY}).json() == []


def test_ai_budget_caps_paid_calls(monkeypatch):
    import pytest
    from fastapi import HTTPException

    from thodar import ai_budget
    monkeypatch.setenv("THODAR_AI_DAILY_BUDGET", "2")
    from thodar.config import get_settings
    get_settings.cache_clear()
    ai_budget.reset()
    ai_budget.spend("x")
    ai_budget.spend("x")
    with pytest.raises(HTTPException):
        ai_budget.spend("x")
    ai_budget.reset()
