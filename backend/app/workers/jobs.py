import uuid

from app.agents.action import plan_action
from app.agents.monitor import run_monitor
from app.agents.pipeline_graph import run_pipeline_for_chat
from app.db.session import SessionLocal
from app.llm.factory import get_embedding_provider, get_llm_provider
from app.memory.consolidation import consolidate_memory


async def process_batch(ctx: dict, chat_id: str) -> dict:
    session = SessionLocal()
    try:
        llm = get_llm_provider()
        embedder = get_embedding_provider()
        parsed_chat_id = uuid.UUID(chat_id)
        await run_pipeline_for_chat(
            session, chat_id=parsed_chat_id, analyst_llm=llm, judge_llm=llm, embedder=embedder,
        )
        escalations = run_monitor(session, chat_id=parsed_chat_id)
        for escalation in escalations:
            await plan_action(session, escalation, llm)
        session.commit()
        return {"chat_id": chat_id, "status": "ok", "escalations_created": len(escalations)}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def monitor_all(ctx: dict) -> dict:
    with SessionLocal() as session:
        escalations = run_monitor(session)
        llm = get_llm_provider()
        for escalation in escalations:
            await plan_action(session, escalation, llm)
        session.commit()
        return {"escalations_created": len(escalations)}


async def consolidate(ctx: dict) -> dict:
    with SessionLocal() as session:
        result = await consolidate_memory(session, get_embedding_provider())
        session.commit()
        return result
