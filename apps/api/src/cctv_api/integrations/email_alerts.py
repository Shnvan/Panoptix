from __future__ import annotations

import smtplib
from email.message import EmailMessage

from cctv_api.core.config import Settings


class AlertEmailConfigError(RuntimeError):
    pass


class AlertEmailSendError(RuntimeError):
    pass


def send_alert_email(
    settings: Settings,
    *,
    recipient: str,
    subject: str,
    body: str,
    html_body: str | None = None,
) -> None:
    if not settings.ALERT_EMAIL_SMTP_HOST.strip():
        raise AlertEmailConfigError("alert-email-smtp-host-missing")
    if not settings.ALERT_EMAIL_FROM.strip():
        raise AlertEmailConfigError("alert-email-from-missing")
    if not recipient.strip():
        raise AlertEmailConfigError("alert-email-recipient-missing")

    message = EmailMessage()
    message["From"] = settings.ALERT_EMAIL_FROM
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    if html_body is not None:
        message.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(
            settings.ALERT_EMAIL_SMTP_HOST,
            settings.ALERT_EMAIL_SMTP_PORT,
            timeout=settings.ALERT_EMAIL_TIMEOUT_SECONDS,
        ) as smtp:
            if settings.ALERT_EMAIL_USE_TLS:
                smtp.starttls()
            if settings.ALERT_EMAIL_SMTP_USERNAME.strip():
                smtp.login(settings.ALERT_EMAIL_SMTP_USERNAME, settings.ALERT_EMAIL_SMTP_PASSWORD)
            smtp.send_message(message)
    except AlertEmailConfigError:
        raise
    except Exception as exc:
        raise AlertEmailSendError("alert-email-send-failed") from exc
