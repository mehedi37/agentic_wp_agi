import uuid

from app.db.models import Chat, Item, Participant
from app.memory.consolidation import consolidate_memory


async def test_entities_merge_across_chats_and_report_workload(client, db_session, analyst_token):
    from app.llm.embeddings import FakeEmbeddingProvider

    # A name unique to this test run: the DB is shared across test runs
    # (db_session.commit() persists, it isn't rolled back), and "Nadia" is
    # also a character in the committed sample data, so a fixed name would
    # pick up unrelated chats/items from other runs.
    name = f"Nadia-{uuid.uuid4()}"
    chat_a = Chat(source="export", name="Chat A", type="group", timezone="Asia/Dhaka")
    chat_b = Chat(source="export", name="Chat B", type="group", timezone="Asia/Dhaka")
    db_session.add_all([chat_a, chat_b])
    db_session.flush()
    nadia_a = Participant(chat_id=chat_a.id, display_name=name)
    nadia_b = Participant(chat_id=chat_b.id, display_name=name)
    db_session.add_all([nadia_a, nadia_b])
    db_session.flush()
    db_session.add_all([
        Item(type="action", title="Confirm delivery", chat_id=chat_a.id, owner_participant_id=nadia_a.id,
             status="open", validation_status="passed"),
        Item(type="action", title="Wiring check", chat_id=chat_b.id, owner_participant_id=nadia_b.id,
             status="open", validation_status="passed"),
        Item(type="action", title="Old, done", chat_id=chat_b.id, owner_participant_id=nadia_b.id,
             status="done", validation_status="passed"),
    ])
    db_session.commit()

    await consolidate_memory(db_session, FakeEmbeddingProvider())
    db_session.commit()

    response = client.get("/api/entities", params={"kind": "person"},
                          headers={"Authorization": f"Bearer {analyst_token}"})
    assert response.status_code == 200
    people = {row["name"]: row for row in response.json()}
    assert name in people
    nadia = people[name]
    assert nadia["workload"] == 2
    assert sorted(nadia["profile"]["chat_ids"]) == sorted([str(chat_a.id), str(chat_b.id)])

    detail = client.get(f"/api/entities/{nadia['id']}", headers={"Authorization": f"Bearer {analyst_token}"})
    assert detail.status_code == 200 and detail.json()["name"] == name


async def test_get_entity_404(client, db_session, analyst_token):
    response = client.get(f"/api/entities/{'0' * 8}-0000-0000-0000-{'0' * 12}",
                          headers={"Authorization": f"Bearer {analyst_token}"})
    assert response.status_code == 404


async def test_entities_require_auth(client):
    assert client.get("/api/entities").status_code == 401
