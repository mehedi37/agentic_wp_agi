import uuid

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import AuditLog, User
from app.services.audit import record_audit_event


def _engine():
    return create_engine(settings.database_url)


def test_record_audit_event_inserts_row_with_actor() -> None:
    engine = _engine()
    with Session(engine) as session:
        user = User(
            email=f"audit-{uuid.uuid4()}@example.com",
            name="Audit Actor",
            role="manager",
            password_hash=hash_password("x"),
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        entry = record_audit_event(
            session,
            user.id,
            "action.approve",
            details={"target_type": "proposed_action", "target_id": str(uuid.uuid4())},
        )
        session.commit()
        session.refresh(entry)

        assert entry.id is not None
        assert entry.user_id == user.id
        assert entry.action == "action.approve"
        assert entry.details is not None
        assert entry.details["target_type"] == "proposed_action"
        assert entry.ts is not None

        session.execute(delete(AuditLog).where(AuditLog.id == entry.id))
        session.execute(delete(User).where(User.id == user.id))
        session.commit()


def test_record_audit_event_allows_null_actor_for_system_events() -> None:
    engine = _engine()
    with Session(engine) as session:
        entry = record_audit_event(session, None, "monitor.escalation_created")
        session.commit()
        session.refresh(entry)

        assert entry.user_id is None
        assert entry.details is None

        session.execute(delete(AuditLog).where(AuditLog.id == entry.id))
        session.commit()
