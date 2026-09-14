import uuid

from app.agents.action import execute_action, plan_action, reject_action
from app.core.security import hash_password
from app.db.models import Escalation, Notification, User
from app.llm.fake_provider import FakeProvider


def _make_escalation(db_session, seed_chat, severity="medium"):
    esc = Escalation(
        rule="overdue_action", severity=severity, chat_id=seed_chat.id, rationale="Test rationale", status="open"
    )
    db_session.add(esc)
    db_session.flush()
    return esc


def _make_manager(db_session) -> User:
    user = User(
        email=f"manager-{uuid.uuid4()}@example.com", name="Manager", role="manager",
        password_hash=hash_password("x"),
    )
    db_session.add(user)
    db_session.flush()
    return user


async def test_medium_severity_auto_executes_as_notify(db_session, seed_chat):
    esc = _make_escalation(db_session, seed_chat, severity="medium")
    llm = FakeProvider(responses=["Please review this overdue item."])

    action = await plan_action(db_session, esc, llm)
    db_session.flush()

    assert action.kind == "notify"
    assert action.status == "executed"
    notif = db_session.query(Notification).filter(Notification.title.like("%overdue_action%")).one_or_none()
    assert notif is not None


async def test_high_severity_stays_pending_for_approval(db_session, seed_chat):
    esc = _make_escalation(db_session, seed_chat, severity="high")
    llm = FakeProvider(responses=["Urgent: please review."])

    action = await plan_action(db_session, esc, llm)
    db_session.flush()

    assert action.kind == "email"
    assert action.status == "pending"


async def test_execute_action_marks_executed_with_decided_by(db_session, seed_chat):
    esc = _make_escalation(db_session, seed_chat, severity="high")
    llm = FakeProvider(responses=["Urgent."])
    action = await plan_action(db_session, esc, llm)
    db_session.flush()

    manager = _make_manager(db_session)
    execute_action(db_session, action, decided_by=manager.id)
    db_session.flush()

    assert action.status == "executed"
    assert action.decided_by == manager.id
    assert action.result is not None


async def test_reject_action_marks_rejected_with_feedback(db_session, seed_chat):
    esc = _make_escalation(db_session, seed_chat, severity="high")
    llm = FakeProvider(responses=["Urgent."])
    action = await plan_action(db_session, esc, llm)
    db_session.flush()

    manager = _make_manager(db_session)
    reject_action(db_session, action, decided_by=manager.id, feedback="not needed right now")
    db_session.flush()

    assert action.status == "rejected"
    assert action.edit == {"feedback": "not needed right now"}
