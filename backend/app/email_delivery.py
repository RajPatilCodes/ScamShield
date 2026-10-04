import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

from fastapi import HTTPException

from .config import settings


@dataclass(frozen=True)
class CapturedEmail:
    recipient: str
    purpose: str
    token: str


# Development/test delivery only: no token logging, public route, or durable capture.
captures: list[CapturedEmail] = []


def deliver_challenge(email: str, purpose: str, token: str):
    if settings.email_adapter == "capture" and settings.environment != "production":
        captures.append(CapturedEmail(email, purpose, token))
        return
    if settings.email_adapter != "smtp":
        raise HTTPException(status_code=503, detail="Email delivery unavailable")
    message = EmailMessage()
    message["From"] = settings.email_sender
    message["To"] = email
    message["Subject"] = f"ScamShield {purpose}"
    message.set_content(f"Use this single-use {purpose} credential in ScamShield:\n{token}\nIf you did not request this, ignore this email.")
    try:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ssl.create_default_context(), timeout=settings.smtp_timeout_seconds) as smtp:
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        raise HTTPException(status_code=503, detail="Email delivery unavailable") from None
