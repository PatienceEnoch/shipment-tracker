from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import ShipmentOrder
from .services.status import effective_status

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(db: Session = Depends(get_db)):
    orders = db.scalars(
        select(ShipmentOrder).order_by(ShipmentOrder.created_at.desc())
    ).all()

    statuses = {order.id: effective_status(order) for order in orders}

    waiting_label = sum(
        status == "awaiting_label" for status in statuses.values()
    )
    waiting_fedex = sum(
        status == "label_created_awaiting_fedex"
        for status in statuses.values()
    )
    in_transit = sum(
        status in {"picked_up", "accepted", "in_transit", "out_for_delivery"}
        for status in statuses.values()
    )
    needs_attention = sum(
        status in {"label_overdue", "fedex_scan_overdue", "exception"}
        for status in statuses.values()
    )

    rows = []

    for order in orders:
        status = statuses[order.id]

        if status in {"label_overdue", "fedex_scan_overdue", "exception"}:
            status_class = "danger"
        elif status in {"awaiting_label", "label_created_awaiting_fedex"}:
            status_class = "warning"
        elif status == "delivered":
            status_class = "success"
        else:
            status_class = "active"

        tracking = order.tracking_number or "—"

        rows.append(
            f"""
            <tr>
                <td>{order.sales_order}</td>
                <td>{tracking}</td>
                <td>
                    <span class="status {status_class}">
                        {status.replace("_", " ").title()}
                    </span>
                </td>
            </tr>
            """
        )

    table_rows = "\n".join(rows) or """
        <tr>
            <td colspan="3" class="empty">No shipments yet.</td>
        </tr>
    """

    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Shipment Tracker</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="30">

    <style>
        body {{
            font-family: Arial, sans-serif;
            background: #f4f6f8;
            margin: 0;
            color: #1f2933;
        }}

        .container {{
            max-width: 1100px;
            margin: 40px auto;
            padding: 0 20px;
        }}

        h1 {{
            margin-bottom: 5px;
        }}

        .subtitle {{
            color: #68737d;
            margin-bottom: 30px;
        }}

        .cards {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 30px;
        }}

        .card {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,.06);
        }}

        .card-number {{
            font-size: 32px;
            font-weight: bold;
        }}

        .card-label {{
            color: #68737d;
            margin-top: 5px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,.06);
        }}

        th, td {{
            padding: 16px;
            text-align: left;
            border-bottom: 1px solid #e6e9ec;
        }}

        th {{
            background: #eef1f4;
        }}

        .status {{
            padding: 6px 10px;
            border-radius: 999px;
            font-size: 14px;
            font-weight: bold;
        }}

        .danger {{
            background: #ffe5e5;
            color: #a61b1b;
        }}

        .warning {{
            background: #fff2cc;
            color: #7a5600;
        }}

        .success {{
            background: #dff5e5;
            color: #176b34;
        }}

        .active {{
            background: #e2ecff;
            color: #174ea6;
        }}

        .empty {{
            text-align: center;
            color: #68737d;
        }}

        @media (max-width: 800px) {{
            .cards {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
    </style>
</head>

<body>
    <div class="container">
        <h1>Shipment Tracker</h1>
        <div class="subtitle">
            Sales order and FedEx shipment monitoring
        </div>

        <div class="cards">
            <div class="card">
                <div class="card-number">{waiting_label}</div>
                <div class="card-label">Waiting for Label</div>
            </div>

            <div class="card">
                <div class="card-number">{waiting_fedex}</div>
                <div class="card-label">Waiting for FedEx</div>
            </div>

            <div class="card">
                <div class="card-number">{in_transit}</div>
                <div class="card-label">In Transit</div>
            </div>

            <div class="card">
                <div class="card-number">{needs_attention}</div>
                <div class="card-label">Needs Attention</div>
            </div>
        </div>

        <input
            id="shipmentSearch"
            type="text"
            placeholder="Search sales order or tracking number..."
            onkeyup="filterShipments()"
            style="
                width: 100%;
                box-sizing: border-box;
                padding: 14px 16px;
                margin-bottom: 16px;
                border: 1px solid #d6dbe0;
                border-radius: 8px;
                font-size: 16px;
                background: white;
            "
        >

        <table id="shipmentTable">
            <thead>
                <tr>
                    <th>Sales Order</th>
                    <th>Tracking Number</th>
                    <th>Status</th>
                </tr>
            </thead>

            <tbody>
                {table_rows}
            </tbody>
        </table>
    </div>
<script>
        function filterShipments() {{
            const input = document.getElementById("shipmentSearch");
            const filter = input.value.toLowerCase();
            const rows = document.querySelectorAll("#shipmentTable tbody tr");

            rows.forEach(row => {{
                const text = row.innerText.toLowerCase();
                row.style.display = text.includes(filter) ? "" : "none";
            }});
        }}
    </script>
</body>
</html>
"""


