from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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
    text_body: str | None = None,
) -> None:
    """Send an alert email.

    When *html_body* is provided the message is sent as multipart/alternative
    with a plain-text part first and the HTML part last (RFC 2046 §5.1.4 —
    the preferred representation is the *last* part).

    *text_body* overrides *body* as the plain-text content when supplied so
    callers can provide a richer plain-text fallback independently.  If neither
    is provided *body* is used as-is (backward-compatible behaviour).
    """
    if not settings.ALERT_EMAIL_SMTP_HOST.strip():
        raise AlertEmailConfigError("alert-email-smtp-host-missing")
    if not settings.ALERT_EMAIL_FROM.strip():
        raise AlertEmailConfigError("alert-email-from-missing")
    if not recipient.strip():
        raise AlertEmailConfigError("alert-email-recipient-missing")

    plain = text_body if text_body is not None else body

    if html_body is not None:
        # Build multipart/alternative: plain first, HTML last (preferred).
        message: MIMEMultipart | MIMEText = MIMEMultipart("alternative")
        message["From"] = settings.ALERT_EMAIL_FROM
        message["To"] = recipient
        message["Subject"] = subject
        message.attach(MIMEText(plain, "plain", "utf-8"))
        message.attach(MIMEText(html_body, "html", "utf-8"))
    else:
        # Plain-text only — backward-compatible path.
        message = MIMEText(plain, "plain", "utf-8")
        message["From"] = settings.ALERT_EMAIL_FROM
        message["To"] = recipient
        message["Subject"] = subject

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
            smtp.sendmail(
                settings.ALERT_EMAIL_FROM,
                recipient,
                message.as_string(),
            )
    except AlertEmailConfigError:
        raise
    except Exception as exc:
        raise AlertEmailSendError("alert-email-send-failed") from exc

