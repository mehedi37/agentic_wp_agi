from sqlalchemy.orm import Session

from app.db.models import AgentRun


def log_agent_run(
    session: Session,
    *,
    run_id: str,
    agent: str,
    node: str,
    iteration: int = 0,
    status: str,
    input_summary: str | None = None,
    output_summary: str | None = None,
    model: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    latency_ms: int | None = None,
    error: str | None = None,
) -> AgentRun:
    run = AgentRun(
        run_id=run_id, agent=agent, node=node, iteration=iteration, status=status,
        input_summary=input_summary, output_summary=output_summary, model=model,
        tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=latency_ms, error=error,
    )
    session.add(run)
    session.flush()
    return run
