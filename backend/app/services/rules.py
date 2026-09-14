"""Validated, persistent monitor configuration."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Rule

DEFAULT_RULES = {
    "overdue_action": {},
    "unowned_high_risk": {},
    "recurring_issue": {"window_days": 7, "min_count": 3},
    "sentiment_dip": {"streak": 3},
}


def rule_config(session: Session, key: str) -> tuple[bool, dict]:
    rule = session.scalar(select(Rule).where(Rule.key == key))
    return (rule.enabled, {**DEFAULT_RULES[key], **rule.params}) if rule else (True, DEFAULT_RULES[key])
