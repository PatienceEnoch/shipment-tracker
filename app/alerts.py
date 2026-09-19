from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AlertNotification, ShipmentOrder
from .services.status import effective_status


def build_alerts(db: Session, pending_only: bool = False) -> list[dict]:
    orders = db.scalars(select(ShipmentOrder)).all()
    alerts = []

    for order in orders:
        status = effective_status(order)

        if status == "label_overdue":
            alert_type = "label_overdue"
            subject = f"Shipment Alert: Sales Order {order.sales_order}"
            message = (
                f"Sales Order {order.sales_order} has been open for more "
                "than 72 hours and no FedEx tracking number has been recorded."
            )

        elif status == "fedex_scan_overdue":
            alert_type = "fedex_scan_overdue"
            subject = f"FedEx Scan Alert: Sales Order {order.sales_order}"
            message = (
                f"Sales Order {order.sales_order} has FedEx tracking number "
                f"{order.tracking_number}, but FedEx has not scanned the "
                "package within 72 hours of label creation."
            )

        else:
            continue

        already_sent = db.scalar(
            select(AlertNotification).where(
                AlertNotification.sales_order == order.sales_order,
                AlertNotification.alert_type == alert_type,
            )
        )

        if pending_only and already_sent:
            continue

        alerts.append(
            {
                "sales_order": order.sales_order,
                "tracking_number": order.tracking_number,
                "type": alert_type,
                "subject": subject,
                "message": message,
                "already_sent": already_sent is not None,
            }
        )

    return alerts


def mark_alert_sent(db: Session, sales_order: str, alert_type: str) -> bool:
    existing = db.scalar(
        select(AlertNotification).where(
            AlertNotification.sales_order == sales_order,
            AlertNotification.alert_type == alert_type,
        )
    )

    if existing:
        return False

    db.add(
        AlertNotification(
            sales_order=sales_order,
            alert_type=alert_type,
        )
    )
    db.commit()
    return True
