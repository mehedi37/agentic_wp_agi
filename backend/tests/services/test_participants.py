from app.services.participants import get_or_create_participant


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
