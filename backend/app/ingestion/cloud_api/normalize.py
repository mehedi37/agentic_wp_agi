"""Normalize authenticated Cloud API events without storing raw phone numbers."""
import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import Chat, Message, ProposedAction
from app.services.participants import get_or_create_participant


def ingest_webhook(session: Session, payload: dict) -> tuple[int, set[uuid.UUID]]:
    inserted = 0
    chats: set[uuid.UUID] = set()
    if payload.get("object") != "whatsapp_business_account":
        raise ValueError("Expected whatsapp_business_account object")
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "messages":
                continue
            value = change["value"]
            business_number = value.get("metadata", {}).get("phone_number_id", "")
            for status in value.get("statuses", []):
                action = session.scalar(select(ProposedAction).where(
                    ProposedAction.result["message_id"].astext == status["id"]).with_for_update())
                if action is not None and status.get("status") in ("sent", "delivered", "read", "failed"):
                    previous = (action.result or {}).get("delivery_status")
                    incoming = status["status"]
                    rank = {None: 0, "accepted": 0, "sent": 1, "failed": 2, "delivered": 3, "read": 4}
                    if rank.get(incoming, 0) >= rank.get(previous, 0):
                        action.result = {**(action.result or {}), "delivery_status": incoming,
                                         "delivered": incoming in ("delivered", "read")}
                        action.status = "failed" if incoming == "failed" else "executed"
            for raw in value.get("messages", []):
                sender, source_id = str(raw["from"]), str(raw["id"])
                if not sender or not source_id or not business_number:
                    raise ValueError("Missing message identity")
                identity = hashlib.sha256(f"{business_number}|{sender}".encode()).hexdigest()
                lock_id = int(identity[:15], 16)
                session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
                chat = session.scalar(select(Chat).where(Chat.source == "cloud_api", Chat.external_id == identity))
                if chat is None:
                    chat = Chat(source="cloud_api", external_id=identity, name=f"WhatsApp ••••{sender[-4:]}",
                                type="direct", timezone="Asia/Dhaka")
                    session.add(chat)
                    session.flush()
                # Re-enqueue on replay too: the previous request may have committed before Redis failed.
                chats.add(chat.id)
                digest = hashlib.sha256(f"cloud_api|{business_number}|{source_id}".encode()).hexdigest()
                if session.scalar(select(Message.id).where(Message.content_hash == digest)):
                    continue
                participant = get_or_create_participant(session, chat.id, f"••••{sender[-4:]}")
                participant.phone_hash = hashlib.sha256(sender.encode()).hexdigest()
                participant.phone_masked = f"••••{sender[-4:]}"
                kind = raw.get("type", "unknown")
                body = raw.get("text", {}).get("body") if kind == "text" else None
                if body is None:
                    body = raw.get(kind, {}).get("caption", f"[{kind} omitted]")
                reply = raw.get("context", {}).get("id")
                reply_id = session.scalar(select(Message.id).where(Message.chat_id == chat.id,
                    Message.source_message_id == reply)) if reply else None
                session.add(Message(chat_id=chat.id, participant_id=participant.id,
                    source_message_id=source_id, ts=datetime.fromtimestamp(int(raw["timestamp"]), UTC),
                    text=str(body), media_type=None if kind == "text" else kind,
                    reply_to_id=reply_id, content_hash=digest, is_system=False))
                session.flush()
                inserted += 1
    return inserted, chats
