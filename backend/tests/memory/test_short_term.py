from app.memory.short_term import get_or_create_chat_state, update_rolling_summary


def test_creates_chat_state_on_first_access(db_session, seed_chat):
    state = get_or_create_chat_state(db_session, seed_chat.id)
    db_session.flush()
    assert state.chat_id == seed_chat.id
    assert state.rolling_summary is None


def test_returns_existing_state(db_session, seed_chat):
    s1 = get_or_create_chat_state(db_session, seed_chat.id)
    db_session.flush()
    s2 = get_or_create_chat_state(db_session, seed_chat.id)
    assert s1.chat_id == s2.chat_id


def test_update_rolling_summary_persists(db_session, seed_chat):
    get_or_create_chat_state(db_session, seed_chat.id)
    db_session.flush()
    updated = update_rolling_summary(db_session, seed_chat.id, "Team discussed Padma rollout timeline.")
    db_session.flush()
    assert updated.rolling_summary == "Team discussed Padma rollout timeline."
