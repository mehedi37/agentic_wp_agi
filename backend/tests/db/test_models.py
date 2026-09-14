import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Chat, Message, User


def _engine():
    return create_engine(settings.database_url)


def test_user_role_roundtrip() -> None:
    engine = _engine()
    with Session(engine) as session:
        user = User(
            email=f"test-{uuid.uuid4()}@example.com",
            name="Test User",
            role="manager",
            password_hash="x",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.id is not None
        assert user.role == "manager"
        session.delete(user)
        session.commit()


def test_message_content_hash_unique() -> None:
    engine = _engine()
    with Session(engine) as session:
        chat = Chat(source="export", name="Test Chat", type="group", timezone="Asia/Dhaka")
        session.add(chat)
        session.commit()
        session.refresh(chat)

        content_hash = f"hash-{uuid.uuid4()}"
        msg = Message(
            chat_id=chat.id,
            ts=datetime.now(UTC),
            text="hello",
            content_hash=content_hash,
        )
        session.add(msg)
        session.commit()

        dup = Message(
            chat_id=chat.id,
            ts=datetime.now(UTC),
            text="hello again",
            content_hash=content_hash,
        )
        session.add(dup)
        try:
            session.commit()
            raised = False
        except IntegrityError:
            session.rollback()
            raised = True
        assert raised, "duplicate content_hash must violate the unique constraint"

        session.delete(msg)
        # Flush the message delete before deleting the chat: there is no ORM
        # relationship() between Chat and Message (only a raw FK with
        # ondelete="CASCADE"), so without an explicit flush here the unit of
        # work may process the chats delete first, letting the DB-level
        # CASCADE remove the message row out from under the still-pending
        # ORM delete for `msg`.
        session.flush()
        session.delete(chat)
        session.commit()
