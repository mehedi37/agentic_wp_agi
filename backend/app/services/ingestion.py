import hashlib
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IngestionJob, Message
from app.ingestion.export_parser.android import parse_android
from app.ingestion.export_parser.detect import detect_format
from app.ingestion.export_parser.ios import parse_ios
from app.ingestion.export_parser.types import ParsedMessage
from app.ingestion.export_parser.zip_loader import load_export_bytes
from app.services.participants import get_or_create_participant


@dataclass
class IngestStats:
    job: IngestionJob
    inserted: int
    duplicates: int
    unparsed_lines: int


def _content_hash(chat_id: uuid.UUID, msg: ParsedMessage) -> str:
    return hashlib.sha256(f"{chat_id}|{msg.ts.isoformat()}|{msg.sender}|{msg.text}".encode()).hexdigest()


async def ingest_export(
    session: Session,
    *,
    chat_id: uuid.UUID,
    filename: str,
    file_bytes: bytes,
    date_order: str = "DMY",
    tz: str = "Asia/Dhaka",
    enqueue: Callable[[uuid.UUID], Awaitable[None]] | None = None,
) -> IngestStats:
    job = IngestionJob(source="export", filename=filename, status="processing")
    session.add(job)
    session.flush()

    chat_text, _media_names = load_export_bytes(file_bytes, filename=filename)
    fmt = detect_format(chat_text)
    parsed = parse_android(chat_text, date_order=date_order, tz=tz) if fmt == "android" \
        else parse_ios(chat_text, date_order=date_order, tz=tz)

    inserted = 0
    duplicates = 0
    for msg in parsed:
        content_hash = _content_hash(chat_id, msg)
        exists = session.scalar(select(Message.id).where(Message.content_hash == content_hash))
        if exists is not None:
            duplicates += 1
            continue
        participant = None
        if msg.sender is not None:
            participant = get_or_create_participant(session, chat_id, msg.sender)
        session.add(
            Message(
                chat_id=chat_id,
                participant_id=participant.id if participant else None,
                ts=msg.ts,
                text=msg.text,
                media_type=msg.media_type,
                is_system=msg.is_system,
                content_hash=content_hash,
            )
        )
        inserted += 1

    job.status = "completed"
    job.stats = {"inserted": inserted, "duplicates": duplicates, "unparsed_lines": 0}
    session.flush()

    if enqueue is not None and inserted > 0:
        await enqueue(chat_id)

    return IngestStats(job=job, inserted=inserted, duplicates=duplicates, unparsed_lines=0)
