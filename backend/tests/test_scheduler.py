from datetime import datetime, time

from thodar.scheduler import IST, parse_hhmm, seconds_until


def test_parse_and_next_run():
    assert parse_hhmm("09:00") == time(9, 0) and parse_hhmm("") is None and parse_hhmm("9am") is None
    now = datetime(2026, 10, 1, 8, 30, tzinfo=IST)
    assert seconds_until(time(9, 0), now) == 30 * 60
    assert seconds_until(time(8, 0), now) == 23.5 * 3600  # already past today: tomorrow
