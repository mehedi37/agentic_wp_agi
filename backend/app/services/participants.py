import difflib
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


def resolve_participant(name_or_mention: str, chat_id: uuid.UUID, session: Session) -> Participant | None:
    """Fuzzy-resolves an `owner_raw`/@mention string to a real participant
    in the chat. Returns `None` on no match or on an ambiguous match --
    never guesses."""
    name = name_or_mention.strip().lstrip("@").strip()
    if not name:
        return None

    exact = session.scalar(
        select(Participant).where(
            Participant.chat_id == chat_id,
            func.lower(Participant.display_name) == name.lower(),
        )
    )
    if exact is not None:
        return exact

    candidates = list(session.scalars(select(Participant).where(Participant.chat_id == chat_id)))
    names = [c.display_name for c in candidates]
    matches = difflib.get_close_matches(name, names, n=2, cutoff=0.6)
    if len(matches) != 1:
        return None
    return next(c for c in candidates if c.display_name == matches[0])
