"""Loads the synthetic registers into a fresh database.

    uv run python scripts/generate_synthetic.py
    uv run python scripts/seed_demo.py --data ../data/generated
"""

import argparse
from datetime import datetime
from pathlib import Path

from sqlalchemy import update

from thodar.db import Base, SessionLocal, engine, init_db
from thodar.models import Mother
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


if __name__ == "__main__":
    main()
