import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.agents.validator import run_validator
from app.db.models import Item, ItemEvidence, ItemHistory, Message, Segment
from app.llm.fake_provider import FakeProvider
from app.schemas.item import EvidenceRef, ExtractedItem
from app.services.items import persist_item


async def test_completion_updates_original_and_preserves_evidence(db_session, seed_chat):
    msg = Message(chat_id=seed_chat.id, ts=datetime.now(UTC), text="Stock report done",
                  content_hash=str(uuid.uuid4()))
    db_session.add(msg)
    db_session.flush()
    segment = Segment(chat_id=seed_chat.id, start_ts=msg.ts, end_ts=msg.ts, message_ids=[msg.id])
    original = Item(chat_id=seed_chat.id, title="Stock report", type="action", status="open",
                    validation_status="passed")
    db_session.add_all([segment, original])
    db_session.flush()
    extracted = ExtractedItem(type="action", title="Stock report", related_item_id=original.id,
        status_hint="completed", confidence=.9, evidence=[EvidenceRef(message_id=msg.id, quote=msg.text)])
    values = {"title": extracted.title, "type": "action", "chat_id": seed_chat.id}
    result = persist_item(db_session, segment, extracted, values, passed=True)
    assert result.id == original.id and result.status == "done"
    assert len(list(db_session.scalars(select(ItemHistory).where(ItemHistory.item_id == result.id)))) == 1
    persist_item(db_session, segment, extracted, values, passed=True)
    assert len(list(db_session.scalars(select(ItemEvidence).where(ItemEvidence.item_id == result.id)))) == 1
    extracted.related_item_id = uuid.uuid4()
    report = await run_validator(db_session, segment=segment, items=[extracted],
        judge_llm=FakeProvider())
    assert not report.passed
    assert any(issue.field == "related_item_id" for issue in report.issues)
