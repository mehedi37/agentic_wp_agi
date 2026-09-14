import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from app.agents.validator import run_validator
from app.db.models import Message, Segment
from app.llm.fake_provider import FakeProvider
from app.schemas.item import EvidenceRef, ExtractedItem

TZ = ZoneInfo("Asia/Dhaka")


def _seed_segment(db_session, seed_chat, txt="kal warehouse stock pathabo"):
    msg = Message(chat_id=seed_chat.id, ts=datetime.now(tz=TZ), text=txt, content_hash=str(uuid.uuid4()))
    db_session.add(msg)
    db_session.flush()
    seg = Segment(chat_id=seed_chat.id, start_ts=msg.ts, end_ts=msg.ts, message_ids=[msg.id])
    db_session.add(seg)
    db_session.flush()
    return seg, msg


async def test_passes_when_evidence_grounds_and_judge_confident(db_session, seed_chat):
    seg, msg = _seed_segment(db_session, seed_chat)
    item = ExtractedItem(
        type="action", title="Send stock", owner_raw="Rafi",
        evidence=[EvidenceRef(message_id=msg.id, quote="kal warehouse stock pathabo")], confidence=0.8,
    )
    judge = FakeProvider(structured_responses=[{"confidence": 0.9}])
    report = await run_validator(db_session, segment=seg, items=[item], judge_llm=judge)
    assert report.passed is True
    assert report.per_item_verdicts[0].passed is True


async def test_fails_when_quote_not_found_in_cited_message(db_session, seed_chat):
    seg, msg = _seed_segment(db_session, seed_chat)
    item = ExtractedItem(
        type="action", title="Send stock", owner_raw="Rafi",
        evidence=[EvidenceRef(message_id=msg.id, quote="this text is not in the message")],
        confidence=0.8,
    )
    judge = FakeProvider(structured_responses=[{"confidence": 0.9}])
    report = await run_validator(db_session, segment=seg, items=[item], judge_llm=judge)
    assert report.passed is False
    assert any("quote" in i.message.lower() for i in report.per_item_verdicts[0].issues)


async def test_fails_when_evidence_message_id_outside_segment(db_session, seed_chat):
    seg, _msg = _seed_segment(db_session, seed_chat)
    foreign_id = uuid.uuid4()
    item = ExtractedItem(
        type="action", title="Send stock",
        evidence=[EvidenceRef(message_id=foreign_id, quote="kal warehouse stock pathabo")],
        confidence=0.8,
    )
    judge = FakeProvider(structured_responses=[{"confidence": 0.9}])
    report = await run_validator(db_session, segment=seg, items=[item], judge_llm=judge)
    assert report.passed is False


async def test_low_judge_confidence_fails_item(db_session, seed_chat):
    seg, msg = _seed_segment(db_session, seed_chat)
    item = ExtractedItem(
        type="action", title="Send stock",
        evidence=[EvidenceRef(message_id=msg.id, quote="kal warehouse stock pathabo")], confidence=0.8,
    )
    judge = FakeProvider(structured_responses=[{"confidence": 0.2}])
    report = await run_validator(db_session, segment=seg, items=[item], judge_llm=judge)
    assert report.passed is False


async def test_feedback_string_summarizes_issues(db_session, seed_chat):
    seg, msg = _seed_segment(db_session, seed_chat)
    item = ExtractedItem(
        type="action", title="Send stock",
        evidence=[EvidenceRef(message_id=msg.id, quote="not present in message")], confidence=0.8,
    )
    judge = FakeProvider(structured_responses=[{"confidence": 0.9}])
    report = await run_validator(db_session, segment=seg, items=[item], judge_llm=judge)
    assert report.feedback is not None and "item 1" in report.feedback.lower()


async def test_empty_items_list_passes(db_session, seed_chat):
    seg, _msg = _seed_segment(db_session, seed_chat)
    judge = FakeProvider(structured_responses=[{"confidence": 0.9}])
    report = await run_validator(db_session, segment=seg, items=[], judge_llm=judge)
    assert report.passed is True
