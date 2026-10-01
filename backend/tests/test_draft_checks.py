from datetime import date

from thodar.draft_checks import check_rows

TODAY = date(2026, 10, 1)


def test_flags_what_ocr_got_wrong_in_live_test():
    # Row 3 as Sarvam Vision read it from our test page (true values: 02-04-26, 10-07-26, 01-09-26)
    row = {"RCH ID": "339876543210", "Name": "S. Priya", "Mobile": "9789012233", "LMP": "20-12-2025",
           "ANC1": "14-02-2026", "ANC2": "04-21-26", "ANC3": "07-2026", "ANC4": "09-2026"}
    issues = check_rows([row], TODAY)[0]
    assert set(issues) == {"ANC2", "ANC3", "ANC4"}
    assert "Name" not in issues and "Mobile" not in issues


def test_clean_rows_pass_and_order_is_checked():
    good = {"RCH ID": "331234567890", "Mobile": "9840012345", "LMP": "03-02-2026", "ANC1": "30-03-26"}
    assert check_rows([good], TODAY) == {}
    swapped = {"LMP": "03-02-2026", "ANC1": "15-05-26", "ANC2": "30-03-26", "Mobile": "12345"}
    issues = check_rows([swapped], TODAY)[0]
    assert issues["ANC2"] == "earlier than ANC1" and "Mobile" in issues
