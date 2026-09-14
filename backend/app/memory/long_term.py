from sqlalchemy.orm import Session

from app.db.models import Item, Message, Segment
from app.llm.embeddings import EmbeddingProvider


async def embed_and_store_message(session: Session, message: Message, provider: EmbeddingProvider) -> None:
    if not message.text.strip():
        return
    [vector] = await provider.embed([message.text])
    message.embedding = vector
    session.flush()


async def embed_and_store_segment(session: Session, segment: Segment, provider: EmbeddingProvider) -> None:
    text = segment.summary or segment.topic
    if not text or not text.strip():
        return
    [vector] = await provider.embed([text])
    segment.embedding = vector
    session.flush()


async def embed_and_store_item(session: Session, item: Item, provider: EmbeddingProvider) -> None:
    text = f"{item.title}. {item.description or ''}".strip()
    if not text:
        return
    [vector] = await provider.embed([text])
    item.embedding = vector
    session.flush()
