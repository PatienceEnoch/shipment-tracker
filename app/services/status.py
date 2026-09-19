from datetime import datetime, timedelta, timezone

from app.models import ShipmentOrder

DEADLINE = timedelta(hours=72)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def effective_status(order: ShipmentOrder, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)

    if order.status == "complete":
        return "complete"

    if order.status == "exception":
        return "exception"

    if order.first_fedex_scan_at:
        return "complete"

    if order.tracking_number and order.label_recorded_at:
        if now - _aware(order.label_recorded_at) >= DEADLINE:
            return "fedex_scan_overdue"
        return "label_created_awaiting_fedex"

    if now - _aware(order.created_at) >= DEADLINE:
        return "label_overdue"

    return "awaiting_label"
