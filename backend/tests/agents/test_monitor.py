from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.agents.monitor import run_monitor
from app.db.models import Escalation, Item

TZ = ZoneInfo("Asia/Dhaka")


def test_creates_escalation_for_overdue_action(db_session, seed_chat):
    past = datetime.now(tz=TZ) - timedelta(days=1)
    item = Item(type="action", title="Send report", chat_id=seed_chat.id, status="open", due_at=past)
    db_session.add(item)
    db_session.flush()

    created = run_monitor(db_session, chat_id=seed_chat.id)
    assert len(created) == 1
    assert created[0].rule == "overdue_action"
    assert created[0].status == "open"


def test_does_not_duplicate_escalation_on_second_run(db_session, seed_chat):
    past = datetime.now(tz=TZ) - timedelta(days=1)
    item = Item(type="action", title="Send report", chat_id=seed_chat.id, status="open", due_at=past)
    db_session.add(item)
    db_session.flush()

    run_monitor(db_session, chat_id=seed_chat.id)
    db_session.flush()
    second_run = run_monitor(db_session, chat_id=seed_chat.id)
    assert second_run == []

    total = db_session.query(Escalation).filter(Escalation.chat_id == seed_chat.id).count()
    assert total == 1


def test_auto_closes_escalation_when_action_marked_done(db_session, seed_chat):
    past = datetime.now(tz=TZ) - timedelta(days=1)
    item = Item(type="action", title="Send report", chat_id=seed_chat.id, status="open", due_at=past)
    db_session.add(item)
    db_session.flush()

    run_monitor(db_session, chat_id=seed_chat.id)
    db_session.flush()

    item.status = "done"
    db_session.flush()
    run_monitor(db_session, chat_id=seed_chat.id)
    db_session.flush()

    escalation = db_session.query(Escalation).filter(Escalation.chat_id == seed_chat.id).one()
    assert escalation.status == "auto_closed"
