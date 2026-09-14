import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
    "sombar": 0, "mongolbar": 1, "budhbar": 2, "brihoshpotibar": 3, "shukrobar": 4,
    "shonibar": 5, "robibar": 6,
}
_RELATIVE_DAYS = {
    "today": 0, "aj": 0, "ajke": 0, "ajk": 0,
    "tomorrow": 1, "kal": 1, "agamikal": 1,
    "day after tomorrow": 2, "porshu": 2, "parsu": 2,
}
_EOD_RE = re.compile(r"^(eod|end of day)$")
_BY_ORDINAL_RE = re.compile(r"^by(\sthe)?\s(?P<day>\d{1,2})(st|nd|rd|th)?$")
_EXPLICIT_DATE_RE = re.compile(r"^(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{2,4})$")
_WEEKDAY_PHRASE_RE = re.compile(r"^(this|next)?\s?(?P<weekday>[a-z]+)$")


def _pivot_year(year: int) -> int:
    return 2000 + year if year < 100 else year


def resolve_date(raw: str, *, anchor_ts: datetime, tz: str = "Asia/Dhaka") -> datetime | None:
    """Deterministic relative/explicit date resolution (PLAN.md §6.2's
    `resolve_date` tool). Returns `None` -- never a guessed date -- when the
    text doesn't match a known pattern; the caller must treat `None` as
    "keep due_date_raw, leave due_at unset", never invent a date."""
    zone = ZoneInfo(tz)
    anchor = anchor_ts.astimezone(zone)
    text = raw.strip().lower()

    if text in _RELATIVE_DAYS:
        target = anchor.date() + timedelta(days=_RELATIVE_DAYS[text])
        return datetime(target.year, target.month, target.day, 23, 59, tzinfo=zone)

    if _EOD_RE.match(text):
        return datetime(anchor.year, anchor.month, anchor.day, 23, 59, tzinfo=zone)

    m = _BY_ORDINAL_RE.match(text)
    if m:
        day = int(m.group("day"))
        year, month = anchor.year, anchor.month
        if day < anchor.day:
            month += 1
            if month > 12:
                month, year = 1, year + 1
        try:
            return datetime(year, month, day, 23, 59, tzinfo=zone)
        except ValueError:
            return None

    m = _EXPLICIT_DATE_RE.match(text)
    if m:
        day, month, year = int(m.group("d")), int(m.group("m")), _pivot_year(int(m.group("y")))
        try:
            return datetime(year, month, day, 23, 59, tzinfo=zone)
        except ValueError:
            return None

    m = _WEEKDAY_PHRASE_RE.match(text)
    if m and m.group("weekday") in _WEEKDAYS:
        target_weekday = _WEEKDAYS[m.group("weekday")]
        qualifier = m.group(1)
        days_ahead = (target_weekday - anchor.weekday()) % 7
        if qualifier == "next" and days_ahead == 0:
            days_ahead = 7
        elif qualifier == "next":
            days_ahead += 7
        target = anchor.date() + timedelta(days=days_ahead)
        return datetime(target.year, target.month, target.day, 23, 59, tzinfo=zone)

    return None
