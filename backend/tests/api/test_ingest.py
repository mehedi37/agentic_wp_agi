import io

from app.db.models import Chat


def test_upload_creates_chat_and_ingests(client, analyst_token, db_session):
    text = "12/03/2026, 9:41 AM - Rafi: kal delivery hobe"
    resp = client.post(
        "/api/ingest/upload",
        headers={"Authorization": f"Bearer {analyst_token}"},
        data={"chat_name": "New Chat", "date_order": "DMY"},
        files={"file": ("chat.txt", io.BytesIO(text.encode()), "text/plain")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 1
    chat = db_session.get(Chat, body["chat_id"])
    assert chat.name == "New Chat" and chat.source == "export"


def test_upload_requires_auth(client):
    resp = client.post("/api/ingest/upload", files={"file": ("chat.txt", io.BytesIO(b""), "text/plain")})
    assert resp.status_code == 401


def test_upload_bad_zip_returns_422(client, analyst_token):
    resp = client.post(
        "/api/ingest/upload",
        headers={"Authorization": f"Bearer {analyst_token}"},
        data={"chat_name": "Bad"},
        files={"file": ("chat.zip", io.BytesIO(b"not a zip"), "application/zip")},
    )
    assert resp.status_code == 422
