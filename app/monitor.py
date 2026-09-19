import asyncio
import os

from .alerts import build_alerts, mark_alert_sent
from .db import SessionLocal
from .email_sender import send_email


def env_true(name: str, default: bool = True) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


async def alert_monitor() -> None:
    interval = int(os.getenv("ALERT_CHECK_INTERVAL_SECONDS", "300"))
    dry_run = env_true("EMAIL_DRY_RUN", True)

    while True:
        db = SessionLocal()

        try:
            alerts = build_alerts(db, pending_only=True)

            for alert in alerts:
                result = send_email(
                    subject=alert["subject"],
                    message=alert["message"],
                    dry_run=dry_run,
                )

                if result["sent"]:
                    mark_alert_sent(
                        db,
                        alert["sales_order"],
                        alert["type"],
                    )

                print(
                    f"[shipment-monitor] "
                    f"{alert['sales_order']} "
                    f"{alert['type']} "
                    f"dry_run={dry_run}"
                )

        except Exception as exc:
            print(f"[shipment-monitor] Error: {exc}")

        finally:
            db.close()

        await asyncio.sleep(interval)
