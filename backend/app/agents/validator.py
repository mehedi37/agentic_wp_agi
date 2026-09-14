from difflib import SequenceMatcher
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Message, Segment
from app.llm.base import LLMProvider
from app.schemas.item import ExtractedItem
from app.schemas.validation import ItemVerdict, ValidationIssue, ValidationReport
from app.services.items import find_update_target

_JUDGE_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "validator_judge_system.md").read_text()
_QUOTE_MATCH_THRESHOLD = 0.8
_JUDGE_CONFIDENCE_THRESHOLD = 0.5


class _JudgeOutput(BaseModel):
    confidence: float


def _quote_grounded(quote: str, message_text: str) -> bool:
    if not quote.strip():
        return False
    if quote in message_text:
        return True
    return SequenceMatcher(None, quote, message_text).ratio() >= _QUOTE_MATCH_THRESHOLD


async def run_validator(
    session: Session, *, segment: Segment, items: list[ExtractedItem], judge_llm: LLMProvider
) -> ValidationReport:
    segment_messages = {
        m.id: m for m in session.scalars(select(Message).where(Message.id.in_(segment.message_ids)))
    }

    verdicts: list[ItemVerdict] = []
    all_issues: list[ValidationIssue] = []

    for idx, item in enumerate(items):
        issues: list[ValidationIssue] = []
        if item.related_item_id and find_update_target(session, segment, item) is None:
            issues.append(ValidationIssue(item_index=idx, field="related_item_id",
                message="related item must exist in the same chat and have the same type"))
        if item.confidence < 0.6:
            issues.append(ValidationIssue(item_index=idx, field="confidence",
                                          message="low confidence requires human review"))

        if not item.evidence:
            issues.append(ValidationIssue(item_index=idx, field="evidence", message="no evidence cited"))
        for ev in item.evidence:
            source = segment_messages.get(ev.message_id)
            if source is None:
                issues.append(
                    ValidationIssue(
                        item_index=idx, field="evidence",
                        message=f"cited message {ev.message_id} is not in this segment",
                    )
                )
                continue
            if not _quote_grounded(ev.quote, source.text):
                issues.append(
                    ValidationIssue(
                        item_index=idx, field="evidence",
                        message=f"quote not found in message {ev.message_id}",
                    )
                )

        judge_confidence = None
        if not issues:
            judge_result = await judge_llm.structured(
                [{"role": "user", "content": f"Item: {item.title}. Evidence: {[e.quote for e in item.evidence]}"}],
                response_model=_JudgeOutput,
                system=_JUDGE_SYSTEM_PROMPT,
            )
            judge_confidence = judge_result.confidence
            if judge_confidence < _JUDGE_CONFIDENCE_THRESHOLD:
                issues.append(
                    ValidationIssue(
                        item_index=idx, field=None,
                        message=f"judge confidence {judge_confidence:.2f} below threshold",
                    )
                )

        passed = not issues
        verdicts.append(ItemVerdict(item_index=idx, passed=passed, confidence=judge_confidence, issues=issues))
        all_issues.extend(issues)

    # `all()` on an empty list is True: a segment with zero extracted items
    # (pure small talk) is a valid, passing outcome -- nothing to validate.
    overall_passed = all(v.passed for v in verdicts)
    feedback = None
    if not overall_passed:
        lines = [f"item {i + 1}: {issue.message}" for i, v in enumerate(verdicts) for issue in v.issues]
        feedback = "; ".join(lines)

    return ValidationReport(
        passed=overall_passed, issues=all_issues, per_item_verdicts=verdicts, feedback=feedback
    )
