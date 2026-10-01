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
