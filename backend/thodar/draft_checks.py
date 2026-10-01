"""Flags cells in a photo-read draft that a nurse should look at twice before importing.

OCR is good but not perfect on crowded handwriting (in live testing Sarvam Vision read a
'02-04-26' that overlapped the next column as '04-21-26'). These checks are clerical, not clinical:
impossible or partial dates, malformed phone numbers and IDs, visits out of order.
"""

import re
from datetime import date

from thodar import normalize

DATE_COLS = {"LMP", "ANC1", "ANC2", "ANC3", "ANC4", "Date", "DOB", "Birth", "6 wk", "10 wk", "14 wk", "9 mo", "16 mo",
             "PNC 48h", "PNC D3", "PNC D7", "PNC 6wk", "Newborn 48h", "Newborn D7"}
PHONE_COLS = {"Mobile", "Ph no", "Mother mobile"}
RCH_COLS = {"RCH ID", "RCH no"}
SEQUENCES = [["LMP", "ANC1", "ANC2", "ANC3", "ANC4"], ["DOB", "Birth", "6 wk", "10 wk", "14 wk", "9 mo", "16 mo"]]
_DMY = re.compile(r"^\s*(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})\s*$")


def parse_dmy(value: str) -> date | None:
    m = _DMY.match(value or "")
    if not m:
        return None
    d, mo, y = (int(g) for g in m.groups())
    y = y + 2000 if y < 100 else y
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def check_rows(rows: list[dict], today: date | None = None) -> dict[int, dict[str, str]]:
    today = today or date.today()
    issues: dict[int, dict[str, str]] = {}
    for i, row in enumerate(rows):
        bad: dict[str, str] = {}
        for col, value in row.items():
            if not value:
                continue
            if col in DATE_COLS:
                d = parse_dmy(str(value))
                if d is None:
                    bad[col] = "not a full DD-MM-YYYY date"
                elif d > today:
                    bad[col] = "date is in the future"
                elif d.year < today.year - 3:
                    bad[col] = "date looks too old"
            elif col in PHONE_COLS and not normalize.phone(value):
                bad[col] = "not a 10-digit mobile number"
            elif col in RCH_COLS and not normalize.rch_id(value):
                bad[col] = "RCH ID should be 12 digits"
        for seq in SEQUENCES:
            prev_col, prev = None, None
            for col in seq:
                d = parse_dmy(str(row.get(col) or ""))
                if d is None or col in bad:
                    continue
                if prev and d < prev:
                    bad[col] = f"earlier than {prev_col}"
                prev_col, prev = col, d
        if bad:
            issues[i] = bad
    return issues
