from datetime import date

from thodar import normalize
from thodar.linking import Candidate, best_link, score


def test_normalize_handles_register_quirks():
    assert normalize.name("R. Kavitha") == normalize.name("Kavitha R") == "kavitha"
    assert normalize.name("Baby of Meena K.") == "meena"
    assert normalize.phone("+91 98400-12345") == "9840012345"
    assert normalize.phone("12345") is None
    assert normalize.rch_id("1234 5678 9012") == "123456789012"


def test_same_rch_id_is_a_match():
    a = Candidate(1, "Kavitha R", None, "123456789012", None)
    b = Candidate(2, "K. Kavita", "9840012345", "123456789012", None)
    link = score(b, a)
    assert link.decision == "match" and link.reason == "same RCH ID"


def test_phone_plus_similar_name_is_a_match():
    known = Candidate(1, "Meena K", "9840012345", None, None, lmp=date(2025, 12, 1))
    row = Candidate(0, "K. Meena", "9840012345", None, None)
    link = best_link(row, [known], event_date=date(2026, 9, 1))
    assert link and link.decision == "match"
    assert "same phone" in link.reason


def test_similar_name_without_phone_goes_to_review_not_merge():
    known = Candidate(1, "Anitha M", "9840012345", None, None, village="Melur")
    row = Candidate(0, "Anita M", None, None, None, village="Melur")
    link = best_link(row, [known])
    assert link and link.decision == "review"


def test_different_rch_ids_never_match():
    a = Candidate(1, "Priya S", "9840012345", "111111111111", None)
    b = Candidate(0, "Priya S", "9840012345", "222222222222", None)
    assert score(b, a).decision == "new"
