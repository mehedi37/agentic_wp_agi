from datetime import UTC, datetime, timedelta

from app.db.models import Chat, Escalation, Item, ProposedAction


async def test_metrics_reflect_seeded_state(client, db_session, analyst_token):
    chat = Chat(source="export", name="Dashboard Test Chat", type="group", timezone="Asia/Dhaka")
    db_session.add(chat)
    db_session.flush()
    past_due = datetime.now(tz=UTC) - timedelta(days=1)
    db_session.add_all([
        Item(type="action", title="Overdue", chat_id=chat.id, status="open",
             due_at=past_due, validation_status="passed"),
        Item(type="risk", title="New risk", chat_id=chat.id, status="open", validation_status="passed"),
        Item(type="decision", title="Approved", chat_id=chat.id, status="open", validation_status="passed"),
    ])
    esc = Escalation(rule="overdue_action", severity="high", chat_id=chat.id, rationale="r", status="open")
    db_session.add(esc)
    db_session.flush()
    db_session.add(ProposedAction(escalation_id=esc.id, kind="notify", payload={}, status="pending"))
    db_session.commit()

    response = client.get("/api/dashboard/metrics", headers={"Authorization": f"Bearer {analyst_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["open_actions"] >= 1
    assert body["overdue_actions"] >= 1
    assert body["new_risks_7d"] >= 1
    assert body["decisions_7d"] >= 1
    assert body["open_escalations"] >= 1
    assert body["pending_approvals"] >= 1


async def test_metrics_require_auth(client):
    assert client.get("/api/dashboard/metrics").status_code == 401
