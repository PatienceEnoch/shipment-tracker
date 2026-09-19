# Shipment Tracker

A Python service built around a real operations problem: knowing whether a sales order actually progressed from **order created** to **shipping label created** to **carrier has the package**.

The tracker watches those handoffs and raises an alert when either one takes longer than 72 hours.

## The workflow

~~~text
Sales-order email
      |
Order created
      |
72-hour label clock
      |
Tracking number recorded
      |
72-hour carrier-scan clock
      |
FedEx possession event
      |
Complete
~~~

The application stops tracking after the first carrier event that proves FedEx has possession. It is intentionally focused on the business handoff to the carrier rather than the customer's full delivery journey.

## What is implemented

- FastAPI application and API endpoints
- SQLite persistence with SQLAlchemy
- Sales-order and tracking-number parsing
- Gmail/IMAP intake support
- Email alert delivery with dry-run support
- 72-hour label and carrier-scan deadlines
- Alert deduplication
- Browser dashboard
- Automated monitoring loop
- Simulated FedEx webhook for possession events
- pytest coverage
- GitHub Actions

## Current limitation

The FedEx side is still simulated.

A webhook such as:

~~~json
{
  "tracking_number": "784512345678",
  "event": "picked_up"
}
~~~

can mark an order complete, which lets me validate the end-to-end state machine before replacing that simulated event with the production FedEx tracking integration.

## State model

An order can move through states such as:

~~~text
awaiting_label
      |
label_recorded
      |
awaiting_fedex_scan
      |
complete
~~~

If a deadline is exceeded, the tracker surfaces the appropriate overdue condition rather than silently losing the order in the workflow.

## Run locally

~~~bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
~~~

Useful local endpoints:

- API docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health
- Orders: http://127.0.0.1:8000/orders
- Overdue alerts: http://127.0.0.1:8000/alerts/overdue

## Configuration

The repository includes `.env.example` for SMTP, IMAP/Gmail intake, alert intervals, and dry-run behavior.

I keep secrets out of the repository and use environment variables for runtime credentials.

## Test

~~~bash
pytest
~~~

## Why I built it

This project came from a real workflow where the important question was not "where is the package right now?"

It was:

> **Did the order make it through the handoffs that are our responsibility?**

That pushed me to think in terms of state, deadlines, idempotent alerts, external events, and operational visibility instead of just building another CRUD application.
