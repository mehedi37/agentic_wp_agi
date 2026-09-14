from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.models import Rule
from app.db.session import get_session
from app.schemas.auth import CurrentUser
from app.services.audit import record_audit_event
from app.services.rules import DEFAULT_RULES, rule_config

_manager = require_role("manager")

router = APIRouter(prefix="/settings", tags=["settings"])


class RuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    params: dict[str, int] = Field(default_factory=dict)


@router.get("/rules")
def get_rules(_user: CurrentUser = Depends(_manager),
              session: Session = Depends(get_session)) -> list[dict]:
    return [{"key": key, "enabled": enabled, "params": params}
            for key in DEFAULT_RULES for enabled, params in [rule_config(session, key)]]


@router.put("/rules/{key}")
def update_rule(key: str, payload: RuleUpdate,
                user: CurrentUser = Depends(_manager),
                session: Session = Depends(get_session)) -> dict:
    if key not in DEFAULT_RULES:
        raise HTTPException(404, "Unknown monitor rule")
    if set(payload.params) - set(DEFAULT_RULES[key]) or any(
        not 1 <= value <= 365 for value in payload.params.values()
    ):
        raise HTTPException(422, "Use known parameters with values between 1 and 365")
    rule = session.scalar(select(Rule).where(Rule.key == key).with_for_update())
    if rule is None:
        rule = Rule(key=key, params={})
        session.add(rule)
    rule.enabled = payload.enabled
    rule.params = {**DEFAULT_RULES[key], **payload.params}
    record_audit_event(session, user.id, "settings.rule_update", {"key": key, **payload.model_dump()})
    session.commit()
    return {"key": key, "enabled": rule.enabled, "params": rule.params}
