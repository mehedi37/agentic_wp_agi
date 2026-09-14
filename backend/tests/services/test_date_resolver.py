from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.date_resolver import resolve_date

TZ = "Asia/Dhaka"
ANCHOR = datetime(2026, 1, 5, 10, 0, tzinfo=ZoneInfo(TZ))  # a Monday


def test_today_english():
    assert resolve_date("today", anchor_ts=ANCHOR, tz=TZ).date() == ANCHOR.date()


def test_kal_is_tomorrow():
    result = resolve_date("kal", anchor_ts=ANCHOR, tz=TZ)
    assert result.date() == ANCHOR.date().replace(day=6)


def test_porshu_is_day_after_tomorrow():
    result = resolve_date("porshu", anchor_ts=ANCHOR, tz=TZ)
    assert result.date() == ANCHOR.date().replace(day=7)


def test_next_friday():
    result = resolve_date("next Friday", anchor_ts=ANCHOR, tz=TZ)
    assert result.weekday() == 4
    assert result.date() > ANCHOR.date()


def test_eod_means_end_of_anchor_day():
    result = resolve_date("EOD", anchor_ts=ANCHOR, tz=TZ)
    assert result.date() == ANCHOR.date()
    assert (result.hour, result.minute) == (23, 59)


def test_by_15th_resolves_within_current_month():
    result = resolve_date("by 15th", anchor_ts=ANCHOR, tz=TZ)
    assert (result.year, result.month, result.day) == (2026, 1, 15)


def test_by_ordinal_already_passed_rolls_to_next_month():
    result = resolve_date("by 2nd", anchor_ts=ANCHOR, tz=TZ)
    assert (result.year, result.month, result.day) == (2026, 2, 2)


def test_unresolvable_returns_none():
    assert resolve_date("sometime probably maybe", anchor_ts=ANCHOR, tz=TZ) is None


def test_explicit_dmy_date():
    result = resolve_date("15/03/2026", anchor_ts=ANCHOR, tz=TZ)
    assert (result.year, result.month, result.day) == (2026, 3, 15)


def test_never_resolves_before_anchor_date_for_relative_terms():
    result = resolve_date("this Monday", anchor_ts=ANCHOR, tz=TZ)
    assert result.date() == ANCHOR.date()
