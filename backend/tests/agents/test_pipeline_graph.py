import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.agents.pipeline_graph import run_pipeline_for_chat
from app.db.models import AgentRun, Item, Message
from app.llm.embeddings import FakeEmbeddingProvider
from app.llm.fake_provider import FakeProvider
from app.schemas.item import EvidenceRef, ExtractedItem

TZ = ZoneInfo("Asia/Dhaka")


def _seed_messages(db_session, seed_chat):
    now = datetime.now(tz=TZ)
    m1 = Message(chat_id=seed_chat.id, ts=now, text="kal warehouse stock pathabo", content_hash=str(uuid.uuid4()))
    m2 = Message(
        chat_id=seed_chat.id, ts=now + timedelta(minutes=2), text="thik ache Rafi", content_hash=str(uuid.uuid4())
    )
    db_session.add_all([m1, m2])
    db_session.flush()
    return [m1, m2]


def _classification():
    return {"topic": "logistics", "category": "project_update", "sentiment": "neutral", "urgency": "medium"}


def _existing_agent_run_ids(db_session) -> set:
    return {r.id for r in db_session.query(AgentRun.id).all()}


async def test_pipeline_passes_on_first_try_and_stores_items(db_session, seed_chat):
    before_run_ids = _existing_agent_run_ids(db_session)
    msgs = _seed_messages(db_session, seed_chat)
    good_item = ExtractedItem(
        type="action", title="Send warehouse stock", owner_raw="Rafi",
        evidence=[EvidenceRef(message_id=msgs[0].id, quote="kal warehouse stock pathabo")], confidence=0.9,
    )
    analyst_llm = FakeProvider(
        structured_responses=[{**_classification(), "items": [good_item.model_dump(mode="json")]}]
    )
    judge_llm = FakeProvider(structured_responses=[{"confidence": 0.9}])

    await run_pipeline_for_chat(
        db_session, chat_id=seed_chat.id, analyst_llm=analyst_llm, judge_llm=judge_llm,
        embedder=FakeEmbeddingProvider(),
    )
    db_session.commit()

    items = db_session.query(Item).filter(Item.chat_id == seed_chat.id).all()
    assert len(items) == 1
    assert items[0].validation_status == "passed"

    runs = db_session.query(AgentRun).filter(AgentRun.id.notin_(before_run_ids)).all()
    nodes = {r.node for r in runs}
    assert {"load_batch", "segment", "analyse", "validate", "memory_write"} <= nodes


async def test_pipeline_retries_after_validator_feedback_then_passes(db_session, seed_chat):
    before_run_ids = _existing_agent_run_ids(db_session)
    msgs = _seed_messages(db_session, seed_chat)
    bad_item = ExtractedItem(
        type="action", title="Send warehouse stock", owner_raw="Rafi",
        evidence=[EvidenceRef(message_id=msgs[0].id, quote="text that is not actually in the message")],
        confidence=0.9,
    )
    good_item = ExtractedItem(
        type="action", title="Send warehouse stock", owner_raw="Rafi",
        evidence=[EvidenceRef(message_id=msgs[0].id, quote="kal warehouse stock pathabo")], confidence=0.9,
    )
    analyst_llm = FakeProvider(
        structured_responses=[
            {**_classification(), "items": [bad_item.model_dump(mode="json")]},
            {**_classification(), "items": [good_item.model_dump(mode="json")]},
        ]
    )
    judge_llm = FakeProvider(structured_responses=[{"confidence": 0.9}])

    await run_pipeline_for_chat(
        db_session, chat_id=seed_chat.id, analyst_llm=analyst_llm, judge_llm=judge_llm,
        embedder=FakeEmbeddingProvider(),
    )
    db_session.commit()

    items = db_session.query(Item).filter(Item.chat_id == seed_chat.id).all()
    assert len(items) == 1
    assert items[0].validation_status == "passed"

    runs = db_session.query(AgentRun).filter(
        AgentRun.id.notin_(before_run_ids), AgentRun.agent == "pipeline", AgentRun.node == "analyse"
    ).all()
    assert len(runs) == 2


async def test_pipeline_routes_to_needs_review_after_three_failures(db_session, seed_chat):
    before_run_ids = _existing_agent_run_ids(db_session)
    msgs = _seed_messages(db_session, seed_chat)
    bad_item = ExtractedItem(
        type="action", title="Send warehouse stock",
        evidence=[EvidenceRef(message_id=msgs[0].id, quote="never appears anywhere")], confidence=0.9,
    )
    analyst_llm = FakeProvider(
        structured_responses=[{**_classification(), "items": [bad_item.model_dump(mode="json")]}]
    )
    judge_llm = FakeProvider(structured_responses=[{"confidence": 0.9}])

    await run_pipeline_for_chat(
        db_session, chat_id=seed_chat.id, analyst_llm=analyst_llm, judge_llm=judge_llm,
        embedder=FakeEmbeddingProvider(),
    )
    db_session.commit()

    items = db_session.query(Item).filter(Item.chat_id == seed_chat.id).all()
    assert len(items) == 1
    assert items[0].validation_status == "needs_review"

    runs = db_session.query(AgentRun).filter(
        AgentRun.id.notin_(before_run_ids), AgentRun.agent == "pipeline", AgentRun.node == "analyse"
    ).all()
    assert len(runs) == 3
