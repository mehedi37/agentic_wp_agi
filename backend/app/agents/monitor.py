"""Monitor agent (PLAN.md §6.4): observe -> detect -> decide -> emit ->
re-check loop. Runs after every pipeline batch (and, in production, on a
cron schedule -- not wired to a scheduler in this phase, see workers/).
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.agent_runs import log_agent_run
from app.db.models import Escalation
from app.services.escalation_rules import (
    EscalationCandidate,
    detect_overdue_actions,
    detect_recurring_issue,
    detect_sentiment_dip,
    detect_unowned_high_risk,
)
from app.services.rules import rule_config

_DETECTORS = [detect_overdue_actions, detect_unowned_high_risk, detect_recurring_issue, detect_sentiment_dip]


def _dedup_key(item_id: uuid.UUID | None, chat_id: uuid.UUID | None, rule: str) -> tuple:
    return (rule, item_id, chat_id if item_id is None else None)


def run_monitor(session: Session, *, chat_id: uuid.UUID | None = None, run_id: str | None = None) -> list[Escalation]:
    run_id = run_id or str(uuid.uuid4())

    candidates: list[EscalationCandidate] = []
    for rule_key, detector in zip(("overdue_action", "unowned_high_risk", "recurring_issue", "sentiment_dip"), _DETECTORS):
        if rule_config(session, rule_key)[0]:
            candidates.extend(detector(session, chat_id=chat_id))
    log_agent_run(
        session, run_id=run_id, agent="monitor", node="detect", status="ok",
        output_summary=f"{len(candidates)} candidates from {len(_DETECTORS)} detectors",
    )

    open_query = select(Escalation).where(Escalation.status.in_(["open", "acknowledged"]))
    if chat_id is not None:
        open_query = open_query.where(Escalation.chat_id == chat_id)
    open_escalations = list(session.scalars(open_query))
    open_by_key = {_dedup_key(e.item_id, e.chat_id, e.rule): e for e in open_escalations}

    created: list[Escalation] = []
    candidate_keys = set()
    for cand in candidates:
        key = _dedup_key(cand.item_id, cand.chat_id, cand.rule)
        candidate_keys.add(key)
        if key in open_by_key:
            continue
        escalation = Escalation(
            rule=cand.rule, severity=cand.severity, item_id=cand.item_id, chat_id=cand.chat_id,
            rationale=cand.rationale, evidence=cand.evidence, status="open",
        )
        session.add(escalation)
        created.append(escalation)
    session.flush()
    log_agent_run(
        session, run_id=run_id, agent="monitor", node="emit", status="ok",
        output_summary=f"{len(created)} new escalations created",
    )

    auto_closed = 0
    for escalation in open_escalations:
        key = _dedup_key(escalation.item_id, escalation.chat_id, escalation.rule)
        if key not in candidate_keys:
            escalation.status = "auto_closed"
            auto_closed += 1
    session.flush()
    log_agent_run(
        session, run_id=run_id, agent="monitor", node="recheck", status="ok",
        output_summary=f"{auto_closed} escalations auto-closed",
    )

    return created
