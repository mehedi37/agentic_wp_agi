from app.services.participants import get_or_create_participant, resolve_participant


def test_creates_new_participant(db_session, seed_chat):
    p = get_or_create_participant(db_session, seed_chat.id, "Rafi")
    db_session.flush()
    assert p.display_name == "Rafi"
    assert p.chat_id == seed_chat.id


def test_returns_existing_participant_case_insensitive(db_session, seed_chat):
    p1 = get_or_create_participant(db_session, seed_chat.id, "Rafi")
    db_session.flush()
    p2 = get_or_create_participant(db_session, seed_chat.id, "rafi")
    assert p1.id == p2.id


def test_same_name_different_chats_are_different_participants(db_session, seed_chat, seed_chat_2):
    p1 = get_or_create_participant(db_session, seed_chat.id, "Rafi")
    p2 = get_or_create_participant(db_session, seed_chat_2.id, "Rafi")
    db_session.flush()
    assert p1.id != p2.id


def test_resolves_exact_name(db_session, seed_chat):
    get_or_create_participant(db_session, seed_chat.id, "Rafi bhai")
    db_session.flush()
    result = resolve_participant("Rafi bhai", seed_chat.id, db_session)
    assert result is not None and result.display_name == "Rafi bhai"


def test_resolves_fuzzy_close_match(db_session, seed_chat):
    get_or_create_participant(db_session, seed_chat.id, "Rafiqul Islam")
    db_session.flush()
    result = resolve_participant("Rafiqul", seed_chat.id, db_session)
    assert result is not None and result.display_name == "Rafiqul Islam"


def test_at_mention_stripped(db_session, seed_chat):
    get_or_create_participant(db_session, seed_chat.id, "Nadia")
    db_session.flush()
    result = resolve_participant("@Nadia", seed_chat.id, db_session)
    assert result is not None and result.display_name == "Nadia"


def test_no_match_returns_none(db_session, seed_chat):
    result = resolve_participant("Someone Totally Unknown", seed_chat.id, db_session)
    assert result is None


def test_ambiguous_match_returns_none(db_session, seed_chat):
    get_or_create_participant(db_session, seed_chat.id, "Rahim")
    get_or_create_participant(db_session, seed_chat.id, "Rahul")
    db_session.flush()
    result = resolve_participant("Rah", seed_chat.id, db_session)
    assert result is None
