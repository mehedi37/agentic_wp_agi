import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from app.schemas.segment import SegmentOut


def test_segment_out_builds_from_minimal_fields() -> None:
    segment = SegmentOut(
        id=uuid.uuid4(),
        chat_id=uuid.uuid4(),
        start_ts=datetime.now(UTC),
        end_ts=datetime.now(UTC),
        analysis_status="pending",
    )
    assert segment.message_ids == []
    assert segment.topic is None


def test_segment_out_from_attributes() -> None:
    fake_orm_segment = SimpleNamespace(
        id=uuid.uuid4(),
        chat_id=uuid.uuid4(),
        start_ts=datetime.now(UTC),
        end_ts=datetime.now(UTC),
        message_ids=[uuid.uuid4(), uuid.uuid4()],
        topic="invoice follow-up",
        category="client",
        sentiment="neutral",
        urgency="medium",
        summary="Discussed invoice status",
        analysis_status="done",
    )

    segment = SegmentOut.model_validate(fake_orm_segment)
    assert segment.topic == "invoice follow-up"
    assert len(segment.message_ids) == 2
