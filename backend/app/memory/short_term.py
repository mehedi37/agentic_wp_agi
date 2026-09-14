import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import ChatState


def get_or_create_chat_state(session: Session, chat_id: uuid.UUID) -> ChatState:
    state = session.get(ChatState, chat_id)
    if state is not None:
        return state
    state = ChatState(chat_id=chat_id)
    session.add(state)
    session.flush()
    return state


def update_rolling_summary(
    session: Session, chat_id: uuid.UUID, summary: str, *, last_message_ts: datetime | None = None
) -> ChatState:
    state = get_or_create_chat_state(session, chat_id)
    state.rolling_summary = summary
    if last_message_ts is not None:
        state.last_message_ts = last_message_ts
    session.flush()
    return state
