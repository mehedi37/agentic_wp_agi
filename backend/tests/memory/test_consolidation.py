import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.models import Message, Summary
from app.llm.embeddings import FakeEmbeddingProvider
from app.memory.consolidation import consolidate_memory


async def test_rollups_keep_citations_and_are_idempotent(db_session, seed_chat):
    message = Message(chat_id=seed_chat.id, ts=datetime(2026, 9, 14, 10, tzinfo=UTC),
                      text="Report approved", content_hash=str(uuid.uuid4()))
    db_session.add(message)
    db_session.flush()
    await consolidate_memory(db_session, FakeEmbeddingProvider())
    rows = list(db_session.scalars(select(Summary).where(Summary.scope_id == str(seed_chat.id))))
    assert {row.scope for row in rows} == {"day", "week"}
    assert all(str(message.id) in row.text for row in rows)
    repeated = await consolidate_memory(db_session, FakeEmbeddingProvider())
    assert repeated["summaries_updated"] == 0
