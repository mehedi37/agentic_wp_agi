from datetime import datetime
from zoneinfo import ZoneInfo

from app.db.models import Item, Message, Segment
from app.llm.embeddings import FakeEmbeddingProvider
from app.memory.long_term import (
    embed_and_store_item,
    embed_and_store_message,
    embed_and_store_segment,
)

TZ = ZoneInfo("Asia/Dhaka")


async def test_embeds_and_stores_message(db_session, seed_chat):
    msg = Message(chat_id=seed_chat.id, ts=datetime.now(tz=TZ), text="kal delivery hobe", content_hash="lt-h1")
    db_session.add(msg)
    db_session.flush()

    await embed_and_store_message(db_session, msg, FakeEmbeddingProvider())
    db_session.flush()
    assert msg.embedding is not None
    assert len(msg.embedding) == 1024


async def test_embeds_and_stores_segment(db_session, seed_chat):
    seg = Segment(
        chat_id=seed_chat.id,
        start_ts=datetime.now(tz=TZ),
        end_ts=datetime.now(tz=TZ),
        summary="Discussion about warehouse delivery timeline.",
    )
    db_session.add(seg)
    db_session.flush()
    await embed_and_store_segment(db_session, seg, FakeEmbeddingProvider())
    db_session.flush()
    assert seg.embedding is not None


async def test_embeds_and_stores_item(db_session, seed_chat):
    item = Item(type="action", title="Deliver warehouse stock", chat_id=seed_chat.id)
    db_session.add(item)
    db_session.flush()
    await embed_and_store_item(db_session, item, FakeEmbeddingProvider())
    db_session.flush()
    assert item.embedding is not None


async def test_skips_embedding_when_text_empty(db_session, seed_chat):
    msg = Message(chat_id=seed_chat.id, ts=datetime.now(tz=TZ), text="", content_hash="lt-h2")
    db_session.add(msg)
    db_session.flush()
    await embed_and_store_message(db_session, msg, FakeEmbeddingProvider())
    assert msg.embedding is None
