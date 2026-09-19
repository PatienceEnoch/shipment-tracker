# Shipment Tracker

A small shipment-monitoring service that matches sales orders to FedEx tracking numbers,
enforces two 72-hour deadlines, and accepts carrier scan events.

## Version 1 workflow

1. A sales-order email arrives.
2. The app extracts the sales order number and creates the order.
3. If no tracking number is attached within 72 hours, the order becomes `label_overdue`.
4. A later email containing the same sales order and a tracking number updates the order.
5. If FedEx does not scan the package within 72 hours of the label being recorded, the order becomes `fedex_scan_overdue`.
6. FedEx webhook events update the shipment to `in_transit`, `exception`, or `delivered`.

The first version uses a simulated carrier webhook so the workflow can be tested before connecting
a production FedEx developer account.

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

Then try `in_transit`, `exception`, or `delivered`.

## Test

```bash
pytest
```
