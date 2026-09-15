from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.schemas.auth import CurrentUser
from app.schemas.dashboard import DashboardMetrics
from app.services.dashboard import compute_dashboard_metrics

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/metrics", response_model=DashboardMetrics)
def get_metrics(
    _user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)
) -> DashboardMetrics:
    return compute_dashboard_metrics(session)
