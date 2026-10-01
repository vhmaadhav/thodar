import pandas as pd
from sqlalchemy import select

from thodar.importer import import_anc_register, import_delivery_register, import_immunisation_register
from thodar.models import Baby, ItemStatus, LinkReview, Mother, ScheduleItem


def _df(rows):
    return pd.DataFrame(rows, dtype=str).where(lambda d: d.notna(), None)


def test_three_registers_become_one_thread(session):
    import_anc_register(session, _df([{
        "RCH ID": "331234567890", "Name": "Meena K", "Mobile": "9000000001", "Village": "Melur",
        "LMP": "01-12-2025", "ANC1": "28-01-2026", "ANC2": "12-03-2026", "ANC3": None, "ANC4": None,
    }]))
    report = import_delivery_register(session, _df([{
        "Date": "05-09-2026", "Mother name": "K. Meena", "Ph no": "+91 90000 00001", "RCH no": None,
        "Baby sex": "F", "Village": "Melur",
    }]))
    assert report.linked == 1 and report.created == 0

    imm = import_immunisation_register(session, _df([{
        "Child name": "B/O Meena K", "DOB": "05-09-2026", "Mother mobile": "9000000001",
        "Birth": "05-09-2026", "6 wk": None,
    }]))
    assert imm.linked == 1

    mother = session.scalars(select(Mother)).one()
    baby = session.scalars(select(Baby)).one()
    items = {i.code: i for i in session.scalars(select(ScheduleItem))}

    assert baby.pregnancy.mother_id == mother.id
    assert items["anc-1"].status is ItemStatus.done
    assert items["anc-3"].status is ItemStatus.pending  # missed, still visible
    assert "pnc-d7" in items and items["uip-birth"].status is ItemStatus.done
    assert items["uip-6w"].baby_id == baby.id and items["uip-6w"].owner == "paediatrics"


def test_ambiguous_row_goes_to_review(session):
    import_anc_register(session, _df([{
        "RCH ID": None, "Name": "Anitha M", "Mobile": "9000000002", "Village": "Melur",
        "LMP": "01-12-2025",
    }]))
    report = import_delivery_register(session, _df([{
        "Date": "05-09-2026", "Mother name": "Anita M", "Ph no": None, "RCH no": None, "Village": "Peraiyur",
    }]))
    assert report.sent_to_review == 1
    assert session.scalars(select(LinkReview)).one().candidate_mother_id == 1
