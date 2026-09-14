from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.db.models import Item, Segment
from app.services.escalation_rules import (
    detect_overdue_actions,
    detect_recurring_issue,
    detect_sentiment_dip,
    detect_unowned_high_risk,
)

TZ = ZoneInfo("Asia/Dhaka")


def test_detects_overdue_action(db_session, seed_chat):
    past = datetime.now(tz=TZ) - timedelta(days=2)
    item = Item(type="action", title="Send report", chat_id=seed_chat.id, status="open", due_at=past)
    db_session.add(item)
    db_session.flush()

    candidates = detect_overdue_actions(db_session, chat_id=seed_chat.id)
    assert len(candidates) == 1
    assert candidates[0].rule == "overdue_action"
    assert candidates[0].item_id == item.id


def test_does_not_flag_done_action_even_if_overdue(db_session, seed_chat):
    past = datetime.now(tz=TZ) - timedelta(days=2)
    item = Item(type="action", title="Send report", chat_id=seed_chat.id, status="done", due_at=past)
    db_session.add(item)
    db_session.flush()

    assert detect_overdue_actions(db_session, chat_id=seed_chat.id) == []


def test_does_not_flag_action_without_due_date(db_session, seed_chat):
    item = Item(type="action", title="Send report", chat_id=seed_chat.id, status="open", due_at=None)
    db_session.add(item)
    db_session.flush()

    assert detect_overdue_actions(db_session, chat_id=seed_chat.id) == []


def test_detects_unowned_high_risk(db_session, seed_chat):
    item = Item(type="risk", title="Fire hazard", chat_id=seed_chat.id, severity="high")
    db_session.add(item)
    db_session.flush()

    candidates = detect_unowned_high_risk(db_session, chat_id=seed_chat.id)
    assert len(candidates) == 1
    assert candidates[0].item_id == item.id


def test_does_not_flag_owned_high_risk(db_session, seed_chat):
    item = Item(type="risk", title="Fire hazard", chat_id=seed_chat.id, severity="high", owner_raw="Rahim")
    db_session.add(item)
    db_session.flush()

    assert detect_unowned_high_risk(db_session, chat_id=seed_chat.id) == []


def test_does_not_flag_low_severity_risk(db_session, seed_chat):
    item = Item(type="risk", title="Minor thing", chat_id=seed_chat.id, severity="low")
    db_session.add(item)
    db_session.flush()

    assert detect_unowned_high_risk(db_session, chat_id=seed_chat.id) == []


def _make_issue_with_segment(db_session, seed_chat, title, ts):
    seg = Segment(chat_id=seed_chat.id, start_ts=ts, end_ts=ts)
    db_session.add(seg)
    db_session.flush()
    item = Item(type="issue", title=title, chat_id=seed_chat.id, segment_id=seg.id)
    db_session.add(item)
    db_session.flush()
    return item


def test_detects_recurring_issue_three_similar_within_window(db_session, seed_chat):
    base = datetime.now(tz=TZ)
    _make_issue_with_segment(db_session, seed_chat, "Warehouse roof leaking", base)
    _make_issue_with_segment(db_session, seed_chat, "Warehouse roof leaking again", base + timedelta(days=1))
    _make_issue_with_segment(db_session, seed_chat, "Warehouse roof leaking badly", base + timedelta(days=2))

    candidates = detect_recurring_issue(db_session, chat_id=seed_chat.id)
    assert len(candidates) == 1
    assert candidates[0].rule == "recurring_issue"


def test_two_similar_issues_do_not_trigger_recurring(db_session, seed_chat):
    base = datetime.now(tz=TZ)
    _make_issue_with_segment(db_session, seed_chat, "Warehouse roof leaking", base)
    _make_issue_with_segment(db_session, seed_chat, "Warehouse roof leaking again", base + timedelta(days=1))

    assert detect_recurring_issue(db_session, chat_id=seed_chat.id) == []


def test_dissimilar_issues_do_not_cluster(db_session, seed_chat):
    base = datetime.now(tz=TZ)
    _make_issue_with_segment(db_session, seed_chat, "Warehouse roof leaking", base)
    _make_issue_with_segment(db_session, seed_chat, "Client payment delayed", base + timedelta(days=1))
    _make_issue_with_segment(db_session, seed_chat, "Forklift battery dead", base + timedelta(days=2))

    assert detect_recurring_issue(db_session, chat_id=seed_chat.id) == []


def test_detects_sentiment_dip_three_negative_segments_in_a_row(db_session, seed_chat):
    base = datetime.now(tz=TZ)
    for i in range(3):
        db_session.add(
            Segment(
                chat_id=seed_chat.id, start_ts=base + timedelta(hours=i), end_ts=base + timedelta(hours=i),
                sentiment="negative",
            )
        )
    db_session.flush()

    candidates = detect_sentiment_dip(db_session, chat_id=seed_chat.id)
    assert len(candidates) == 1
    assert candidates[0].rule == "sentiment_dip"


def test_no_dip_when_mixed_sentiment(db_session, seed_chat):
    base = datetime.now(tz=TZ)
    sentiments = ["negative", "positive", "negative"]
    for i, sentiment in enumerate(sentiments):
        db_session.add(
            Segment(
                chat_id=seed_chat.id, start_ts=base + timedelta(hours=i), end_ts=base + timedelta(hours=i),
                sentiment=sentiment,
            )
        )
    db_session.flush()

    assert detect_sentiment_dip(db_session, chat_id=seed_chat.id) == []
