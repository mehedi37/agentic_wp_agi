from datetime import datetime
from zoneinfo import ZoneInfo

from app.agents.analyst import run_analyst
from app.db.models import Message, Segment
from app.llm.fake_provider import FakeProvider
from app.schemas.item import EvidenceRef, ExtractedItem

TZ = ZoneInfo("Asia/Dhaka")


def _seed_segment(db_session, seed_chat):
    msg = Message(
        chat_id=seed_chat.id, ts=datetime.now(tz=TZ), text="kal warehouse stock pathabo",
        content_hash="analyst-h1",
    )
    db_session.add(msg)
    db_session.flush()
    seg = Segment(
        chat_id=seed_chat.id, start_ts=msg.ts, end_ts=msg.ts, message_ids=[msg.id],
        analysis_status="pending",
    )
    db_session.add(seg)
    db_session.flush()
    return seg, msg


async def test_returns_extracted_items_from_scripted_llm(db_session, seed_chat):
    seg, msg = _seed_segment(db_session, seed_chat)
    scripted = ExtractedItem(
        type="action", title="Send warehouse stock", owner_raw="Rafi", due_date_raw="kal",
        evidence=[EvidenceRef(message_id=msg.id, quote="kal warehouse stock pathabo")],
        confidence=0.8,
    )
    provider = FakeProvider(
        structured_responses=[
            {
                "items": [scripted.model_dump(mode="json")],
                "topic": "logistics", "category": "project_update",
                "sentiment": "neutral", "urgency": "medium",
            }
        ]
    )

    result = await run_analyst(db_session, segment=seg, llm=provider, feedback=None)

    assert len(result.items) == 1
    assert result.items[0].title == "Send warehouse stock"


async def test_passes_feedback_into_prompt_when_retrying(db_session, seed_chat):
    seg, msg = _seed_segment(db_session, seed_chat)
    scripted = ExtractedItem(
        type="action", title="Send warehouse stock", owner_raw="Rafi",
        evidence=[EvidenceRef(message_id=msg.id, quote="kal warehouse stock pathabo")], confidence=0.9,
    )
    provider = FakeProvider(
        structured_responses=[
            {
                "items": [scripted.model_dump(mode="json")],
                "topic": "logistics", "category": "project_update",
                "sentiment": "neutral", "urgency": "medium",
            }
        ]
    )

    await run_analyst(db_session, segment=seg, llm=provider, feedback="item 1: owner ambiguous")

    sent_messages = provider.calls[0]["messages"]
    assert any("owner ambiguous" in m["content"] for m in sent_messages)
