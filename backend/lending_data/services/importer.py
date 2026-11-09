"""CSV / Excel importer for LendingClub-schema loan files.

Design rules:
* Only columns actually present in the file are used. Absent expected columns
  are recorded on the ImportBatch (``missing_columns``) - never invented.
* Rows failing validation are rejected and counted, not silently dropped.
* Re-importing the same file is idempotent: existing (source, loan_id) pairs
  are skipped and counted as duplicates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from django.db import transaction

from borrowers.models import Borrower
from lending_data.models import DataSource, ImportBatch, Loan

from . import parsing as p

# model field -> (source column, parser)
FIELD_MAP: dict[str, tuple[str, callable]] = {
    "loan_amount": ("loan_amnt", p.to_decimal),
    "funded_amount": ("funded_amnt", p.to_decimal),
    "investor_funded_amount": ("funded_amnt_inv", p.to_decimal),
    "term_months": ("term", p.parse_term_months),
    "interest_rate": ("int_rate", p.to_decimal),
    "installment": ("installment", p.to_decimal),
    "grade": ("grade", lambda v: "" if p.is_blank(v) else str(v).strip().upper()),
    "sub_grade": ("sub_grade", lambda v: "" if p.is_blank(v) else str(v).strip().upper()),
    "purpose": ("purpose", lambda v: "" if p.is_blank(v) else str(v).strip().lower()),
    "issue_date": ("issue_d", p.parse_date),
    "annual_income": ("annual_inc", p.to_decimal),
    "dti": ("dti", p.to_decimal),
    "employment_years": ("emp_length", p.parse_employment_years),
    "home_ownership": ("home_ownership", lambda v: "" if p.is_blank(v) else str(v).strip().upper()),
    "verification_status": ("verification_status", lambda v: "" if p.is_blank(v) else str(v).strip()),
    "earliest_credit_line": ("earliest_cr_line", p.parse_date),
    "fico_low": ("fico_range_low", p.to_int),
    "fico_high": ("fico_range_high", p.to_int),
    "delinq_2yrs": ("delinq_2yrs", p.to_int),
    "public_records": ("pub_rec", p.to_int),
    "revolving_balance": ("revol_bal", p.to_decimal),
    "revolving_utilization": ("revol_util", p.to_decimal),
    "open_accounts": ("open_acc", p.to_int),
    "total_accounts": ("total_acc", p.to_int),
    "total_payment": ("total_pymnt", p.to_decimal),
    "principal_received": ("total_rec_prncp", p.to_decimal),
    "interest_received": ("total_rec_int", p.to_decimal),
    "late_fees_received": ("total_rec_late_fee", p.to_decimal),
    "recoveries": ("recoveries", p.to_decimal),
    "recovery_fees": ("collection_recovery_fee", p.to_decimal),
    "outstanding_principal": ("out_prncp", p.to_decimal),
    "last_payment_date": ("last_pymnt_d", p.parse_date),
    "last_payment_amount": ("last_pymnt_amnt", p.to_decimal),
}
ID_COLUMN = "id"
BORROWER_COLUMN = "member_id"
STATUS_COLUMN = "loan_status"
REQUIRED = ("id", "loan_amnt", "int_rate")
CHUNK = 20_000


@dataclass
class ImportResult:
    batch: ImportBatch
    errors: list[str] = field(default_factory=list)


def read_frames(path: Path):
    """Yield DataFrames of strings (chunked for CSV, whole sheet for Excel)."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        # LendingClub files have a banner line before the header and footer rows.
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            first = fh.readline()
        skip = 1 if first.lower().startswith("notes offered") else 0
        yield from pd.read_csv(
            path, dtype=str, chunksize=CHUNK, skiprows=skip, on_bad_lines="skip", encoding_errors="replace"
        )
    elif suffix in {".xlsx", ".xlsm"}:
        yield pd.read_excel(path, dtype=str, engine="openpyxl")
    else:
        raise ValueError(f"Unsupported file type {suffix!r}; use .csv or .xlsx")


def _build_loan(row: dict, source: DataSource, columns: set[str]) -> Loan:
    loan_id = row.get(ID_COLUMN)
    if p.is_blank(loan_id):
        raise ValueError("missing loan id")
    loan_id = str(loan_id).strip()
    kwargs = {}
    for model_field, (col, parser) in FIELD_MAP.items():
        if col in columns:
            kwargs[model_field] = parser(row.get(col))
    if kwargs.get("loan_amount") is None:
        raise ValueError("missing loan amount")
    if kwargs["loan_amount"] <= 0:
        raise ValueError("loan amount must be positive")
    if kwargs.get("interest_rate") is None:
        raise ValueError("missing interest rate")
    if not (0 <= kwargs["interest_rate"] <= 100):
        raise ValueError(f"interest rate out of range: {kwargs['interest_rate']}")
    fl, fh = kwargs.get("fico_low"), kwargs.get("fico_high")
    if fl is not None and fh is not None and fl > fh:
        raise ValueError("fico_low > fico_high")
    raw_status = row.get(STATUS_COLUMN) if STATUS_COLUMN in columns else None
    kwargs["loan_status_raw"] = "" if p.is_blank(raw_status) else str(raw_status).strip()
    kwargs["status"] = p.standardise_status(raw_status)
    return Loan(source=source, loan_id=loan_id, **kwargs)


@transaction.atomic
def import_file(path: str | Path, source: DataSource) -> ImportResult:
    path = Path(path)
    batch = ImportBatch.objects.create(source=source, filename=path.name)
    errors: list[str] = []
    seen = set(Loan.objects.filter(source=source).values_list("loan_id", flat=True))
    borrower_cache: dict[str, Borrower] = {
        b.external_id: b for b in Borrower.objects.filter(source=source)
    }
    read = imported = dup = rejected = 0
    columns_seen: set[str] = set()

    for frame in read_frames(path):
        frame.columns = [str(c).strip() for c in frame.columns]
        columns = set(frame.columns)
        columns_seen |= columns
        if not set(REQUIRED) <= columns:
            raise ValueError(f"File is missing required columns: {sorted(set(REQUIRED) - columns)}")
        to_create: list[Loan] = []
        for rec in frame.to_dict("records"):
            read += 1
            try:
                loan = _build_loan(rec, source, columns)
            except ValueError as exc:
                rejected += 1
                if len(errors) < 25:
                    errors.append(f"row {read}: {exc}")
                continue
            if loan.loan_id in seen:
                dup += 1
                continue
            seen.add(loan.loan_id)
            ext = rec.get(BORROWER_COLUMN) if BORROWER_COLUMN in columns else None
            if not p.is_blank(ext):
                ext = str(ext).strip()
                if ext not in borrower_cache:
                    borrower_cache[ext] = Borrower.objects.create(source=source, external_id=ext)
                loan.borrower = borrower_cache[ext]
            to_create.append(loan)
        Loan.objects.bulk_create(to_create, batch_size=2000)
        imported += len(to_create)

    expected = {c for c, _ in FIELD_MAP.values()} | {STATUS_COLUMN}
    batch.rows_read, batch.rows_imported = read, imported
    batch.rows_duplicate, batch.rows_rejected = dup, rejected
    batch.missing_columns = ", ".join(sorted(expected - columns_seen))
    batch.errors_sample = "\n".join(errors)
    batch.save()
    return ImportResult(batch=batch, errors=errors)
