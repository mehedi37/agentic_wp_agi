import time
import uuid
from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.agent_runs import log_agent_run
from app.agents.analyst import run_analyst
from app.agents.state import PipelineState
from app.agents.validator import run_validator
from app.db.models import Message, Segment
from app.llm.base import LLMProvider
from app.llm.embeddings import EmbeddingProvider
from app.memory.long_term import (
    embed_and_store_item,
    embed_and_store_message,
    embed_and_store_segment,
)
from app.memory.short_term import update_rolling_summary
from app.services.date_resolver import resolve_date
from app.services.items import persist_item
from app.services.participants import resolve_participant
from app.services.segmentation import persist_pending_segments

_MAX_ITERATIONS = 3


def _get_segment(session: Session, segment_id: uuid.UUID) -> Segment:
    segment = session.get(Segment, segment_id)
    if segment is None:
        raise ValueError(f"segment {segment_id} not found")
    return segment


def _build_graph(
    session: Session, llm: LLMProvider, judge_llm: LLMProvider, embedder: EmbeddingProvider
) -> Any:
    async def analyse_node(state: PipelineState) -> PipelineState:
        segment = _get_segment(session, state["segment_id"])
        start = time.perf_counter()
        result = await run_analyst(session, segment=segment, llm=llm, feedback=state["feedback"])
        log_agent_run(
            session, run_id=state["run_id"], agent="pipeline", node="analyse",
            iteration=state["iteration"], status="ok",
            input_summary=f"segment {segment.id}", output_summary=f"{len(result.items)} items",
            latency_ms=int((time.perf_counter() - start) * 1000),
        )
        segment.topic, segment.category = result.topic, result.category
        segment.sentiment, segment.urgency = result.sentiment, result.urgency
        return {**state, "candidate_items": result.items, "iteration": state["iteration"] + 1}

    async def validate_node(state: PipelineState) -> PipelineState:
        segment = _get_segment(session, state["segment_id"])
        report = await run_validator(
            session, segment=segment, items=state["candidate_items"], judge_llm=judge_llm
        )
        log_agent_run(
            session, run_id=state["run_id"], agent="pipeline", node="validate",
            iteration=state["iteration"], status="ok" if report.passed else "failed",
            output_summary=report.feedback or "passed",
        )
        return {**state, "validation": report, "feedback": report.feedback}

    def route_after_validate(state: PipelineState) -> str:
        report = state["validation"]
        assert report is not None
        if report.passed:
            return "pass"
        if state["iteration"] >= _MAX_ITERATIONS:
            return "needs_review"
        return "retry"

    async def memory_write_node(state: PipelineState) -> PipelineState:
        segment = _get_segment(session, state["segment_id"])
        report = state["validation"]
        status = "passed" if report is not None and report.passed else "needs_review"
        for extracted in state["candidate_items"]:
            owner_participant = None
            if extracted.owner_raw:
                owner_participant = resolve_participant(extracted.owner_raw, segment.chat_id, session)
            due_at = extracted.due_at
            if due_at is None and extracted.due_date_raw:
                due_at = resolve_date(extracted.due_date_raw, anchor_ts=segment.end_ts)

            values = {
                "type": extracted.type, "title": extracted.title, "description": extracted.description,
                "chat_id": segment.chat_id, "segment_id": segment.id,
                "owner_participant_id": owner_participant.id if owner_participant else None,
                "owner_raw": extracted.owner_raw, "due_at": due_at, "due_raw": extracted.due_date_raw,
                "priority": extracted.priority, "severity": extracted.severity, "likelihood": extracted.likelihood,
                "confidence": extracted.confidence, "validation_status": status,
            }
            item = persist_item(session, segment, extracted, values, passed=status == "passed")
            await embed_and_store_item(session, item, embedder)

        segment.analysis_status = "done" if status == "passed" else "needs_review"
        await embed_and_store_segment(session, segment, embedder)
        update_rolling_summary(
            session, segment.chat_id, segment.summary or segment.topic or "", last_message_ts=segment.end_ts
        )
        session.flush()
        log_agent_run(session, run_id=state["run_id"], agent="pipeline", node="memory_write", status="ok")
        return {**state, "status": status}

    graph = StateGraph(PipelineState)
    graph.add_node("analyse", analyse_node)
    graph.add_node("validate", validate_node)
    graph.add_node("memory_write", memory_write_node)
    graph.set_entry_point("analyse")
    graph.add_edge("analyse", "validate")
    graph.add_conditional_edges(
        "validate", route_after_validate,
        {"retry": "analyse", "needs_review": "memory_write", "pass": "memory_write"},
    )
    graph.add_edge("memory_write", END)
    return graph.compile()


async def run_pipeline_for_chat(
    session: Session,
    *,
    chat_id: uuid.UUID,
    analyst_llm: LLMProvider,
    judge_llm: LLMProvider,
    embedder: EmbeddingProvider,
) -> None:
    """`load_batch` + `segment` happen here, outside the compiled graph,
    because they operate once per *chat batch* (many segments), while the
    compiled graph runs once per *segment* (the analyse<->validate retry
    loop is segment-scoped, per PLAN.md §4.1)."""
    run_id = str(uuid.uuid4())
    start = time.perf_counter()
    unembedded = list(
        session.scalars(
            select(Message).where(Message.chat_id == chat_id, Message.embedding.is_(None))
        )
    )
    for message in unembedded:
        await embed_and_store_message(session, message, embedder)
    log_agent_run(
        session, run_id=run_id, agent="pipeline", node="load_batch", status="ok",
        output_summary=f"{len(unembedded)} messages embedded",
        latency_ms=int((time.perf_counter() - start) * 1000),
    )

    start = time.perf_counter()
    segments = persist_pending_segments(session, chat_id)
    log_agent_run(
        session, run_id=run_id, agent="pipeline", node="segment", status="ok",
        output_summary=f"{len(segments)} segments", latency_ms=int((time.perf_counter() - start) * 1000),
    )

    graph = _build_graph(session, analyst_llm, judge_llm, embedder)
    for segment in segments:
        initial_state: PipelineState = {
            "run_id": run_id, "chat_id": chat_id, "segment_id": segment.id, "iteration": 0,
            "candidate_items": [], "validation": None, "feedback": None, "status": "in_progress",
        }
        await graph.ainvoke(initial_state)
