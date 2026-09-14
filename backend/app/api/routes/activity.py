import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import AgentRun, Chat, IngestionJob, ItemEvidence, Message
from app.db.session import get_session
from app.schemas.auth import CurrentUser
from app.workers.queue import enqueue_process_batch

router = APIRouter(tags=["activity"], dependencies=[Depends(get_current_user)])
_limit = Query(100, ge=1, le=500)


@router.get("/agent-runs")
def agent_runs(limit: int = _limit, session: Session = Depends(get_session)) -> list[dict]:
    return [jsonable_encoder(row) for row in session.scalars(
        select(AgentRun).order_by(AgentRun.ts.desc()).limit(limit)
    )]


@router.get("/ingest/jobs")
def jobs(session: Session = Depends(get_session)) -> list[dict]:
    return [jsonable_encoder(row) for row in session.scalars(
        select(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(100)
    )]


@router.get("/items/{item_id}/evidence")
def evidence(item_id: uuid.UUID, session: Session = Depends(get_session)) -> list[dict]:
    rows = session.execute(select(ItemEvidence, Message).join(
        Message, ItemEvidence.message_id == Message.id
    ).where(ItemEvidence.item_id == item_id))
    return [{"message_id": str(message.id), "chat_id": str(message.chat_id),
             "quote": ref.quote, "text": message.text, "ts": message.ts.isoformat()}
            for ref, message in rows]


@router.get("/messages/{message_id}")
def message(message_id: uuid.UUID, session: Session = Depends(get_session)) -> dict:
    row = session.get(Message, message_id)
    if row is None:
        raise HTTPException(404, "Message not found")
    return {"id": str(row.id), "chat_id": str(row.chat_id), "text": row.text,
            "ts": row.ts.isoformat()}


@router.post("/chats/{chat_id}/process")
async def process(chat_id: uuid.UUID, _user: CurrentUser = Depends(get_current_user),
                  session: Session = Depends(get_session)) -> dict:
    if session.get(Chat, chat_id) is None:
        raise HTTPException(404, "Chat not found")
    await enqueue_process_batch(chat_id)
    return {"status": "queued"}
