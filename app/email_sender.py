import os
import smtplib
from email.message import EmailMessage


def send_email(subject: str, message: str, dry_run: bool = True) -> dict:
    recipient = os.getenv("ALERT_EMAIL_TO")
    sender = os.getenv("ALERT_EMAIL_FROM")
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if dry_run:
        return {
            "sent": False,
            "dry_run": True,
            "to": recipient,
            "subject": subject,
            "message": message,
        }

    missing = [
        name
        for name, value in {
            "ALERT_EMAIL_TO": recipient,
            "ALERT_EMAIL_FROM": sender,
            "SMTP_HOST": smtp_host,
            "SMTP_USER": smtp_user,
            "SMTP_PASSWORD": smtp_password,
        }.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Missing email configuration: " + ", ".join(missing)
        )

    email = EmailMessage()
    email["From"] = sender
    email["To"] = recipient
    email["Subject"] = subject
    email.set_content(message)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(email)

    return {
        "sent": True,
        "dry_run": False,
        "to": recipient,
        "subject": subject,
    }
