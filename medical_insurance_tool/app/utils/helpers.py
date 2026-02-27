"""
General utilities: session state helpers, formatting, validation.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Optional


def generate_broker_ref() -> str:
    """Generate a unique broker reference number."""
    today = date.today()
    uid = str(uuid.uuid4())[:6].upper()
    return f"MQ-{today.strftime('%Y%m%d')}-{uid}"


def format_aed(amount: float) -> str:
    """Format a number as AED currency string."""
    return f"AED {amount:,.2f}"


def validate_emirates_id(eid: str) -> bool:
    """Validate UAE Emirates ID format: 784-YYYY-NNNNNNN-C."""
    cleaned = re.sub(r"[\s\-]", "", eid)
    return bool(re.match(r"^784\d{4}\d{7}\d$", cleaned))


def validate_passport_number(num: str) -> bool:
    """Basic passport number format check."""
    return bool(re.match(r"^[A-Z0-9]{6,9}$", num.upper()))


def parse_date_flexible(s: str) -> Optional[date]:
    """Try multiple date formats and return a date object or None."""
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%d/%m/%y", "%d-%m-%y",
        "%Y-%m-%d",
        "%d %b %Y", "%d %B %Y",
    ]
    s = s.strip()
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def age_from_dob(dob: date) -> int:
    today = date.today()
    return (
        today.year - dob.year
        - ((today.month, today.day) < (dob.month, dob.day))
    )


def truncate(s: str, max_len: int = 30) -> str:
    return s if len(s) <= max_len else s[:max_len - 1] + "…"


def safe_str(val) -> str:
    if val is None:
        return ""
    return str(val).strip()
