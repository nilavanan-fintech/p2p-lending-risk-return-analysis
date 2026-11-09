"""Investor return aggregates over RESOLVED loans only (see calculations.py)."""
from __future__ import annotations

from collections import defaultdict

from django.db.models import Q

from lending_data.models import Loan

from . import calculations as calc

RESOLVED = [s.value for s in Loan.RESOLVED]


def _pool(loans) -> dict:
    funded = payments = fees = interest = principal = recov = 0.0
    w_years = w_sum = 0.0
    n = 0
    for ln in loans:
        f = float(ln.funded_amount or ln.loan_amount or 0)
        if f <= 0 or ln.total_payment is None:
            continue
        n += 1
        funded += f
        payments += float(ln.total_payment)
        fees += float(ln.recovery_fees or 0)
        interest += float(ln.interest_received or 0)
        principal += float(ln.principal_received or 0)
        recov += float(ln.recoveries or 0)
        h = calc.holding_years(ln.issue_date, ln.last_payment_date)
        if h:
            w_years += h * f
            w_sum += f
    net = calc.net_return(funded, payments, fees)
    avg_h = (w_years / w_sum) if w_sum else None
    return {
        "loans": n,
        "invested": round(funded, 2),
        "principal_recovered": round(principal, 2),
        "interest_received": round(interest, 2),
        "recoveries": round(recov, 2),
        "loss_amount": round(max(funded - principal - recov, 0), 2),
        "gross_return": calc.gross_return(funded, payments),
        "net_return": net,
        "avg_holding_years": avg_h,
        # Approximation: pooled return compounded over funded-weighted holding period.
        "net_annualised_approx": calc.annualise(net, avg_h),
    }


def return_by(qs, field: str) -> list[dict]:
    """Group resolved loans by a model field (grade, term_months, purpose...)."""
    groups = defaultdict(list)
    for ln in qs.filter(status__in=RESOLVED).only(
        "funded_amount", "loan_amount", "total_payment", "recovery_fees", "interest_received",
        "principal_received", "recoveries", "issue_date", "last_payment_date", field,
    ).iterator(chunk_size=5000):
        groups[getattr(ln, field)].append(ln)
    return [{"group": k if k not in (None, "") else "Unknown", **_pool(v)}
            for k, v in sorted(groups.items(), key=lambda kv: str(kv[0]))]


def overall_return(qs) -> dict:
    out = _pool(qs.filter(status__in=RESOLVED).iterator(chunk_size=5000))
    active = qs.exclude(status__in=RESOLVED).filter(status__in=["current", "late"])
    out["outstanding_principal"] = float(sum((x or 0) for x in active.values_list("outstanding_principal", flat=True)))
    out["basis"] = "resolved loans only (fully paid, default, charged off); current loans excluded"
    return out
