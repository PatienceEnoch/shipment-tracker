from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ShipmentOrder
from app.services.email_parser import ParsedEmail, parse_email


class MissingSalesOrderError(ValueError):
    pass


class TrackingConflictError(ValueError):
    pass


def ingest_email_content(
    db: Session,
    subject: str,
    text: str,
) -> tuple[ParsedEmail, ShipmentOrder]:
    parsed = parse_email(subject, text)

    if not parsed.sales_order:
        raise MissingSalesOrderError(
            "Could not find a sales order number in the email."
        )

    order = db.scalar(
        select(ShipmentOrder).where(
            ShipmentOrder.sales_order == parsed.sales_order
        )
    )

    now = datetime.now(timezone.utc)

    if order is None:
        order = ShipmentOrder(sales_order=parsed.sales_order)
        db.add(order)
        db.flush()

    if parsed.tracking_number:
        existing = db.scalar(
            select(ShipmentOrder).where(
                ShipmentOrder.tracking_number == parsed.tracking_number,
                ShipmentOrder.id != order.id,
            )
        )

        if existing:
            raise TrackingConflictError(
                "Tracking number is already assigned to another sales order."
            )

        if not order.tracking_number:
            order.tracking_number = parsed.tracking_number
            order.label_recorded_at = now
        elif order.tracking_number != parsed.tracking_number:
            raise TrackingConflictError(
                "Sales order already has a different tracking number."
            )

        if order.first_fedex_scan_at is None:
            order.status = "label_created_awaiting_fedex"

    db.commit()
    db.refresh(order)

    return parsed, order
