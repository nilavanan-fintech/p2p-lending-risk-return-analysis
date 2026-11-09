"""Portfolio allocation and concentration analytics.

Diversification reduces idiosyncratic (single-borrower) risk only; it does NOT
remove systematic/credit-cycle risk. Outputs state this explicitly.
"""
from __future__ import annotations

from django.db.models import Count, Q, Sum
from django.db.models.functions import ExtractYear

from lending_data.models import Loan
from return_analysis.calculations import effective_number, herfindahl

NOTE = ("HHI measures concentration of funded amount across categories (0-10,000; "
        "<1,500 unconcentrated, 1,500-2,500 moderate, >2,500 high - US DOJ convention). "
        "Diversification lowers idiosyncratic risk but does not eliminate credit risk.")


def allocation(qs, field: str) -> list[dict]:
    rows = qs.values(field).annotate(loans=Count("id"), funded=Sum("funded_amount"),
                                     outstanding=Sum("outstanding_principal")).order_by(field)
    total = sum(float(r["funded"] or 0) for r in rows) or 0
    return [{
        "group": r[field] if r[field] not in (None, "") else "Unknown",
        "loans": r["loans"],
        "funded_amount": float(r["funded"] or 0),
        "share": round(float(r["funded"] or 0) / total, 4) if total else None,
        "outstanding_principal": float(r["outstanding"] or 0),
    } for r in rows]


def concentration(qs, field: str) -> dict:
    alloc = allocation(qs, field)
    hhi = herfindahl([a["funded_amount"] for a in alloc])
    return {
        "dimension": field,
        "hhi": round(hhi, 1) if hhi is not None else None,
        "effective_categories": round(effective_number(hhi), 2) if hhi else None,
        "largest_category": max(alloc, key=lambda a: a["funded_amount"])["group"] if alloc else None,
        "note": NOTE,
    }


def default_exposure(qs) -> dict:
    bad = qs.filter(status__in=[s.value for s in Loan.BAD]).aggregate(
        loans=Count("id"), funded=Sum("funded_amount"), principal=Sum("principal_received"),
        recoveries=Sum("recoveries"))
    funded_all = qs.aggregate(f=Sum("funded_amount"))["f"] or 0
    exposure = float((bad["funded"] or 0) - (bad["principal"] or 0))
    return {
        "defaulted_loans": bad["loans"],
        "defaulted_funded_amount": float(bad["funded"] or 0),
        "loss_exposure": exposure,
        "recoveries": float(bad["recoveries"] or 0),
        "share_of_funded": round(exposure / float(funded_all), 4) if funded_all else None,
    }


def by_issue_year(qs) -> list[dict]:
    return [{"issue_year": r["y"], "loans": r["n"], "funded_amount": float(r["f"] or 0)}
            for r in qs.exclude(issue_date__isnull=True).annotate(y=ExtractYear("issue_date"))
            .values("y").annotate(n=Count("id"), f=Sum("funded_amount")).order_by("y")]
