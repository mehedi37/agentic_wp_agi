import uuid
from datetime import datetime, timezone

from app.schemas.message import MessageIn


def test_message_in_builds_from_minimal_fields() -> None:
    msg = MessageIn(
        chat_id=uuid.uuid4(),
        ts=datetime.now(timezone.utc),
        text="hello",
        content_hash="abc123",
    )
    assert msg.is_system is False
    assert msg.participant_id is None
