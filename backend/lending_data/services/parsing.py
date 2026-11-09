"""Pure parsing helpers for LendingClub-style raw values (no Django imports)."""
from __future__ import annotations

import math
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# Standardisation of raw loan_status strings. Matching is case-insensitive on
# the stripped value. "Does not meet the credit policy" variants are mapped by
# their final outcome (they are legacy-policy loans, flagged in raw status).
STATUS_MAP = {
    "fully paid": "fully_paid",
    "does not meet the credit policy. status:fully paid": "fully_paid",
    "current": "current",
    "in grace period": "late",
    "late (16-30 days)": "late",
    "late (31-120 days)": "late",
    "default": "default",
    "charged off": "charged_off",
    "does not meet the credit policy. status:charged off": "charged_off",
}


def is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip().lower() in {"", "nan", "none", "null", "n/a", "na"}


def to_decimal(value) -> Decimal | None:
    if is_blank(value):
        return None
    s = str(value).strip().replace(",", "").replace("%", "").replace("$", "").replace("₹", "")
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ValueError(f"not a number: {value!r}")
    if not d.is_finite():
        raise ValueError(f"not finite: {value!r}")
    return d


def to_int(value) -> int | None:
    d = to_decimal(value)
    return None if d is None else int(d)


def parse_term_months(value) -> int | None:
    if is_blank(value):
        return None
    m = re.search(r"\d+", str(value))
    if not m:
        raise ValueError(f"bad term: {value!r}")
    return int(m.group())


def parse_employment_years(value) -> Decimal | None:
    """'< 1 year' -> 0, '10+ years' -> 10, '3 years' -> 3, blank -> None."""
    if is_blank(value):
        return None
    s = str(value).strip().lower()
    if s.startswith("<"):
        return Decimal(0)
    m = re.search(r"\d+(\.\d+)?", s)
    if not m:
        raise ValueError(f"bad employment length: {value!r}")
    return Decimal(m.group())


_DATE_FORMATS = ("%b-%Y", "%b-%y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S")


def parse_date(value) -> date | None:
    if is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date: {value!r}")


def standardise_status(raw) -> str:
    if is_blank(raw):
        return "unknown"
    return STATUS_MAP.get(str(raw).strip().lower(), "unknown")
