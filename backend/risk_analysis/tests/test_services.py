from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from india_context import rbi_rules
from lending_data.models import DataSource, Loan
from portfolio_analysis import services as pf
from return_analysis import services as rt
from risk_analysis import services as rk

pytestmark = pytest.mark.django_db


@pytest.fixture
def src():
    return DataSource.objects.create(name="demo", kind="synthetic")


def mk(src, i, grade, status, rate="10", amt="1000", paid="0", dti="10", **kw):
    return Loan.objects.create(
        source=src, loan_id=str(i), grade=grade, status=status, loan_amount=Decimal(amt),
        funded_amount=Decimal(amt), interest_rate=Decimal(rate), dti=Decimal(dti),
        total_payment=Decimal(paid), principal_received=Decimal(paid), term_months=36, **kw)


@pytest.fixture
def loans(src):
    mk(src, 1, "A", "fully_paid", paid="1100", issue_date=date(2016, 1, 1), last_payment_date=date(2017, 1, 1))
    mk(src, 2, "A", "fully_paid", paid="1100", issue_date=date(2016, 1, 1), last_payment_date=date(2017, 1, 1))
    mk(src, 3, "B", "charged_off", paid="400", rate="14", dti="25", recoveries=Decimal("50"),
       issue_date=date(2017, 1, 1), last_payment_date=date(2018, 1, 1))
    mk(src, 4, "B", "fully_paid", paid="1150", rate="14", issue_date=date(2017, 1, 1),
       last_payment_date=date(2018, 1, 1))
    mk(src, 5, "B", "current", rate="14", outstanding_principal=Decimal("700"), issue_date=date(2018, 1, 1))
    mk(src, 6, "B", "late", rate="14", issue_date=date(2018, 1, 1))
    return Loan.objects.all()


def test_default_rate_excludes_unresolved(loans):
    rows = {r["group"]: r for r in rk.default_rate_by_grade(loans)}
    assert rows["A"]["default_rate"] == 0.0 and rows["A"]["resolved_loans"] == 2
    # B: resolved = 1 charged off + 1 paid; current/late excluded from denominator
    assert rows["B"]["resolved_loans"] == 2 and rows["B"]["default_rate"] == 0.5
    assert rows["B"]["all_loans"] == 4


def test_status_summary_denominators(loans):
    s = rk.status_summary(loans)
    assert s["total"] == 6 and s["resolved_loans"] == 4
    assert s["default_rate"] == 0.25 and s["charge_off_rate"] == 0.25
    assert s["delinquency_rate"] == 0.5          # 1 late / (1 current + 1 late)
    assert s["recovery_rate"] == pytest.approx(50 / 600, abs=1e-4)  # loss exposure 1000-400


def test_bands_keep_unknowns(loans, src):
    mk(src, 99, "C", "fully_paid", paid="1000", dti="10")
    Loan.objects.filter(loan_id="99").update(dti=None)
    groups = {r["group"] for r in rk.default_rate_by_dti_band(Loan.objects.all())}
    assert "Unknown" in groups and "0-10" not in groups or "10-20" in groups


def test_vintage(loans):
    v = {r["issue_year"]: r for r in rk.vintage_by_issue_year(loans)}
    assert v[2016]["default_rate"] == 0.0 and v[2017]["default_rate"] == 0.5
    assert v[2018]["default_rate"] is None  # nothing resolved yet -> undefined, not 0


def test_returns_resolved_only(loans):
    o = rt.overall_return(loans)
    assert o["loans"] == 4 and o["invested"] == 4000
    assert o["gross_return"] == pytest.approx((1100 + 1100 + 400 + 1150 - 4000) / 4000)
    assert o["outstanding_principal"] == 700
    by_grade = {r["group"]: r for r in rt.return_by(loans, "grade")}
    assert by_grade["A"]["gross_return"] == pytest.approx(0.10)
    assert by_grade["A"]["net_annualised_approx"] == pytest.approx(0.10, abs=0.01)


def test_portfolio_concentration(loans):
    c = pf.concentration(loans, "grade")
    # funded: A=2000, B=4000 -> shares 1/3, 2/3 -> HHI = 1111 + 4444
    assert c["hhi"] == pytest.approx(5555.6, abs=0.1) and c["largest_category"] == "B"
    assert "does not eliminate" in c["note"] or "not eliminate" in c["note"]


def test_rbi_rules_flag_unverified():
    assert all(not r.verified for r in rbi_rules.RULES.values())
    assert not rbi_rules.check_lender(60 * rbi_rules.LAKH)[0]["passed"]
    assert not rbi_rules.check_lender(20 * rbi_rules.LAKH)[1]["passed"]
    assert rbi_rules.check_lender(20 * rbi_rules.LAKH, has_ca_certificate=True)[1]["passed"]
    assert rbi_rules.check_lender_to_borrower(50_000)["passed"]
    assert not rbi_rules.check_borrower(11 * rbi_rules.LAKH)["passed"]


def test_api_requires_auth_and_serves_csv(loans):
    client = APIClient()
    assert client.get("/api/analytics/status-summary/").status_code in (401, 403)
    client.force_authenticate(get_user_model().objects.create_user("u", password="x"))
    assert client.get("/api/analytics/status-summary/").json()["total"] == 6
    r = client.get("/api/analytics/default-rate/grade/?export=csv")
    assert r["Content-Type"].startswith("text/csv") and b"default_rate" in r.content
    assert client.get("/api/analytics/default-rate/bogus/").status_code == 404
    assert client.get("/api/analytics/status-summary/?source=nope").status_code == 404
    assert client.post("/api/analytics/status-summary/").status_code == 405
    body = b"".join(client.get("/api/analytics/loans.csv?source=demo").streaming_content).decode()
    lines = body.strip().splitlines()
    assert lines[0].startswith("loan_id,source_name,source_kind") and len(lines) == 7
