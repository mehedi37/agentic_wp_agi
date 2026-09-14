import uuid
from datetime import UTC, datetime

from app.schemas.escalation import EscalationOut
from app.schemas.item import EvidenceRef


def test_escalation_out_evidence_is_list_of_evidence_refs() -> None:
    escalation = EscalationOut(
        id=uuid.uuid4(),
        rule="overdue_action",
        severity="high",
        item_id=uuid.uuid4(),
        chat_id=uuid.uuid4(),
        rationale="Action is 3 days overdue with no progress update.",
        evidence=[EvidenceRef(message_id=uuid.uuid4(), quote="I'll send it tomorrow")],
        status="open",
        created_at=datetime.now(UTC),
    )
    assert len(escalation.evidence or []) == 1
    assert isinstance(escalation.evidence[0], EvidenceRef)


def test_escalation_out_evidence_defaults_to_none() -> None:
    escalation = EscalationOut(
        id=uuid.uuid4(),
        rule="overdue_action",
        severity="high",
        item_id=None,
        chat_id=None,
        rationale="No mitigation owner assigned.",
        evidence=None,
        status="open",
        created_at=datetime.now(UTC),
    )
    assert escalation.evidence is None
