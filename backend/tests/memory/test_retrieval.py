from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.db.models import Message
from app.llm.embeddings import FakeEmbeddingProvider
from app.memory.long_term import embed_and_store_message
from app.memory.retrieval import hybrid_search

TZ = ZoneInfo("Asia/Dhaka")


async def _seed_messages(db_session, seed_chat, provider):
    now = datetime.now(tz=TZ)
    texts = [
        "kal warehouse delivery confirm hobe",
        "গোডাউনে আবার লিকেজ হচ্ছে",
        "client meeting rescheduled to next week",
        "warehouse stock count completed",
    ]
    messages = []
    for i, txt in enumerate(texts):
        msg = Message(chat_id=seed_chat.id, ts=now - timedelta(hours=i), text=txt, content_hash=f"ret-h{i}")
        db_session.add(msg)
        db_session.flush()
        await embed_and_store_message(db_session, msg, provider)
        messages.append(msg)
    db_session.flush()
    return messages


async def test_keyword_query_finds_matching_message(db_session, seed_chat):
    provider = FakeEmbeddingProvider()
    await _seed_messages(db_session, seed_chat, provider)
    results = await hybrid_search(db_session, "warehouse", provider, k=5, chat_id=seed_chat.id)
    assert any("warehouse" in r.text for r in results)


async def test_bangla_query_finds_bangla_message(db_session, seed_chat):
    provider = FakeEmbeddingProvider()
    await _seed_messages(db_session, seed_chat, provider)
    results = await hybrid_search(db_session, "গোডাউন লিকেজ", provider, k=5, chat_id=seed_chat.id)
    assert any("লিকেজ" in r.text for r in results)


async def test_results_carry_source_message_id(db_session, seed_chat):
    provider = FakeEmbeddingProvider()
    await _seed_messages(db_session, seed_chat, provider)
    results = await hybrid_search(db_session, "warehouse", provider, k=5, chat_id=seed_chat.id)
    assert all(r.message_id is not None for r in results)


async def test_chat_filter_excludes_other_chats(db_session, seed_chat, seed_chat_2):
    provider = FakeEmbeddingProvider()
    await _seed_messages(db_session, seed_chat, provider)
    other = Message(
        chat_id=seed_chat_2.id, ts=datetime.now(tz=TZ), text="warehouse unrelated chat", content_hash="ret-other1"
    )
    db_session.add(other)
    db_session.flush()
    await embed_and_store_message(db_session, other, provider)
    db_session.flush()

    results = await hybrid_search(db_session, "warehouse", provider, k=10, chat_id=seed_chat.id)
    assert all(r.chat_id == seed_chat.id for r in results)


async def test_k_limits_result_count(db_session, seed_chat):
    provider = FakeEmbeddingProvider()
    await _seed_messages(db_session, seed_chat, provider)
    results = await hybrid_search(db_session, "warehouse delivery client stock", provider, k=2)
    assert len(results) <= 2
