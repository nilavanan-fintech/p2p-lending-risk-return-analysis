"""Credit-risk and loan-performance aggregates computed in the database.

METRIC DEFINITIONS (denominators are explicit and returned with every row)
* default_rate      = (default + charged_off) / resolved loans
                      resolved = fully_paid + default + charged_off
                      Current/late loans are excluded: their outcome is not yet
                      known (right-censoring), so including them would
                      understate risk.
* charge_off_rate   = charged_off / resolved loans
* delinquency_rate  = late / (current + late) i.e. share of ACTIVE loans late
* recovery_rate     = recoveries / loss_exposure on bad loans, where
                      loss_exposure = funded amount - principal received.
All functions take a Loan queryset so callers can scope by data source.
"""
from __future__ import annotations

from django.db.models import (Case, CharField, Count, DecimalField, F, IntegerField, Q, Sum, Value, When)
from django.db.models.functions import ExtractYear

from lending_data.models import Loan

RESOLVED_Q = Q(status__in=[s.value for s in Loan.RESOLVED])
BAD_Q = Q(status__in=[s.value for s in Loan.BAD])


def _rate(num, den):
    return round(num / den, 4) if den else None


def bucket(field: str, edges: list[float], fmt: str = "{lo:g}-{hi:g}", last: str = "{lo:g}+"):
    """Case/When expression labelling `field` into half-open [lo, hi) buckets.
    Null values fall into 'Unknown' (kept visible, never silently dropped)."""
    whens = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        whens.append(When(**{f"{field}__gte": lo, f"{field}__lt": hi}, then=Value(fmt.format(lo=lo, hi=hi))))
    whens.append(When(**{f"{field}__gte": edges[-1]}, then=Value(last.format(lo=edges[-1]))))
    return Case(*whens, default=Value("Unknown"), output_field=CharField())


def _default_rows(qs, label_expr):
    rows = (
        qs.annotate(_g=label_expr)
        .values("_g")
        .annotate(
            all_loans=Count("id"),
            resolved_loans=Count("id", filter=RESOLVED_Q),
            bad_loans=Count("id", filter=BAD_Q),
            charged_off=Count("id", filter=Q(status=Loan.Status.CHARGED_OFF)),
        )
        .order_by("_g")
    )
    return [
        {
            "group": r["_g"] or "Unknown",
            "all_loans": r["all_loans"],
            "resolved_loans": r["resolved_loans"],
            "bad_loans": r["bad_loans"],
            "default_rate": _rate(r["bad_loans"], r["resolved_loans"]),
            "charge_off_rate": _rate(r["charged_off"], r["resolved_loans"]),
        }
        for r in rows
    ]


def default_rate_by_grade(qs):
    return _default_rows(qs, F("grade"))


def default_rate_by_purpose(qs):
    return _default_rows(qs, F("purpose"))


def default_rate_by_term(qs):
    return _default_rows(qs, Case(When(term_months__isnull=False, then=F("term_months")), default=Value(0),
                                  output_field=IntegerField()))


def default_rate_by_interest_band(qs, edges=(0, 8, 12, 16, 20, 25, 100)):
    return _default_rows(qs, bucket("interest_rate", list(edges)))


def default_rate_by_dti_band(qs, edges=(0, 10, 20, 30, 40)):
    return _default_rows(qs, bucket("dti", list(edges)))


def default_rate_by_income_band(qs, edges=(0, 30000, 60000, 90000, 120000, 200000)):
    return _default_rows(qs, bucket("annual_income", list(edges), fmt="{lo:,.0f}-{hi:,.0f}", last="{lo:,.0f}+"))


def default_rate_by_loan_amount_band(qs, edges=(0, 5000, 10000, 20000, 30000)):
    return _default_rows(qs, bucket("loan_amount", list(edges), fmt="{lo:,.0f}-{hi:,.0f}", last="{lo:,.0f}+"))


def default_rate_by_fico_band(qs, edges=(300, 660, 700, 740, 780)):
    return _default_rows(qs, bucket("fico_low", list(edges)))


def status_summary(qs) -> dict:
    """Counts and the four distinct rates with their denominators."""
    c = qs.aggregate(
        total=Count("id"),
        fully_paid=Count("id", filter=Q(status="fully_paid")),
        current=Count("id", filter=Q(status="current")),
        late=Count("id", filter=Q(status="late")),
        default=Count("id", filter=Q(status="default")),
        charged_off=Count("id", filter=Q(status="charged_off")),
        unknown=Count("id", filter=Q(status="unknown")),
        recoveries=Sum("recoveries", filter=BAD_Q),
        funded=Sum(Case(When(BAD_Q, then=F("funded_amount")), output_field=DecimalField())),
        principal=Sum(Case(When(BAD_Q, then=F("principal_received")), output_field=DecimalField())),
    )
    resolved = c["fully_paid"] + c["default"] + c["charged_off"]
    active = c["current"] + c["late"]
    loss_exposure = float((c["funded"] or 0) - (c["principal"] or 0))
    rec = float(c["recoveries"] or 0)
    return {
        **{k: c[k] for k in ("total", "fully_paid", "current", "late", "default", "charged_off", "unknown")},
        "resolved_loans": resolved,
        "default_rate": _rate(c["default"] + c["charged_off"], resolved),
        "default_rate_denominator": "resolved loans (fully paid + default + charged off)",
        "charge_off_rate": _rate(c["charged_off"], resolved),
        "delinquency_rate": _rate(c["late"], active),
        "delinquency_rate_denominator": "active loans (current + late)",
        "recovery_rate": _rate(rec, loss_exposure) if loss_exposure > 0 else None,
        "recovery_rate_denominator": "funded amount minus principal received on default/charged-off loans",
    }


def vintage_by_issue_year(qs):
    """Cohort view: loans, resolved share and default rate per issue year."""
    rows = (
        qs.exclude(issue_date__isnull=True)
        .annotate(_y=ExtractYear("issue_date"))
        .values("_y")
        .annotate(
            loans=Count("id"),
            funded=Sum("funded_amount"),
            resolved=Count("id", filter=RESOLVED_Q),
            bad=Count("id", filter=BAD_Q),
        )
        .order_by("_y")
    )
    return [
        {
            "issue_year": r["_y"],
            "loans": r["loans"],
            "funded_amount": float(r["funded"] or 0),
            "resolved_share": _rate(r["resolved"], r["loans"]),
            "default_rate": _rate(r["bad"], r["resolved"]),
        }
        for r in rows
    ]
