import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from app.agents.analyst import run_analyst
from app.core.security import hash_password
from app.db.models import Message, Segment, User
from app.llm.fake_provider import FakeProvider
from app.schemas.item import EvidenceRef, ExtractedItem
from app.services.feedback import record_item_correction

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


async def test_passes_past_human_corrections_into_prompt(db_session, seed_chat):
    seg, msg = _seed_segment(db_session, seed_chat)
    manager = User(email=f"an-fb-{uuid.uuid4()}@example.com", name="Manager", role="manager",
                   password_hash=hash_password("x"))
    db_session.add(manager)
    db_session.flush()
    record_item_correction(
        db_session, item_id=uuid.uuid4(), chat_id=seed_chat.id, item_type="risk",
        title="Phantom risk from last week", from_status="needs_review", to_status="cancelled",
        user_id=manager.id,
    )
    db_session.commit()
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

    await run_analyst(db_session, segment=seg, llm=provider, feedback=None)

    sent_messages = provider.calls[0]["messages"]
    assert any("Phantom risk from last week" in m["content"] for m in sent_messages)
    assert any("rejected as not a real item" in m["content"] for m in sent_messages)
