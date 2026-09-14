from app.agents.agent_runs import log_agent_run
from app.db.models import AgentRun


def test_logs_a_run_row(db_session):
    log_agent_run(
        db_session, run_id="run-1", agent="pipeline", node="analyse", iteration=1,
        status="ok", input_summary="segment abc", output_summary="3 items", model="fake-model",
        tokens_in=10, tokens_out=20, latency_ms=5,
    )
    db_session.flush()
    row = db_session.query(AgentRun).filter(AgentRun.run_id == "run-1").one()
    assert row.node == "analyse" and row.status == "ok"
