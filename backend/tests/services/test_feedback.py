import uuid

from app.core.security import hash_password
from app.db.models import Feedback, User
from app.services.feedback import (
    recent_action_feedback,
    recent_item_corrections,
    record_item_correction,
)


def _manager(db_session) -> User:
    user = User(email=f"fb-{uuid.uuid4()}@example.com", name="Manager", role="manager",
               password_hash=hash_password("x"))
    db_session.add(user)
    db_session.flush()
    return user


async def test_recent_action_feedback_formats_approvals_and_rejections(db_session):
    marker = str(uuid.uuid4())
    manager = _manager(db_session)
    db_session.add(Feedback(kind="action_approval", target_id=uuid.uuid4(), user_id=manager.id,
                            payload={"approved": True, "payload": {"subject": f"approved-{marker}"}}))
    db_session.add(Feedback(kind="action_rejection", target_id=uuid.uuid4(), user_id=manager.id,
                            payload={"approved": False, "feedback": "too aggressive",
                                     "payload": {"subject": f"rejected-{marker}"}}))
    db_session.commit()

    text = recent_action_feedback(db_session, limit=50)
    assert f"Approved as drafted: \"approved-{marker}\"" in text
    assert f"Rejected: \"rejected-{marker}\"" in text
    assert "too aggressive" in text


async def test_recent_item_corrections_scoped_to_chat_and_reports_verdict(db_session, seed_chat, seed_chat_2):
    manager = _manager(db_session)
    record_item_correction(db_session, item_id=uuid.uuid4(), chat_id=seed_chat.id, item_type="action",
                           title="Confirm delivery", from_status="needs_review", to_status="open",
                           user_id=manager.id)
    record_item_correction(db_session, item_id=uuid.uuid4(), chat_id=seed_chat.id, item_type="risk",
                           title="Phantom risk", from_status="needs_review", to_status="cancelled",
                           user_id=manager.id)
    record_item_correction(db_session, item_id=uuid.uuid4(), chat_id=seed_chat_2.id, item_type="action",
                           title="Other chat item", from_status="needs_review", to_status="open",
                           user_id=manager.id)
    db_session.commit()

    text = recent_item_corrections(db_session, seed_chat.id)
    assert "Confirm delivery" in text and "confirmed as real" in text
    assert "Phantom risk" in text and "rejected as not a real item" in text
    assert "Other chat item" not in text
