"""Read-only analytics endpoints for Power BI (Web connector / CSV) and users.

Every endpoint is GET-only and requires authentication. Add ?source=<name> to
scope to one DataSource; ?export=csv returns a flat CSV that Power BI's
Text/CSV or Web connector can load directly.
"""
import csv

from django.http import Http404, HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

from india_context import rbi_rules
from lending_data.models import DataSource, Loan
from portfolio_analysis import services as pf
from return_analysis import services as rt
from risk_analysis import services as rk


def _qs(request):
    qs = Loan.objects.all()
    name = request.query_params.get("source")
    if name:
        if not DataSource.objects.filter(name=name).exists():
            raise Http404(f"Unknown source {name!r}")
        qs = qs.filter(source__name=name)
    return qs


def _respond(request, rows, filename):
    if request.query_params.get("export") == "csv":
        rows = rows if isinstance(rows, list) else [rows]
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
        if rows:
            w = csv.DictWriter(resp, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        return resp
    return Response(rows)


@api_view(["GET"])
def sources(request):
    rows = [{"name": s.name, "kind": s.kind, "country": s.country, "version": s.version,
             "period": s.period, "loans": s.loans.count()} for s in DataSource.objects.all()]
    return _respond(request, rows, "sources")


@api_view(["GET"])
def status_summary(request):
    return _respond(request, rk.status_summary(_qs(request)), "status_summary")


@api_view(["GET"])
def default_rate(request, dimension):
    fn = {
        "grade": rk.default_rate_by_grade, "purpose": rk.default_rate_by_purpose,
        "term": rk.default_rate_by_term, "interest": rk.default_rate_by_interest_band,
        "dti": rk.default_rate_by_dti_band, "income": rk.default_rate_by_income_band,
        "amount": rk.default_rate_by_loan_amount_band, "fico": rk.default_rate_by_fico_band,
    }.get(dimension)
    if fn is None:
        raise Http404("dimension must be one of grade, purpose, term, interest, dti, income, amount, fico")
    return _respond(request, fn(_qs(request)), f"default_rate_by_{dimension}")


@api_view(["GET"])
def vintage(request):
    return _respond(request, rk.vintage_by_issue_year(_qs(request)), "vintage")


@api_view(["GET"])
def returns(request, dimension):
    if dimension == "overall":
        return _respond(request, rt.overall_return(_qs(request)), "return_overall")
    if dimension not in {"grade", "term_months", "purpose"}:
        raise Http404("dimension must be overall, grade, term_months or purpose")
    return _respond(request, rt.return_by(_qs(request), dimension), f"return_by_{dimension}")


@api_view(["GET"])
def portfolio(request, dimension):
    if dimension not in {"grade", "term_months", "purpose"}:
        raise Http404("dimension must be grade, term_months or purpose")
    return _respond(request, pf.allocation(_qs(request), dimension), f"allocation_{dimension}")


@api_view(["GET"])
def concentration(request, dimension):
    if dimension not in {"grade", "term_months", "purpose"}:
        raise Http404("dimension must be grade, term_months or purpose")
    return Response(pf.concentration(_qs(request), dimension))


@api_view(["GET"])
def default_exposure(request):
    return Response(pf.default_exposure(_qs(request)))


LOAN_EXPORT_FIELDS = [
    "loan_id", "source__name", "source__kind", "grade", "sub_grade", "purpose", "term_months",
    "issue_date", "loan_amount", "funded_amount", "investor_funded_amount", "interest_rate",
    "annual_income", "dti", "employment_years", "home_ownership", "fico_low", "fico_high",
    "delinq_2yrs", "revolving_utilization", "status", "total_payment", "principal_received",
    "interest_received", "recoveries", "recovery_fees", "outstanding_principal", "last_payment_date",
]


class _Echo:
    def write(self, value):
        return value


@api_view(["GET"])
def loans_export(request):
    """Streaming flat loan-level CSV = the Power BI fact table (Loans)."""
    import csv as _csv
    from django.http import StreamingHttpResponse

    qs = _qs(request).order_by("id").values_list(*LOAN_EXPORT_FIELDS)
    writer = _csv.writer(_Echo())

    def rows():
        yield writer.writerow([f.replace("__", "_") for f in LOAN_EXPORT_FIELDS])
        for r in qs.iterator(chunk_size=5000):
            yield writer.writerow(r)

    resp = StreamingHttpResponse(rows(), content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="loans.csv"'
    return resp


@api_view(["GET"])
def india_rules(request):
    rows = [{"code": r.code, "description": r.description, "limit_inr": r.limit_inr,
             "verified": r.verified, "source": r.source} for r in rbi_rules.RULES.values()]
    return _respond(request, rows, "rbi_rules")
