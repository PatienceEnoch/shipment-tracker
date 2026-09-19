import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedEmail:
    sales_order: str | None
    tracking_number: str | None


SALES_ORDER_PATTERNS = [
    re.compile(
        r"\b(?:sales\s*order|sales\s*order\s*(?:number|no\.?|#)|so|s\.o\.)"
        r"\s*[:#-]?\s*([A-Za-z0-9-]{4,32})\b",
        re.IGNORECASE,
    ),
]

TRACKING_PATTERNS = [
    re.compile(
        r"\b(?:fedex\s*)?(?:tracking(?:\s*(?:number|no\.?|#))?)"
        r"\s*[:#-]?\s*([0-9][0-9 -]{10,30}[0-9])\b",
        re.IGNORECASE,
    ),
]


def _clean_tracking(value: str) -> str:
    return re.sub(r"[\s-]+", "", value)


def parse_email(subject: str, text: str) -> ParsedEmail:
    blob = f"{subject}\n{text}"

    sales_order = None
    for pattern in SALES_ORDER_PATTERNS:
        match = pattern.search(blob)
        if match:
            sales_order = match.group(1)
            break

    tracking_number = None
    for pattern in TRACKING_PATTERNS:
        match = pattern.search(blob)
        if match:
            tracking_number = _clean_tracking(match.group(1))
            break

    return ParsedEmail(
        sales_order=sales_order,
        tracking_number=tracking_number,
    )
