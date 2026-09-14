from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.models import Chat
from app.db.session import get_session
from app.ingestion.export_parser.detect import UnrecognizedFormatError
from app.ingestion.export_parser.zip_loader import NoChatFileError
from app.schemas.auth import CurrentUser
from app.schemas.ingestion import IngestResponse
from app.services.ingestion import ingest_export
from app.workers.queue import enqueue_process_batch

router = APIRouter(prefix="/ingest", tags=["ingestion"])

_require_analyst_or_manager = require_role("analyst", "manager")


@router.post("/upload", response_model=IngestResponse)
async def upload_export(
    file: UploadFile = File(...),
    chat_name: str = Form(...),
    date_order: str = Form("DMY"),
    _user: CurrentUser = Depends(_require_analyst_or_manager),
    session: Session = Depends(get_session),
) -> IngestResponse:
    if date_order not in ("DMY", "MDY") or not chat_name.strip():
        raise HTTPException(status_code=422, detail="Provide a chat name and DMY or MDY date order")
    chat = session.scalar(select(Chat).where(Chat.name == chat_name.strip(), Chat.source == "export"))
    if chat is None:
        chat = Chat(source="export", name=chat_name.strip(), type="group", timezone="Asia/Dhaka")
        session.add(chat)
        session.flush()

    file_bytes = await file.read()
    try:
        stats = await ingest_export(
            session,
            chat_id=chat.id,
            filename=file.filename or "upload",
            file_bytes=file_bytes,
            date_order=date_order,
        )
    except (UnrecognizedFormatError, NoChatFileError) as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    session.commit()
    if stats.inserted:
        try:
            await enqueue_process_batch(chat.id)
        except (RedisError, OSError, TimeoutError):
            stats.job.status = "queue_failed"
            stats.job.error = "Messages saved; processing queue unavailable. Retry processing."
            session.commit()
    return IngestResponse(
        job_id=stats.job.id,
        chat_id=chat.id,
        status=stats.job.status,
        inserted=stats.inserted,
        duplicates=stats.duplicates,
        unparsed_lines=stats.unparsed_lines,
    )
