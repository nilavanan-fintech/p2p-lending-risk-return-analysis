from decimal import Decimal

import pytest

# The importer needs pandas; skip (visibly) where the host blocks its DLLs.
pd = pytest.importorskip("pandas", reason="pandas cannot be imported in this environment", exc_type=ImportError)

from lending_data.models import DataSource, Loan  # noqa: E402
from lending_data.services import parsing as p  # noqa: E402
from lending_data.services.importer import import_file  # noqa: E402

pytestmark = pytest.mark.django_db


def _write(tmp_path, rows):
    path = tmp_path / "loans.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


BASE = {"id": "1", "loan_amnt": "5000", "int_rate": "10.5%", "term": " 36 months",
        "grade": "b", "loan_status": "Fully Paid", "issue_d": "Jan-2016", "member_id": "m1"}


def test_import_valid_duplicate_and_rejected(tmp_path):
    rows = [
        BASE,
        {**BASE, "id": "2", "loan_status": "Charged Off", "member_id": "m1"},
        {**BASE, "id": "1"},                      # duplicate within file
        {**BASE, "id": "3", "loan_amnt": "-5"},   # rejected: negative amount
        {**BASE, "id": "4", "int_rate": "abc"},   # rejected: non-numeric rate
    ]
    src = DataSource.objects.create(name="t", kind="synthetic")
    res = import_file(_write(tmp_path, rows), src)
    b = res.batch
    assert (b.rows_read, b.rows_imported, b.rows_duplicate, b.rows_rejected) == (5, 2, 1, 2)
    loan = Loan.objects.get(loan_id="1")
    assert loan.grade == "B" and loan.term_months == 36 and loan.status == "fully_paid"
    assert Loan.objects.get(loan_id="2").is_bad
    assert Loan.objects.get(loan_id="1").borrower_id == Loan.objects.get(loan_id="2").borrower_id
    # absent columns are reported, not fabricated
    assert "annual_inc" in b.missing_columns and loan.annual_income is None


def test_reimport_is_idempotent(tmp_path):
    src = DataSource.objects.create(name="t", kind="synthetic")
    path = _write(tmp_path, [BASE])
    import_file(path, src)
    res = import_file(path, src)
    assert res.batch.rows_imported == 0 and res.batch.rows_duplicate == 1
    assert Loan.objects.count() == 1


def test_missing_required_columns(tmp_path):
    src = DataSource.objects.create(name="t", kind="synthetic")
    with pytest.raises(ValueError):
        import_file(_write(tmp_path, [{"id": "1"}]), src)


def test_excel_import(tmp_path):
    path = tmp_path / "loans.xlsx"
    pd.DataFrame([BASE]).to_excel(path, index=False)
    src = DataSource.objects.create(name="x", kind="observed")
    assert import_file(path, src).batch.rows_imported == 1
