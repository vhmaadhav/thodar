"""Loads the synthetic registers into a fresh database.

    uv run python scripts/generate_synthetic.py
    uv run python scripts/seed_demo.py --data ../data/generated
"""

import argparse
from datetime import datetime
from pathlib import Path

from sqlalchemy import update

from thodar.db import Base, SessionLocal, engine, init_db
from datetime import date

from sqlalchemy import select

from thodar.api.auth_routes import ensure_demo_staff
from thodar.auth import Actor, audit
from thodar.models import Mother, Role, Staff
from thodar.schedule_engine import expire_items
from thodar.worklist import Action, build_worklist, record_action
from thodar.importer import (
    import_anc_register,
    import_delivery_register,
    import_immunisation_register,
    read_table,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../data/generated")
    args = ap.parse_args()
    data = Path(args.data)

    Base.metadata.drop_all(engine)
    init_db()
    with SessionLocal() as s:
        for fn, path in [
            (import_anc_register, data / "anc_register.csv"),
            (import_delivery_register, data / "delivery_register.csv"),
            (import_immunisation_register, data / "immunisation_register.csv"),
        ]:
            r = fn(s, read_table(path))
            print(f"{r.source}: {r.rows} rows, {r.created} new, {r.linked} linked, "
                  f"{r.sent_to_review} to review, {len(r.skipped)} skipped")
        # Synthetic families: record consent so the reminder flow can be demonstrated end to end.
        s.execute(update(Mother).values(consent_at=datetime.now()))
        s.commit()

        # Demo staff (PINs shown on the sign-in page in demo mode) and a few home visits the nurse
        # has asked the village health nurse to make, so field mode has something to show.
        ensure_demo_staff(s)
        nurse = s.scalars(select(Staff).where(Staff.role == Role.nurse)).first()
        actor = Actor(nurse.id, nurse.name, nurse.role, [])
        today = date.today()
        expire_items(s, today)
        requested = 0
        for row in build_worklist(s, today, horizon_days=0):
            if requested >= 6:
                break
            if (row.mother.village or "") in ("Melur", "Vadipatti", "Usilampatti") and row.days_overdue > 7:
                record_action(s, row.item, Action.request_visit, actor=nurse.name,
                              note="2 calls unanswered; please visit")
                audit(s, actor, "visit_request_visit", "item", row.item.id)
                requested += 1
        s.commit()
        print(f"demo staff ready; {requested} home visits requested for the VHN")


if __name__ == "__main__":
    main()
