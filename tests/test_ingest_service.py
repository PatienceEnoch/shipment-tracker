from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import ShipmentOrder
from app.services.ingest import ingest_email_content


def test_email_can_create_then_add_tracking():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        parsed, order = ingest_email_content(
            db,
            subject="Sales Order 105500",
            text="Sales Order: 105500",
        )

        assert parsed.sales_order == "105500"
        assert order.status == "awaiting_label"
        assert order.tracking_number is None

        parsed, order = ingest_email_content(
            db,
            subject="Tracking for Sales Order 105500",
            text=(
                "Sales Order: 105500\n"
                "FedEx Tracking: 784512345680"
            ),
        )

        assert parsed.tracking_number == "784512345680"
        assert order.tracking_number == "784512345680"
        assert order.status == "label_created_awaiting_fedex"

        stored = db.query(ShipmentOrder).filter_by(
            sales_order="105500"
        ).one()
        assert stored.id == order.id
