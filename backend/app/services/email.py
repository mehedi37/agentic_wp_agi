import smtplib
from email.message import EmailMessage

from app.core.config import settings


def send_email(payload: dict, action_id: str) -> dict:
    recipient = payload.get("to") or settings.digest_recipient
    if settings.email_mode == "simulated":
        return {"channel": "email", "simulated": True, "delivered": False, "recipient": recipient}
    if settings.email_mode != "smtp":
        raise ValueError("Unsupported email mode")
    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = recipient
    message["Subject"] = payload.get("subject", "Management alert")
    message["Message-ID"] = f"<{action_id}@dashboard.local>"
    message.set_content(payload.get("body", ""))
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        refused = smtp.send_message(message)
    if refused:
        raise ValueError("SMTP rejected one or more recipients")
    return {"channel": "email", "simulated": False, "accepted": True,
            "delivered": False, "message_id": message["Message-ID"]}
