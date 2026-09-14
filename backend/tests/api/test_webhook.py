import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock

from sqlalchemy import select

from app.core.config import settings
from app.db.models import Message


def payload():
    return {"object": "whatsapp_business_account", "entry": [{"changes": [{"field": "messages",
        "value": {"metadata": {"phone_number_id": "test-business"}, "messages": [{
            "from": "8801700000001", "id": f"wamid.{uuid.uuid4()}", "timestamp": "1773302400",
            "type": "text", "text": {"body": "Rafi will send the stock report tomorrow"}}]}}]}]}


def post(client, data):
    body = json.dumps(data).encode()
    signature = hmac.new(settings.whatsapp_app_secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post("/api/webhook", content=body, headers={"X-Hub-Signature-256": f"sha256={signature}"})


def test_verification_and_signature(client):
    response = client.get("/api/webhook", params={"hub.mode": "subscribe",
        "hub.verify_token": settings.whatsapp_verify_token, "hub.challenge": "1234"})
    assert response.status_code == 200 and response.text == "1234"
    assert client.post("/api/webhook", json=payload()).status_code == 401


def test_signed_replay_is_idempotent_and_requeues(client, db_session, monkeypatch):
    enqueue = AsyncMock()
    monkeypatch.setattr("app.api.routes.webhook.enqueue_process_batch", enqueue)
    data = payload()
    assert post(client, data).json()["inserted"] == 1
    assert post(client, data).json()["inserted"] == 0
    assert enqueue.await_count == 2
    source_id = data["entry"][0]["changes"][0]["value"]["messages"][0]["id"]
    message = db_session.scalar(select(Message).where(Message.source_message_id == source_id))
    assert message.text == "Rafi will send the stock report tomorrow"
    assert message.raw is None


def test_valid_signature_does_not_make_malformed_payload_valid(client, db_session):
    assert post(client, {"object": "wrong"}).status_code == 422
