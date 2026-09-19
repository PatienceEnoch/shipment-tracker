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
    TrackingConflictError,
    ingest_email_content,
)


def _extract_text(raw_message: bytes) -> tuple[str, str]:
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    subject = str(message.get("Subject", ""))

    body = message.get_body(preferencelist=("plain", "html"))

    if body is None:
        text = ""
    else:
        text = body.get_content()

        if body.get_content_type() == "text/html":
            text = html.unescape(re.sub(r"<[^>]+>", " ", text))
            text = re.sub(r"\s+", " ", text).strip()

    return subject, text


def _subject_is_candidate(subject: str, subject_prefix: str) -> bool:
    normalized = subject.strip().lower()

    if normalized.startswith(subject_prefix.lower()):
        return True

    return (
        normalized.startswith("sales order ")
        or normalized.startswith("tracking for sales order ")
    )


def _message_key(raw_message: bytes) -> str:
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    message_id = str(message.get("Message-ID", "")).strip()

    if message_id:
        return message_id

    return hashlib.sha256(raw_message).hexdigest()


def process_gmail_once() -> dict:
    if os.getenv("GMAIL_INTAKE_ENABLED", "false").lower() != "true":
        return {
            "enabled": False,
            "checked": 0,
            "matched": 0,
            "processed": 0,
            "errors": 0,
        }

    gmail_user = os.getenv("GMAIL_USER") or os.getenv("SMTP_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD") or os.getenv(
        "SMTP_PASSWORD"
    )
    subject_prefix = os.getenv(
        "GMAIL_INTAKE_SUBJECT_PREFIX",
        "[Shipment Tracker]",
    )
    imap_host = os.getenv("IMAP_HOST", "imap.gmail.com")
    imap_port = int(os.getenv("IMAP_PORT", "993"))

    missing = [
        name
        for name, value in {
            "GMAIL_USER/SMTP_USER": gmail_user,
            "GMAIL_APP_PASSWORD/SMTP_PASSWORD": gmail_password,
        }.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Missing Gmail intake configuration: " + ", ".join(missing)
        )

    checked = 0
    matched = 0
    processed = 0
    errors = 0

    with imaplib.IMAP4_SSL(imap_host, imap_port) as client:
        client.login(gmail_user, gmail_password)
        client.select("INBOX")

        status, data = client.search(None, "ALL")

        if status != "OK":
            raise RuntimeError("Gmail IMAP search failed.")

        message_numbers = data[0].split()[-100:]

        for message_number in message_numbers:
            checked += 1

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

            subject, body = _extract_text(raw_message)

            if not _subject_is_candidate(subject, subject_prefix):
                continue

            matched += 1
            key = _message_key(raw_message)

            with SessionLocal() as db:
                already_processed = db.scalar(
                    select(ProcessedEmail).where(
                        ProcessedEmail.message_key == key
                    )
                )

                if already_processed:
                    continue

                try:
                    ingest_email_content(
                        db,
                        subject=subject,
                        text=body,
                    )

                    db.add(
                        ProcessedEmail(
                            message_key=key,
                            status="processed",
                        )
                    )
                    db.commit()
                    processed += 1

                except TrackingConflictError as exc:
                    db.rollback()
                    db.add(
                        ProcessedEmail(
                            message_key=key,
                            status="error",
                            detail=str(exc),
                        )
                    )
                    db.commit()
                    errors += 1

                except Exception as exc:
                    db.rollback()
                    db.add(
                        ProcessedEmail(
                            message_key=key,
                            status="error",
                            detail=str(exc),
                        )
                    )
                    db.commit()
                    errors += 1

    return {
        "enabled": True,
        "checked": checked,
        "matched": matched,
        "processed": processed,
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
                    f"checked={result['checked']} "
                    f"matched={result['matched']} "
                    f"processed={result['processed']} "
                    f"errors={result['errors']}"
                )

        except Exception as exc:
            print(f"[gmail-intake] Error: {exc}")

        await asyncio.sleep(interval)
