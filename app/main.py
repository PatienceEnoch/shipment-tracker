import asyncio
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .alerts import build_alerts, mark_alert_sent
from .dashboard import router as dashboard_router
from .db import Base, engine, get_db
from .email_sender import send_email
from .gmail_reader import gmail_intake_monitor, process_gmail_once
from .models import ShipmentOrder
from .monitor import alert_monitor
from .schemas import EmailPayload, FedExEvent
from .services.ingest import (
    MissingSalesOrderError,
    TrackingConflictError,
    ingest_email_content,
)
from .services.status import effective_status

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Shipment Tracker",
    version="0.1.0",
    description=(
        "Tracks sales orders, label creation, FedEx scans, and two 72-hour deadlines."
    ),
)

app.include_router(dashboard_router)


def serialize_order(order: ShipmentOrder) -> dict:
    return {
        "id": order.id,
        "sales_order": order.sales_order,
        "tracking_number": order.tracking_number,
        "status": effective_status(order),
        "stored_status": order.status,
        "created_at": order.created_at,
        "label_recorded_at": order.label_recorded_at,
        "first_fedex_scan_at": order.first_fedex_scan_at,
        "delivered_at": order.delivered_at,
        "last_event": order.last_event,
    }


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/ingest/email")
def ingest_email(payload: EmailPayload, db: Session = Depends(get_db)) -> dict:
    try:
        parsed, order = ingest_email_content(
            db,
            subject=payload.subject,
            text=payload.text,
        )
    except MissingSalesOrderError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TrackingConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "parsed": {
            "sales_order": parsed.sales_order,
            "tracking_number": parsed.tracking_number,
        },
        "order": serialize_order(order),
    }


@app.post("/gmail/check-now")
def gmail_check_now() -> dict:
    return process_gmail_once()


@app.post("/webhooks/fedex")
def fedex_webhook(event: FedExEvent, db: Session = Depends(get_db)) -> dict:
    order = db.scalar(
        select(ShipmentOrder).where(
            ShipmentOrder.tracking_number == event.tracking_number
        )
    )

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="No sales order is associated with this tracking number.",
        )

    normalized = event.event.strip().lower().replace(" ", "_")
    allowed = {
        "picked_up",
        "accepted",
        "in_transit",
        "exception",
        "out_for_delivery",
        "delivered",
    }

    if normalized not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported FedEx event: {event.event}",
        )

    now = datetime.now(timezone.utc)

    if order.first_fedex_scan_at is None:
        order.first_fedex_scan_at = now

    order.last_event = normalized
    order.status = normalized

    if normalized == "delivered":
        order.delivered_at = now

    db.commit()
    db.refresh(order)

    return {"order": serialize_order(order)}


@app.get("/orders")
def list_orders(db: Session = Depends(get_db)) -> list[dict]:
    orders = db.scalars(
        select(ShipmentOrder).order_by(ShipmentOrder.created_at.desc())
    ).all()
    return [serialize_order(order) for order in orders]


@app.get("/alerts/overdue")
def overdue_alerts(db: Session = Depends(get_db)) -> list[dict]:
    orders = db.scalars(select(ShipmentOrder)).all()
    return [
        serialize_order(order)
        for order in orders
        if effective_status(order) in {"label_overdue", "fedex_scan_overdue"}
    ]


@app.get("/alerts/email-preview")
def email_alert_preview(db: Session = Depends(get_db)) -> list[dict]:
    return build_alerts(db)


@app.get("/alerts/pending")
def pending_email_alerts(db: Session = Depends(get_db)) -> list[dict]:
    return build_alerts(db, pending_only=True)


@app.post("/alerts/mark-sent/{sales_order}/{alert_type}")
def mark_email_alert_sent(
    sales_order: str,
    alert_type: str,
    db: Session = Depends(get_db),
) -> dict:
    created = mark_alert_sent(db, sales_order, alert_type)
    return {
        "sales_order": sales_order,
        "alert_type": alert_type,
        "marked_sent": created,
    }


@app.post("/alerts/send-pending")
def send_pending_alerts(
    dry_run: bool = True,
    db: Session = Depends(get_db),
) -> list[dict]:
    alerts = build_alerts(db, pending_only=True)
    results = []

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

        results.append(
            {
                "sales_order": alert["sales_order"],
                "type": alert["type"],
                **result,
            }
        )

    return results


_alert_task = None
_gmail_task = None


@app.on_event("startup")
async def start_background_tasks():
    global _alert_task, _gmail_task

    _alert_task = asyncio.create_task(alert_monitor())
    _gmail_task = asyncio.create_task(gmail_intake_monitor())


@app.on_event("shutdown")
async def stop_background_tasks():
    global _alert_task, _gmail_task

    for task in (_alert_task, _gmail_task):
        if task:
            task.cancel()
