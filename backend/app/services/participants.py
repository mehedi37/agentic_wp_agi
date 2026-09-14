import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Participant


def get_or_create_participant(session: Session, chat_id: uuid.UUID, display_name: str) -> Participant:
    existing = session.scalar(
        select(Participant).where(
            Participant.chat_id == chat_id,
            func.lower(Participant.display_name) == display_name.strip().lower(),
        )
    )
    if existing is not None:
        return existing
    participant = Participant(chat_id=chat_id, display_name=display_name.strip())
    session.add(participant)
    session.flush()
    return participant
