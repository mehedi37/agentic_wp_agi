import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.action import execute_action, reject_action
from app.api.deps import get_current_user, require_role
from app.db.models import ProposedAction
from app.db.session import get_session
from app.schemas.action import ProposedActionOut
from app.schemas.auth import CurrentUser

router = APIRouter(prefix="/actions", tags=["actions"])

_require_manager = require_role("manager")


def _get_pending_action(session: Session, action_id: uuid.UUID) -> ProposedAction:
    action = session.get(ProposedAction, action_id)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    if action.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Action is not pending (status={action.status})"
        )
    return action


@router.get("", response_model=list[ProposedActionOut])
def list_actions(
    action_status: str | None = None,
    _user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ProposedAction]:
    query = select(ProposedAction).order_by(ProposedAction.created_at.desc())
    if action_status is not None:
        query = query.where(ProposedAction.status == action_status)
    return list(session.scalars(query))


@router.post("/{action_id}/approve", response_model=ProposedActionOut)
def approve_action(
    action_id: uuid.UUID,
    current_user: CurrentUser = Depends(_require_manager),
    session: Session = Depends(get_session),
) -> ProposedAction:
    action = _get_pending_action(session, action_id)
    execute_action(session, action, decided_by=current_user.id)
    session.commit()
    return action


@router.post("/{action_id}/reject", response_model=ProposedActionOut)
def reject_action_route(
    action_id: uuid.UUID,
    feedback: str | None = Body(default=None, embed=True),
    current_user: CurrentUser = Depends(_require_manager),
    session: Session = Depends(get_session),
) -> ProposedAction:
    action = _get_pending_action(session, action_id)
    reject_action(session, action, decided_by=current_user.id, feedback=feedback)
    session.commit()
    return action
