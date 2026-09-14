import hashlib
from unittest.mock import AsyncMock

from app.db.models import Message
from app.services.ingestion import ingest_export


def _content_hash(chat_id, ts, sender, text) -> str:
    return hashlib.sha256(f"{chat_id}|{ts.isoformat()}|{sender}|{text}".encode()).hexdigest()


async def test_ingests_new_android_export(db_session, seed_chat):
    text = (
        "12/03/2026, 9:41 AM - Rafi: kal delivery hobe\n"
        "12/03/2026, 9:42 AM - Nadia: ok thik ache"
    )
    enqueue = AsyncMock()
    stats = await ingest_export(
        db_session,
        chat_id=seed_chat.id,
        filename="chat.txt",
        file_bytes=text.encode(),
        date_order="DMY",
        enqueue=enqueue,
    )
    db_session.commit()
    assert stats.inserted == 2
    assert stats.duplicates == 0
    rows = db_session.query(Message).filter(Message.chat_id == seed_chat.id).all()
    assert len(rows) == 2
    enqueue.assert_awaited_once_with(seed_chat.id)


async def test_reupload_is_idempotent(db_session, seed_chat):
    text = "12/03/2026, 9:41 AM - Rafi: kal delivery hobe"
    enqueue = AsyncMock()
    await ingest_export(
        db_session, chat_id=seed_chat.id, filename="chat.txt", file_bytes=text.encode(),
        date_order="DMY", enqueue=enqueue,
    )
    db_session.commit()
    stats2 = await ingest_export(
        db_session, chat_id=seed_chat.id, filename="chat.txt", file_bytes=text.encode(),
        date_order="DMY", enqueue=enqueue,
    )
    db_session.commit()
    assert stats2.inserted == 0
    assert stats2.duplicates == 1
    rows = db_session.query(Message).filter(Message.chat_id == seed_chat.id).all()
    assert len(rows) == 1


async def test_participants_created_from_senders(db_session, seed_chat):
    text = "12/03/2026, 9:41 AM - Rafi: hi\n12/03/2026, 9:42 AM - Nadia: hey"
    enqueue = AsyncMock()
    await ingest_export(
        db_session, chat_id=seed_chat.id, filename="chat.txt", file_bytes=text.encode(),
        date_order="DMY", enqueue=enqueue,
    )
    db_session.commit()
    from app.db.models import Participant
    names = {p.display_name for p in db_session.query(Participant).filter(Participant.chat_id == seed_chat.id)}
    assert names == {"Rafi", "Nadia"}
