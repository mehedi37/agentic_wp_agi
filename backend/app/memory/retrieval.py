import uuid

from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import Message
from app.llm.embeddings import EmbeddingProvider

_RRF_K = 60


class SearchResult(BaseModel):
    message_id: uuid.UUID
    chat_id: uuid.UUID
    text: str
    score: float


async def hybrid_search(
    session: Session,
    query: str,
    provider: EmbeddingProvider,
    *,
    k: int = 10,
    chat_id: uuid.UUID | None = None,
) -> list[SearchResult]:
    """Fuses pgvector cosine search with Postgres full-text search (`simple`
    config, PLAN.md §7) via Reciprocal Rank Fusion: score = sum over the two
    rankers of 1/(RRF_K + rank). Every result carries `message_id` so
    citations are guaranteed."""
    fetch_n = max(k * 4, 20)

    [query_vector] = await provider.embed([query])
    vector_stmt = (
        select(Message.id)
        .where(Message.embedding.is_not(None))
        .order_by(Message.embedding.cosine_distance(query_vector))
        .limit(fetch_n)
    )
    if chat_id is not None:
        vector_stmt = vector_stmt.where(Message.chat_id == chat_id)
    vector_ranked = list(session.scalars(vector_stmt))

    fts_stmt = (
        select(Message.id)
        .where(text("tsv @@ plainto_tsquery('simple', :q)"))
        .order_by(text("ts_rank(tsv, plainto_tsquery('simple', :q)) DESC"))
        .limit(fetch_n)
        .params(q=query)
    )
    if chat_id is not None:
        fts_stmt = fts_stmt.where(Message.chat_id == chat_id)
    fts_ranked = list(session.scalars(fts_stmt))

    scores: dict[uuid.UUID, float] = {}
    for rank, msg_id in enumerate(vector_ranked):
        scores[msg_id] = scores.get(msg_id, 0.0) + 1.0 / (_RRF_K + rank + 1)
    for rank, msg_id in enumerate(fts_ranked):
        scores[msg_id] = scores.get(msg_id, 0.0) + 1.0 / (_RRF_K + rank + 1)

    if not scores:
        return []

    top_ids = sorted(scores, key=lambda mid: scores[mid], reverse=True)[:k]
    rows = {m.id: m for m in session.scalars(select(Message).where(Message.id.in_(top_ids)))}
    return [
        SearchResult(message_id=mid, chat_id=rows[mid].chat_id, text=rows[mid].text, score=scores[mid])
        for mid in top_ids
        if mid in rows
    ]
