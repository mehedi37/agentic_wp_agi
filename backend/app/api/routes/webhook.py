import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_session
from app.ingestion.cloud_api.normalize import ingest_webhook
from app.workers.queue import enqueue_process_batch

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.get("", response_class=PlainTextResponse)
def verify(mode: str = Query(alias="hub.mode"), token: str = Query(alias="hub.verify_token"),
           challenge: str = Query(alias="hub.challenge")) -> str:
    if mode != "subscribe" or not hmac.compare_digest(token, settings.whatsapp_verify_token):
        raise HTTPException(403, "Invalid verification token")
    return challenge


@router.post("")
async def receive(request: Request, session: Session = Depends(get_session)) -> dict:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 2_000_000:
            raise HTTPException(413, "Webhook payload too large")
    signature = "sha256=" + hmac.new(settings.whatsapp_app_secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, request.headers.get("x-hub-signature-256", "")):
        raise HTTPException(401, "Invalid signature")
    try:
        payload = json.loads(body)
        inserted, chats = ingest_webhook(session, payload)
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
        session.rollback()
        raise HTTPException(422, "Malformed webhook payload") from exc
    session.commit()
    try:
        for chat_id in chats:
            await enqueue_process_batch(chat_id)
    except (RedisError, OSError, TimeoutError) as exc:
        raise HTTPException(503, "Messages stored; retry to queue processing") from exc
    return {"inserted": inserted, "chats": len(chats)}
