import uuid

import pytest
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.db.models import Chat, Escalation, ProposedAction, User


@pytest.fixture()
def manager_user(db_session: Session):
    user = User(
        email=f"actions-manager-{uuid.uuid4()}@example.com", name="Manager", role="manager",
        password_hash=hash_password("x"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def manager_token(manager_user: User) -> str:
    return create_access_token(manager_user.id, manager_user.role)


@pytest.fixture()
def pending_action(db_session: Session):
    chat = Chat(source="export", name="Actions Test Chat", type="group", timezone="Asia/Dhaka")
    db_session.add(chat)
    db_session.flush()
    esc = Escalation(rule="overdue_action", severity="high", chat_id=chat.id, rationale="r", status="open")
    db_session.add(esc)
    db_session.flush()
    action = ProposedAction(
        escalation_id=esc.id, kind="email", payload={"subject": "s", "body": "b"}, status="pending"
    )
    db_session.add(action)
    db_session.commit()
    db_session.refresh(action)
    return action


def test_manager_can_approve(client, manager_token, pending_action, db_session):
    resp = client.post(
        f"/api/actions/{pending_action.id}/approve", headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "executed"


def test_analyst_cannot_approve(client, analyst_token, pending_action):
    resp = client.post(
        f"/api/actions/{pending_action.id}/approve", headers={"Authorization": f"Bearer {analyst_token}"}
    )
    assert resp.status_code == 403


def test_manager_can_reject_with_feedback(client, manager_token, pending_action):
    resp = client.post(
        f"/api/actions/{pending_action.id}/reject",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"feedback": "not needed"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_approving_twice_returns_409(client, manager_token, pending_action):
    client.post(f"/api/actions/{pending_action.id}/approve", headers={"Authorization": f"Bearer {manager_token}"})
    resp = client.post(
        f"/api/actions/{pending_action.id}/approve", headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert resp.status_code == 409


def test_list_actions_requires_auth(client):
    resp = client.get("/api/actions")
    assert resp.status_code == 401


def test_list_actions_filters_by_status(client, analyst_token, pending_action):
    resp = client.get("/api/actions?action_status=pending", headers={"Authorization": f"Bearer {analyst_token}"})
    assert resp.status_code == 200
    assert any(a["id"] == str(pending_action.id) for a in resp.json())
