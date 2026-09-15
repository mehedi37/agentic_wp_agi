"""Weekly management brief, rendered as a downloadable PDF (T5.3)."""
import io
from datetime import UTC, datetime, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Escalation, Item
from app.services.dashboard import compute_dashboard_metrics

_STYLES = getSampleStyleSheet()
_BODY = ParagraphStyle("body_small", parent=_STYLES["BodyText"], fontSize=9, leading=12)


def _metrics_table(session: Session) -> Table:
    metrics = compute_dashboard_metrics(session)
    rows = [
        ["Metric", "Value"],
        ["Open actions", str(metrics.open_actions)],
        ["Overdue actions", str(metrics.overdue_actions)],
        ["New risks (7d)", str(metrics.new_risks_7d)],
        ["Decisions (7d)", str(metrics.decisions_7d)],
        ["Open escalations", str(metrics.open_escalations)],
        ["Pending approvals", str(metrics.pending_approvals)],
    ]
    table = Table(rows, colWidths=[8 * cm, 4 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
    ]))
    return table


def _open_escalations_table(session: Session, limit: int = 15) -> Table:
    rows: list[list] = [["Rule", "Severity", "Rationale"]]
    escalations = session.scalars(
        select(Escalation).where(Escalation.status.in_(["open", "acknowledged"]))
        .order_by(Escalation.created_at.desc()).limit(limit)
    )
    for esc in escalations:
        rows.append([esc.rule, esc.severity, Paragraph(esc.rationale or "", _BODY)])
    if len(rows) == 1:
        rows.append(["—", "—", "No open escalations"])
    table = Table(rows, colWidths=[3.5 * cm, 2.5 * cm, 8 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
    ]))
    return table


def _overdue_actions_table(session: Session, limit: int = 15) -> Table:
    now = datetime.now(tz=UTC)
    rows: list[list] = [["Action", "Owner", "Due"]]
    items = session.scalars(
        select(Item).where(
            Item.type == "action", Item.due_at.is_not(None), Item.due_at < now,
            Item.status.notin_(["done", "cancelled"]),
        ).order_by(Item.due_at).limit(limit)
    )
    for item in items:
        rows.append([Paragraph(item.title, _BODY), item.owner_raw or "unassigned",
                     item.due_at.strftime("%Y-%m-%d") if item.due_at else "—"])
    if len(rows) == 1:
        rows.append(["—", "—", "No overdue actions"])
    table = Table(rows, colWidths=[8 * cm, 3.5 * cm, 2.5 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
    ]))
    return table


def build_weekly_report_pdf(session: Session) -> bytes:
    """Renders a management brief: current KPIs, open escalations, overdue actions.

    Deterministic and dependency-free of any LLM call, so it works
    identically under LLM_PROVIDER=fake and needs no extra approval or
    generation step -- it is a report over data the pipeline already
    produced, not a new agent output.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    now = datetime.now(tz=UTC)
    period = f"{(now - timedelta(days=7)).strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}"

    story = [
        Paragraph("Weekly Management Brief", _STYLES["Title"]),
        Paragraph(f"Period: {period} · Generated {now.strftime('%Y-%m-%d %H:%M UTC')}", _STYLES["Normal"]),
        Spacer(1, 0.6 * cm),
        Paragraph("Key metrics", _STYLES["Heading2"]),
        _metrics_table(session),
        Spacer(1, 0.6 * cm),
        Paragraph("Open escalations", _STYLES["Heading2"]),
        _open_escalations_table(session),
        Spacer(1, 0.6 * cm),
        Paragraph("Overdue actions", _STYLES["Heading2"]),
        _overdue_actions_table(session),
    ]
    doc.build(story)
    return buffer.getvalue()
