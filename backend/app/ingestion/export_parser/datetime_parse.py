import re
from datetime import datetime
from zoneinfo import ZoneInfo

_TIME_RE = re.compile(
    r"^(?P<h>\d{1,2}):(?P<m>\d{2})(:(?P<s>\d{2}))?\s?(?P<ampm>[APap][Mm])?$"
)


def _pivot_year(year: int) -> int:
    return 2000 + year if year < 100 else year


def parse_export_datetime(date_str: str, time_str: str, *, date_order: str, tz: str) -> datetime:
    """`date_order` is "DMY" or "MDY" and is only a tie-breaker: if one part
    of the date is unambiguously > 12 it is treated as the day regardless
    of the configured order (handles exports where the configured order
    was guessed wrong but the data itself resolves the ambiguity)."""
    d1_str, d2_str, y_str = date_str.split("/")
    d1, d2, year = int(d1_str), int(d2_str), _pivot_year(int(y_str))

    if d1 > 12 and d2 <= 12:
        day, month = d1, d2
    elif d2 > 12 and d1 <= 12:
        day, month = d2, d1
    elif date_order == "MDY":
        month, day = d1, d2
    else:
        day, month = d1, d2

    m = _TIME_RE.match(time_str.strip())
    if not m:
        raise ValueError(f"unrecognized time: {time_str!r}")
    hour, minute = int(m.group("h")), int(m.group("m"))
    second = int(m.group("s") or 0)
    ampm = (m.group("ampm") or "").lower()
    if ampm == "am":
        hour = 0 if hour == 12 else hour
    elif ampm == "pm":
        hour = 12 if hour == 12 else hour + 12

    return datetime(year, month, day, hour, minute, second, tzinfo=ZoneInfo(tz))
