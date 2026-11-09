from django.core.validators import MinValueValidator
from django.db import models


class DataSource(models.Model):
    """Provenance record. Every loan belongs to exactly one source so that
    observed, real-world data is never mixed up with synthetic demo data."""

    class Kind(models.TextChoices):
        OBSERVED = "observed", "Observed (real public dataset)"
        SYNTHETIC = "synthetic", "Synthetic demonstration data"

    name = models.CharField(max_length=120, unique=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    country = models.CharField(max_length=60, blank=True)
    version = models.CharField(max_length=60, blank=True)
    period = models.CharField(max_length=60, blank=True, help_text="e.g. 2007-2018")
    url = models.URLField(blank=True)
    licence = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} [{self.kind}]"


class Loan(models.Model):
    class Status(models.TextChoices):
        FULLY_PAID = "fully_paid", "Fully paid"
        CURRENT = "current", "Current"
        LATE = "late", "Late / in grace period"
        DEFAULT = "default", "Default"
        CHARGED_OFF = "charged_off", "Charged off"
        UNKNOWN = "unknown", "Unmapped status"

    # Statuses where the final outcome is known (denominator for default rate).
    RESOLVED = (Status.FULLY_PAID, Status.DEFAULT, Status.CHARGED_OFF)
    BAD = (Status.DEFAULT, Status.CHARGED_OFF)

    source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name="loans")
    loan_id = models.CharField(max_length=64)
    borrower = models.ForeignKey(
        "borrowers.Borrower", null=True, blank=True, on_delete=models.SET_NULL, related_name="loans"
    )

    # --- Origination terms (known at application time) ---
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    funded_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    investor_funded_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, help_text="Investor contribution"
    )
    term_months = models.PositiveSmallIntegerField(null=True, blank=True)
    interest_rate = models.DecimalField(max_digits=6, decimal_places=3, help_text="Annual %, e.g. 13.56")
    installment = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    grade = models.CharField(max_length=2, blank=True, db_index=True)
    sub_grade = models.CharField(max_length=3, blank=True)
    purpose = models.CharField(max_length=60, blank=True, db_index=True)
    issue_date = models.DateField(null=True, blank=True, db_index=True)

    # --- Borrower attributes at application time ---
    annual_income = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    dti = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    employment_years = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True, help_text="0 = <1 year, 10 = 10+ years"
    )
    home_ownership = models.CharField(max_length=20, blank=True)
    verification_status = models.CharField(max_length=30, blank=True)
    earliest_credit_line = models.DateField(null=True, blank=True)
    fico_low = models.PositiveSmallIntegerField(null=True, blank=True)
    fico_high = models.PositiveSmallIntegerField(null=True, blank=True)
    delinq_2yrs = models.PositiveSmallIntegerField(null=True, blank=True)
    public_records = models.PositiveSmallIntegerField(null=True, blank=True)
    revolving_balance = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    revolving_utilization = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    open_accounts = models.PositiveSmallIntegerField(null=True, blank=True)
    total_accounts = models.PositiveSmallIntegerField(null=True, blank=True)

    # --- Outcome / performance (POST-origination; never use as ML features) ---
    loan_status_raw = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.UNKNOWN, db_index=True)
    total_payment = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    principal_received = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    interest_received = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    late_fees_received = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    recoveries = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    recovery_fees = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    outstanding_principal = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    last_payment_date = models.DateField(null=True, blank=True)
    last_payment_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source", "loan_id"], name="uniq_loan_per_source")]
        indexes = [models.Index(fields=["source", "status"]), models.Index(fields=["source", "issue_date"])]

    @property
    def is_bad(self) -> bool:
        return self.status in self.BAD

    @property
    def is_resolved(self) -> bool:
        return self.status in self.RESOLVED

    def __str__(self) -> str:
        return f"Loan {self.loan_id} ({self.source_id})"


class ImportBatch(models.Model):
    """Audit trail for each file import, including rejected-row counts."""

    source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name="batches")
    filename = models.CharField(max_length=255)
    rows_read = models.PositiveIntegerField(default=0)
    rows_imported = models.PositiveIntegerField(default=0)
    rows_duplicate = models.PositiveIntegerField(default=0)
    rows_rejected = models.PositiveIntegerField(default=0)
    missing_columns = models.TextField(blank=True, help_text="Expected fields absent from the file")
    errors_sample = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.filename} ({self.rows_imported}/{self.rows_read})"
