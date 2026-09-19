# Shipment Tracker

A small shipment-monitoring service that matches sales orders to FedEx tracking numbers,
enforces two 72-hour deadlines, and accepts carrier scan events.

## Version 1 workflow

1. A sales-order email arrives.
2. The app extracts the sales order number and creates the order.
3. If no tracking number is attached within 72 hours, the order becomes `label_overdue`.
4. A later email containing the same sales order and a tracking number updates the order.
5. If FedEx does not scan the package within 72 hours of the label being recorded, the order becomes `fedex_scan_overdue`.
6. The first FedEx event that proves the carrier has possession marks the order `complete`.
7. Once complete, the tracker stops caring about later transit or delivery events.

The first version uses a simulated FedEx event endpoint so the workflow can be tested before connecting
FedEx's production tracking API.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:

- API docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health
- Orders: http://127.0.0.1:8000/orders
- Overdue alerts: http://127.0.0.1:8000/alerts/overdue

## Example: sales-order email

```bash
curl -X POST http://127.0.0.1:8000/ingest/email \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "sales@example.com",
    "subject": "Sales Order 105482",
    "text": "Sales Order: 105482",
    "message_id": "message-001"
  }'
```

## Example: label email

```bash
curl -X POST http://127.0.0.1:8000/ingest/email \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "shipping@example.com",
    "subject": "Tracking for Sales Order 105482",
    "text": "Sales Order: 105482\nFedEx Tracking: 784512345678",
    "message_id": "message-002"
  }'
```

## Example: simulated FedEx scan

```bash
curl -X POST http://127.0.0.1:8000/webhooks/fedex \
  -H "Content-Type: application/json" \
  -d '{
    "tracking_number": "784512345678",
    "event": "picked_up"
  }'
```

A possession event such as `picked_up` marks the order `complete`. The tracker is intentionally
concerned only with whether FedEx acquired the package, not the customer's delivery journey.

## Test

```bash
pytest
```
