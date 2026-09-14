import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Chat, Message
from app.db.session import get_session
from app.schemas.auth import CurrentUser
from app.schemas.chat import ChatOut
from app.schemas.message import MessageOut

router = APIRouter(prefix="/chats", tags=["chats"])


@router.get("", response_model=list[ChatOut])
def list_chats(
    _user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)
) -> list[Chat]:
    return list(session.scalars(select(Chat).order_by(Chat.created_at.desc())))


@router.get("/{chat_id}/messages", response_model=list[MessageOut])
def list_chat_messages(
    chat_id: uuid.UUID,
    limit: int = 200,
    _user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Message]:
    query = select(Message).where(Message.chat_id == chat_id).order_by(Message.ts).limit(limit)
    return list(session.scalars(query))
