from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.schemas.auth import CurrentUser
from app.services.reports import build_weekly_report_pdf

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/weekly.pdf")
def weekly_report_pdf(
    _user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)
) -> Response:
    pdf = build_weekly_report_pdf(session)
    return Response(content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=weekly-management-brief.pdf"})
