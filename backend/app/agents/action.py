"""Action agent (PLAN.md §6.5): plan -> (auto-act | await approval) ->
execute -> verify -> record.

Dashboard-alert actions ("notify") bypass the approval gate and execute
immediately (PLAN's state diagram: `Plan --> InternalAct: dashboard alert
only`). Outbound actions ("email"/"whatsapp") require manager approval via
the API before executing. The real SMTP/WhatsApp Cloud API senders are
Phase 4 scope (PLAN.md T4.2) -- until then, approved outbound actions
"execute" as a recorded simulation, which still exercises the full
plan/approve/execute/verify/record loop end-to-end.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models import Escalation, Notification, ProposedAction
from app.llm.base import LLMProvider

_HIGH_SEVERITY_KIND = "email"
_DEFAULT_KIND = "notify"


async def _draft_message(escalation: Escalation, llm: LLMProvider) -> str:
    prompt = (
        f"Write a short, direct one-paragraph management alert message for this escalation. "
        f"Rule: {escalation.rule}. Severity: {escalation.severity}. "
        f"Rationale: {escalation.rationale}. Do not invent facts beyond the rationale."
    )
    result = await llm.chat([{"role": "user", "content": prompt}])
    return result.text


async def plan_action(session: Session, escalation: Escalation, llm: LLMProvider) -> ProposedAction:
    kind = _HIGH_SEVERITY_KIND if escalation.severity == "high" else _DEFAULT_KIND
    body = await _draft_message(escalation, llm)
    payload = {"subject": f"[{escalation.severity.upper()}] {escalation.rule}", "body": body}

    action = ProposedAction(escalation_id=escalation.id, kind=kind, payload=payload, status="pending")
    session.add(action)
    session.flush()

    if kind == "notify":
        execute_action(session, action)
    return action


def execute_action(session: Session, action: ProposedAction, *, decided_by: uuid.UUID | None = None) -> ProposedAction:
    """Executes an approved (or auto-approved "notify") action, then
    records a verify result. Real outbound send is Phase 4 scope; email/
    whatsapp are recorded as a simulated send here."""
    now = datetime.now(tz=UTC)
    action.status = "executing"
    session.flush()

    if action.kind == "notify":
        session.add(Notification(role="manager", title=action.payload.get("subject", ""), body=action.payload.get("body", "")))
        result = {"delivered": True, "channel": "dashboard"}
    else:
        result = {"simulated": True, "channel": action.kind, "would_send": action.payload}

    action.status = "executed"
    action.result = result
    action.decided_by = decided_by
    action.decided_at = now
    session.flush()
    return action


def reject_action(session: Session, action: ProposedAction, *, decided_by: uuid.UUID, feedback: str | None = None) -> ProposedAction:
    action.status = "rejected"
    action.decided_by = decided_by
    action.decided_at = datetime.now(tz=UTC)
    if feedback:
        action.edit = {"feedback": feedback}
    session.flush()
    return action
