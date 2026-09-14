from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.ingestion.export_parser.datetime_parse import parse_export_datetime

TZ = "Asia/Dhaka"


def test_dmy_24h():
    dt = parse_export_datetime("12/03/2026", "14:30", date_order="DMY", tz=TZ)
    assert dt == datetime(2026, 3, 12, 14, 30, tzinfo=ZoneInfo(TZ))


def test_mdy_12h_pm():
    dt = parse_export_datetime("3/12/2026", "2:30 PM", date_order="MDY", tz=TZ)
    assert dt == datetime(2026, 3, 12, 14, 30, tzinfo=ZoneInfo(TZ))


def test_12h_with_seconds():
    dt = parse_export_datetime("12/03/26", "09:41:03 AM", date_order="DMY", tz=TZ)
    assert dt == datetime(2026, 3, 12, 9, 41, 3, tzinfo=ZoneInfo(TZ))


def test_2digit_year_pivots_to_2000s():
    dt = parse_export_datetime("1/1/24", "00:00", date_order="DMY", tz=TZ)
    assert dt.year == 2024


def test_unambiguous_day_over_12_overrides_configured_order():
    # 25 cannot be a month: must be day=25 regardless of date_order="MDY"
    dt = parse_export_datetime("25/03/2026", "10:00", date_order="MDY", tz=TZ)
    assert (dt.day, dt.month) == (25, 3)


def test_noon_and_midnight_12h():
    assert parse_export_datetime("1/1/2026", "12:00 AM", date_order="DMY", tz=TZ).hour == 0
    assert parse_export_datetime("1/1/2026", "12:00 PM", date_order="DMY", tz=TZ).hour == 12


def test_invalid_raises():
    with pytest.raises(ValueError):
        parse_export_datetime("31/02/2026", "10:00", date_order="DMY", tz=TZ)
