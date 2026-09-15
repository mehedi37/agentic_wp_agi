from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Escalation, Item, ProposedAction
from app.schemas.dashboard import DashboardMetrics


def compute_dashboard_metrics(session: Session) -> DashboardMetrics:
    now = datetime.now(tz=UTC)
    week_ago = now - timedelta(days=7)

    open_actions = session.scalar(
        select(func.count()).select_from(Item).where(Item.type == "action", Item.status.notin_(["done", "cancelled"]))
    ) or 0
    overdue_actions = session.scalar(
        select(func.count()).select_from(Item).where(
            Item.type == "action", Item.due_at.is_not(None), Item.due_at < now,
            Item.status.notin_(["done", "cancelled"]),
        )
    ) or 0
    new_risks_7d = session.scalar(
        select(func.count()).select_from(Item).where(Item.type == "risk", Item.created_at >= week_ago)
    ) or 0
    decisions_7d = session.scalar(
        select(func.count()).select_from(Item).where(Item.type == "decision", Item.created_at >= week_ago)
    ) or 0
    open_escalations = session.scalar(
        select(func.count()).select_from(Escalation).where(Escalation.status.in_(["open", "acknowledged"]))
    ) or 0
    pending_approvals = session.scalar(
        select(func.count()).select_from(ProposedAction).where(ProposedAction.status == "pending")
    ) or 0

    return DashboardMetrics(
        open_actions=open_actions, overdue_actions=overdue_actions, new_risks_7d=new_risks_7d,
        decisions_7d=decisions_7d, open_escalations=open_escalations, pending_approvals=pending_approvals,
    )
