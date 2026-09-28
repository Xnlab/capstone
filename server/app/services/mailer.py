"""SMTP 메일 전송. SMTP_HOST 가 비어 있으면 실제 발송 없이 MOCK 처리."""

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

log = logging.getLogger(__name__)


def send_mail(to: str, subject: str, body: str, attachments: list[tuple[str, bytes, str]]) -> dict:
    """attachments: [(파일명, 바이트, mime subtype)]"""
    if not settings.SMTP_HOST:
        log.info("[MOCK MAIL] to=%s subject=%s files=%s", to, subject, [a[0] for a in attachments])
        return {"sent": True, "mock": True}

    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    for name, data, subtype in attachments:
        maintype = "application"
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as s:
        s.starttls()
        if settings.SMTP_USER:
            s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        s.send_message(msg)
    return {"sent": True, "mock": False}
