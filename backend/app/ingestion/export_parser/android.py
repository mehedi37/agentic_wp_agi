import re

from app.ingestion.export_parser.datetime_parse import parse_export_datetime
from app.ingestion.export_parser.types import ParsedMessage, strip_invisible_marks

_LINE_RE = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s(?P<time>\d{1,2}:\d{2}(\s?[APap][Mm])?)\s-\s"
    r"((?P<sender>[^:]+):\s)?(?P<text>.*)$"
)
_MEDIA_OMITTED_RE = re.compile(r"^<Media omitted>$", re.IGNORECASE)


def parse_android(text: str, *, date_order: str, tz: str) -> list[ParsedMessage]:
    messages: list[ParsedMessage] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = strip_invisible_marks(raw_line)
        if not line.strip():
            continue
        m = _LINE_RE.match(line)
        if m is None:
            if messages:
                messages[-1].text += "\n" + line
            continue
        ts = parse_export_datetime(m.group("date"), m.group("time"), date_order=date_order, tz=tz)
        sender = m.group("sender")
        body = m.group("text")
        is_media = bool(_MEDIA_OMITTED_RE.match(body.strip()))
        messages.append(
            ParsedMessage(
                ts=ts,
                sender=sender,
                text="" if is_media else body,
                is_system=sender is None,
                media_type="unknown" if is_media else None,
                line_no=line_no,
            )
        )
    return messages
