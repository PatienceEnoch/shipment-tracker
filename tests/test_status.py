from datetime import datetime, timedelta, timezone

from app.models import ShipmentOrder
from app.services.status import effective_status


def test_label_becomes_overdue_after_72_hours():
    now = datetime.now(timezone.utc)
    order = ShipmentOrder(
        sales_order="10001",
        created_at=now - timedelta(hours=73),
    )

    assert effective_status(order, now=now) == "label_overdue"


def test_fedex_scan_becomes_overdue_after_72_hours():
    now = datetime.now(timezone.utc)
    order = ShipmentOrder(
        sales_order="10002",
        tracking_number="784512345678",
        created_at=now - timedelta(hours=80),
        label_recorded_at=now - timedelta(hours=73),
        status="label_created_awaiting_fedex",
    )

    assert effective_status(order, now=now) == "fedex_scan_overdue"


def test_scan_stops_second_timer():
    now = datetime.now(timezone.utc)
    order = ShipmentOrder(
        sales_order="10003",
        tracking_number="784512345679",
        created_at=now - timedelta(hours=100),
        label_recorded_at=now - timedelta(hours=90),
        first_fedex_scan_at=now - timedelta(hours=85),
        status="in_transit",
    )

    assert effective_status(order, now=now) == "in_transit"
