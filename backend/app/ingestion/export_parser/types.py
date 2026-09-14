from dataclasses import dataclass
from datetime import datetime


@dataclass
class ParsedMessage:
    ts: datetime  # tz-aware, in the chat's timezone
    sender: str | None  # None for system messages
    text: str
    is_system: bool
    media_type: str | None  # "image" | "video" | "audio" | "document" | "sticker" | "gif" | None
    line_no: int  # 1-based line where this message started, for unparsed-line reporting


def strip_invisible_marks(text: str) -> str:
    return text.replace("‎", "").replace(" ", " ")
