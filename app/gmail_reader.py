import asyncio
import hashlib
import html
import imaplib
import os
import re
from email import policy
from email.parser import BytesParser

from sqlalchemy import select

from .db import SessionLocal
from .models import ProcessedEmail
from .services.ingest import (
    MissingSalesOrderError,
    TrackingConflictError,
    ingest_email_content,
)


def _extract_text(raw_message: bytes) -> tuple[str, str, str]:
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    subject = str(message.get("Subject", ""))
    recipient = str(message.get("To", ""))

    body = message.get_body(preferencelist=("plain", "html"))

    if body is None:
        text = ""
    else:
        text = body.get_content()

        if body.get_content_type() == "text/html":
            text = html.unescape(re.sub(r"<[^>]+>", " ", text))
            text = re.sub(r"\s+", " ", text).strip()

    return subject, recipient, text


def _message_key(raw_message: bytes) -> str:
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    message_id = str(message.get("Message-ID", "")).strip()

    if message_id:
        return message_id

    return hashlib.sha256(raw_message).hexdigest()


def process_gmail_once() -> dict:
    if os.getenv("GMAIL_INTAKE_ENABLED", "false").lower() != "true":
        return {"enabled": False, "processed": 0, "ignored": 0, "errors": 0}

    intake_address = os.getenv("GMAIL_INTAKE_ADDRESS")
    gmail_user = os.getenv("GMAIL_USER") or os.getenv("SMTP_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD") or os.getenv(
        "SMTP_PASSWORD"
    )
    imap_host = os.getenv("IMAP_HOST", "imap.gmail.com")
    imap_port = int(os.getenv("IMAP_PORT", "993"))

    missing = [
        name
        for name, value in {
            "GMAIL_INTAKE_ADDRESS": intake_address,
            "GMAIL_USER/SMTP_USER": gmail_user,
            "GMAIL_APP_PASSWORD/SMTP_PASSWORD": gmail_password,
        }.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Missing Gmail intake configuration: " + ", ".join(missing)
        )

    processed = 0
    ignored = 0
    errors = 0

    with imaplib.IMAP4_SSL(imap_host, imap_port) as client:
        client.login(gmail_user, gmail_password)
        client.select("INBOX")

        status, data = client.search(
            None,
            "TO",
            f'"{intake_address}"',
        )

        if status != "OK":
            raise RuntimeError("Gmail IMAP search failed.")

        message_numbers = data[0].split()[-100:]

        for message_number in message_numbers:
            status, message_data = client.fetch(
                message_number,
                "(BODY.PEEK[])",
            )

            if status != "OK":
                errors += 1
                continue

            raw_message = next(
                (
                    item[1]
                    for item in message_data
                    if isinstance(item, tuple)
                ),
                None,
            )

            if not raw_message:
                errors += 1
                continue

            key = _message_key(raw_message)

            with SessionLocal() as db:
                already_processed = db.scalar(
                    select(ProcessedEmail).where(
                        ProcessedEmail.message_key == key
                    )
                )

                if already_processed:
                    continue

                subject, recipient, body = _extract_text(raw_message)

                if intake_address.lower() not in recipient.lower():
                    continue

                record = ProcessedEmail(
                    message_key=key,
                    status="processed",
                )
                db.add(record)

                try:
                    ingest_email_content(
                        db,
                        subject=subject,
                        text=body,
                    )
                    processed += 1
                except MissingSalesOrderError as exc:
                    record.status = "ignored"
                    record.detail = str(exc)
                    db.commit()
                    ignored += 1
                except TrackingConflictError as exc:
                    record.status = "error"
                    record.detail = str(exc)
                    db.commit()
                    errors += 1
                except Exception:
                    db.rollback()
                    raise

    return {
        "enabled": True,
        "processed": processed,
        "ignored": ignored,
        "errors": errors,
    }


async def gmail_intake_monitor() -> None:
    interval = int(os.getenv("GMAIL_CHECK_INTERVAL_SECONDS", "60"))

    while True:
        try:
            result = await asyncio.to_thread(process_gmail_once)

            if result["enabled"]:
                print(
                    "[gmail-intake] "
                    f"processed={result['processed']} "
                    f"ignored={result['ignored']} "
                    f"errors={result['errors']}"
                )

        except Exception as exc:
            print(f"[gmail-intake] Error: {exc}")

        await asyncio.sleep(interval)
