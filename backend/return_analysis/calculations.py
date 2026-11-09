"""Investor-return mathematics (pure functions, no Django, no pandas).

FORMULAS AND ASSUMPTIONS
------------------------
Let F = funded amount (investor principal at origination), P = total payment
received (principal + interest + late fees + recoveries, as reported by the
source), C = collection/recovery fees.

* Gross return      = (P - F) / F
* Net return        = (P - C - F) / F        (fees and losses are both captured
                                              because losses show up as P < F)
* Annualised return = (1 + r) ** (1 / h) - 1 where h = holding period in years
  (issue date -> last payment date). A single compounding of a pooled return
  over an average holding period is an APPROXIMATION; it is labelled as such
  in outputs.
* IRR   : rate making NPV of equally spaced cash flows zero (per period).
* XIRR  : rate making NPV of dated cash flows zero, 365-day year.

IRR/XIRR are only computed from a genuine cash-flow series with at least one
outflow and one inflow. They return None otherwise - they NEVER extrapolate a
schedule from totals. LendingClub's public file has totals, not dated
payments, so XIRR is available only for datasets that carry payment dates.

Return metrics are only meaningful for RESOLVED loans (fully paid / charged
off / default). Current loans have incomplete cash flows and are excluded by
the services that call these functions.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Sequence


def gross_return(funded, total_payment) -> float | None:
    f = float(funded or 0)
    if f <= 0 or total_payment is None:
        return None
    return (float(total_payment) - f) / f


def net_return(funded, total_payment, fees=0) -> float | None:
    f = float(funded or 0)
    if f <= 0 or total_payment is None:
        return None
    return (float(total_payment) - float(fees or 0) - f) / f


def annualise(total_return: float | None, holding_years: float | None) -> float | None:
    if total_return is None or holding_years is None or holding_years <= 0:
        return None
    if total_return <= -1:
        return -1.0
    return (1 + total_return) ** (1 / holding_years) - 1


def holding_years(start: date | None, end: date | None) -> float | None:
    if not start or not end or end <= start:
        return None
    return (end - start).days / 365.0


def _npv(rate: float, flows: Sequence[float], times: Sequence[float]) -> float:
    return sum(cf / (1 + rate) ** t for cf, t in zip(flows, times))


def _solve(flows, times) -> float | None:
    has_out = any(cf < 0 for cf in flows)
    has_in = any(cf > 0 for cf in flows)
    if len(flows) < 2 or not (has_out and has_in):
        return None
    lo, hi = -0.999999, 10.0
    f_lo, f_hi = _npv(lo, flows, times), _npv(hi, flows, times)
    if f_lo * f_hi > 0:
        return None  # no sign change in bracket -> no reliable root
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = _npv(mid, flows, times)
        if abs(f_mid) < 1e-9:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def irr(cash_flows: Sequence[float]) -> float | None:
    """Per-period IRR of equally spaced flows (index = period number)."""
    return _solve(list(cash_flows), list(range(len(cash_flows))))


def xirr(cash_flows: Sequence[float], dates: Sequence[date]) -> float | None:
    """Annual XIRR of dated flows. Returns None for incomplete input."""
    if len(cash_flows) != len(dates) or len(cash_flows) < 2:
        return None
    t0 = min(dates)
    times = [(d - t0).days / 365.0 for d in dates]
    return _solve([float(c) for c in cash_flows], times)


def herfindahl(values: Sequence[float | Decimal]) -> float | None:
    """HHI on a 0-10,000 scale from raw exposures. None if total is zero."""
    vals = [float(v) for v in values if v is not None and float(v) > 0]
    total = sum(vals)
    if total <= 0:
        return None
    return sum((v / total * 100) ** 2 for v in vals)


def effective_number(hhi: float | None) -> float | None:
    return None if not hhi else 10_000 / hhi
