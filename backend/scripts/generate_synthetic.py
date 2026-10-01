"""Generates three deliberately messy, fully synthetic registers for demos and tests.

No real people: names are drawn from a list of common given names, phone numbers use the
reserved-looking 9000xxxxxx range, and RCH IDs are random.

    uv run python scripts/generate_synthetic.py --out ../data/generated --mothers 80
"""

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

GIVEN = ["Kavitha", "Meena", "Priya", "Anitha", "Lakshmi", "Divya", "Revathi", "Sangeetha", "Nandhini",
         "Saranya", "Deepa", "Gayathri", "Jayanthi", "Keerthana", "Malathi", "Pavithra", "Radhika",
         "Selvi", "Sumathi", "Vidhya", "Bhuvana", "Indhu", "Kalaivani", "Mahalakshmi", "Nithya", "Shalini"]
INITIALS = list("ARKMSVPTDGN")
VILLAGES = ["Melur", "Thiruparankundram", "Vadipatti", "Usilampatti", "Peraiyur", "Kottampatti", "Madurai Urban"]

ANC_DAYS = [56, 98, 196, 252]
UIP = [("Birth", 0), ("6 wk", 42), ("10 wk", 70), ("14 wk", 98), ("9 mo", 270), ("16 mo", 487)]


def fmt(d: date | None) -> str:
    return d.strftime("%d-%m-%Y") if d else ""


def messy_phone(phone: str, rng: random.Random) -> str:
    style = rng.random()
    if style < 0.1:
        return ""
    if style < 0.35:
        return f"+91 {phone[:5]} {phone[5:]}"
    if style < 0.5:
        return f"{phone[:5]}-{phone[5:]}"
    return phone


def messy_name(given: str, initial: str, rng: random.Random) -> str:
    r = rng.random()
    if r < 0.4:
        return f"{initial}. {given}"
    if r < 0.5:  # a typo, as in handwritten registers
        i = rng.randrange(1, len(given) - 1)
        return f"{given[:i]}{given[i + 1:]} {initial}"
    return f"{given} {initial}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../data/generated")
    ap.add_argument("--mothers", type=int, default=80)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--today", default=None, help="dd-mm-yyyy; defaults to today")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    today = date.today() if not args.today else date(*reversed([int(x) for x in args.today.split("-")]))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    anc_rows, delivery_rows, imm_rows = [], [], []
    for i in range(args.mothers):
        given, initial = rng.choice(GIVEN), rng.choice(INITIALS)
        canonical = f"{given} {initial}"
        phone = f"9000{i:06d}"
        rch = f"33{rng.randrange(10**9, 10**10)}"
        village = rng.choice(VILLAGES)
        lmp = today - timedelta(days=rng.randint(60, 700))
        walk_in = rng.random() < 0.06  # delivered here, ANC elsewhere

        if not walk_in:
            visits = []
            for n, offset in enumerate(ANC_DAYS):
                due = lmp + timedelta(days=offset)
                attended = due < today - timedelta(days=3) and rng.random() < (0.97 - 0.1 * n)
                visits.append(fmt(due + timedelta(days=rng.randint(0, 12))) if attended else "")
            anc_rows.append({"RCH ID": rch, "Name": canonical, "Mobile": phone, "Village": village,
                             "LMP": fmt(lmp), **{f"ANC{n + 1}": v for n, v in enumerate(visits)}})

        delivered = lmp + timedelta(days=rng.randint(252, 287))
        if delivered >= today:
            continue
        delivery_rows.append({
            "Date": fmt(delivered),
            "Mother name": messy_name(given, initial, rng),
            "Ph no": messy_phone(phone, rng),
            "RCH no": rch if rng.random() < 0.7 else "",
            "Baby sex": rng.choice("MF"),
            "Village": village,
        })

        doses = {}
        for n, (col, offset) in enumerate(UIP):
            due = delivered + timedelta(days=offset)
            given_dose = due < today - timedelta(days=5) and rng.random() < (0.98 - 0.07 * n)
            doses[col] = fmt(due + timedelta(days=rng.randint(0, 20))) if given_dose else ""
        if any(doses.values()):
            prefix = rng.choice(["Baby of", "B/O", "Baby of"])
            imm_rows.append({"Child name": f"{prefix} {messy_name(given, initial, rng)}", "DOB": fmt(delivered),
                             "Mother mobile": messy_phone(phone, rng), **doses})

    for name, rows in [("anc_register.csv", anc_rows), ("delivery_register.csv", delivery_rows),
                       ("immunisation_register.csv", imm_rows)]:
        with open(out / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"{name}: {len(rows)} rows")


if __name__ == "__main__":
    main()
