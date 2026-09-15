"""Replay signed WhatsApp Cloud API webhook fixtures against a running backend.

Demonstrates the Cloud API ingestion path (T4.1) without a real Meta app:
each fixture in `data/sample/webhook_fixtures/*.json` is HMAC-signed with the
same `WHATSAPP_APP_SECRET` the backend verifies against, then POSTed to
`POST /api/webhook`. Run after `make up` (and optionally `make seed`):

    cd backend && uv run python -m scripts.simulate_webhook
"""
import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path

import httpx

from app.core.config import settings

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api")
SAMPLES = Path(os.environ.get("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[2] / "data" / "sample")))


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(settings.whatsapp_app_secret.encode(), body, hashlib.sha256).hexdigest()


def main() -> None:
    fixtures = sorted((SAMPLES / "webhook_fixtures").glob("*.json"))
    if not fixtures:
        raise FileNotFoundError(f"No webhook fixtures found under {SAMPLES / 'webhook_fixtures'}")

    with httpx.Client(timeout=10) as client:
        verify = client.get(f"{API_BASE_URL}/webhook", params={
            "hub.mode": "subscribe", "hub.verify_token": settings.whatsapp_verify_token,
            "hub.challenge": "simulate-webhook",
        })
        verify.raise_for_status()
        print(f"Verify handshake OK: {verify.text}")

        for fixture in fixtures:
            body = fixture.read_bytes()
            # Fixture timestamps are fixed for readability; stamp "now" so
            # ingested messages sort naturally alongside a freshly seeded demo.
            payload = json.loads(body)
            now = int(time.time())
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    for msg in change["value"].get("messages", []):
                        msg["timestamp"] = str(now)
                    for status in change["value"].get("statuses", []):
                        status["timestamp"] = str(now)
            body = json.dumps(payload).encode()

            response = client.post(f"{API_BASE_URL}/webhook", content=body,
                headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"})
            print(f"{fixture.name}: {response.status_code} {response.json() if response.is_success else response.text}")
            if not response.is_success:
                sys.exit(1)


if __name__ == "__main__":
    main()
