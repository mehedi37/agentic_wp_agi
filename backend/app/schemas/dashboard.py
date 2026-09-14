from pydantic import BaseModel


class DashboardMetrics(BaseModel):
    open_actions: int
    overdue_actions: int
    new_risks_7d: int
    decisions_7d: int
    open_escalations: int
    pending_approvals: int
