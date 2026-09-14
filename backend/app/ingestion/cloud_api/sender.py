import httpx

from app.core.config import settings


def send_whatsapp(payload: dict, action_id: str) -> dict:
    if settings.whatsapp_mode == "simulated":
        return {"channel": "whatsapp", "simulated": True, "message_id": f"simulated.{action_id}",
                "delivery_status": "simulated", "delivered": False}
    if settings.whatsapp_mode != "live":
        raise ValueError("Unsupported WhatsApp mode")
    if not all((settings.whatsapp_phone_number_id, settings.whatsapp_access_token, payload.get("to"))):
        raise ValueError("WhatsApp credentials and recipient are required")
    url = (f"https://graph.facebook.com/{settings.whatsapp_api_version}/"
           f"{settings.whatsapp_phone_number_id}/messages")
    with httpx.Client(timeout=15) as client:
        response = client.post(url, headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            json={"messaging_product": "whatsapp", "to": payload["to"], "type": "text",
                  "text": {"body": payload.get("body", "")}})
        response.raise_for_status()
    return {"channel": "whatsapp", "simulated": False, "delivered": False,
            "delivery_status": "accepted", "message_id": response.json()["messages"][0]["id"]}
