from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Escalation
from app.db.session import get_session
from app.schemas.auth import CurrentUser
from app.schemas.escalation import EscalationOut

router = APIRouter(prefix="/escalations", tags=["escalations"])


@router.get("", response_model=list[EscalationOut])
def list_escalations(
    escalation_status: str | None = None,
    _user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Escalation]:
    query = select(Escalation).order_by(Escalation.created_at.desc())
    if escalation_status is not None:
        query = query.where(Escalation.status == escalation_status)
    return list(session.scalars(query))
