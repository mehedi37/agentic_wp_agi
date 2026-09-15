from app.db.models import Chat, Escalation


async def test_weekly_report_is_a_pdf(client, db_session, analyst_token):
    chat = Chat(source="export", name="Reports Test Chat", type="group", timezone="Asia/Dhaka")
    db_session.add(chat)
    db_session.flush()
    db_session.add(Escalation(rule="overdue_action", severity="high", chat_id=chat.id,
                              rationale="Delivery is 3 days overdue", status="open"))
    db_session.commit()

    response = client.get("/api/reports/weekly.pdf", headers={"Authorization": f"Bearer {analyst_token}"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert "weekly-management-brief.pdf" in response.headers["content-disposition"]


async def test_weekly_report_requires_auth(client):
    assert client.get("/api/reports/weekly.pdf").status_code == 401
