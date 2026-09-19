from app.services.email_parser import parse_email


def test_parses_sales_order_only():
    result = parse_email(
        "New Sales Order 105482",
        "Sales Order: 105482",
    )

    assert result.sales_order == "105482"
    assert result.tracking_number is None


def test_parses_sales_order_and_tracking():
    result = parse_email(
        "Tracking for Sales Order 105482",
        "Sales Order: 105482\nFedEx Tracking: 7845 1234 5678",
    )

    assert result.sales_order == "105482"
    assert result.tracking_number == "784512345678"
