import re

from app.ingestion.export_parser.types import strip_invisible_marks

_ANDROID_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4},\s\d{1,2}:\d{2}(\s?[APap][Mm])?\s-\s")
_IOS_RE = re.compile(r"^\[\d{1,2}/\d{1,2}/\d{2,4},\s\d{1,2}:\d{2}:\d{2}(\s?[APap][Mm])?\]\s")


class UnrecognizedFormatError(ValueError):
    pass


def detect_format(text: str) -> str:
    for raw_line in text.splitlines():
        line = strip_invisible_marks(raw_line).strip()
        if not line:
            continue
        if _IOS_RE.match(line):
            return "ios"
        if _ANDROID_RE.match(line):
            return "android"
        raise UnrecognizedFormatError(f"first non-empty line does not match any known export format: {line!r}")
    raise UnrecognizedFormatError("empty export text")
