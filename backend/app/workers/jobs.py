import uuid

from app.agents.pipeline_graph import run_pipeline_for_chat
from app.db.session import SessionLocal
from app.llm.factory import get_embedding_provider, get_llm_provider


async def process_batch(ctx: dict, chat_id: str) -> dict:
    session = SessionLocal()
    try:
        llm = get_llm_provider()
        embedder = get_embedding_provider()
        await run_pipeline_for_chat(
            session, chat_id=uuid.UUID(chat_id), analyst_llm=llm, judge_llm=llm, embedder=embedder,
        )
        session.commit()
        return {"chat_id": chat_id, "status": "ok"}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
