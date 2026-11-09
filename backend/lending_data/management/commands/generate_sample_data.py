"""Generate a SYNTHETIC demonstration CSV in LendingClub column layout.

Purpose: let the importer, analytics and Power BI exports be exercised without
the (large) real dataset. Values are random draws from stated assumptions -
they are NOT real borrowers, loans or returns, and must never be reported as
observed results. Rows are tagged with ids prefixed 'SYN' and the file is
meant to be imported with --kind synthetic.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand

GRADES = list("ABCDEFG")
# Assumed (illustrative) 36-month default probabilities and rates by grade.
P_DEFAULT = dict(zip(GRADES, [0.05, 0.10, 0.16, 0.22, 0.28, 0.34, 0.40]))
RATE = dict(zip(GRADES, [7.5, 11.0, 14.0, 17.0, 20.5, 24.0, 27.0]))
PURPOSES = ["debt_consolidation", "credit_card", "home_improvement", "small_business", "car", "medical", "other"]


class Command(BaseCommand):
    help = "Write a synthetic demo CSV (LendingClub layout) to data/sample/."

    def add_arguments(self, parser):
        parser.add_argument("--rows", type=int, default=2000)
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--out", type=Path, default=Path("../data/sample/synthetic_loans.csv"))

    def handle(self, *args, **o):
        rng = np.random.default_rng(o["seed"])
        n = o["rows"]
        grade = rng.choice(GRADES, n, p=[.2, .28, .25, .15, .08, .03, .01])
        amount = rng.choice(np.arange(1000, 35001, 500), n)
        term = rng.choice([36, 60], n, p=[.75, .25])
        rate = np.array([RATE[g] for g in grade]) + rng.normal(0, 1.0, n)
        dti = np.clip(rng.normal(18, 8, n), 0, 45).round(2)
        income = np.exp(rng.normal(11.1, 0.5, n)).round(0)
        p_bad = np.clip(np.array([P_DEFAULT[g] for g in grade]) + (dti - 18) * 0.004, 0.01, 0.8)
        u = rng.random(n)
        issue = pd.to_datetime("2015-01-01") + pd.to_timedelta(rng.integers(0, 365 * 3, n), unit="D")
        outcome = np.where(u < p_bad, "Charged Off", np.where(u < p_bad + 0.08, "Current", "Fully Paid"))
        bad, paid = outcome == "Charged Off", outcome == "Fully Paid"
        interest_full = amount * rate / 100 * term / 12 * 0.55
        frac = np.where(bad, rng.uniform(0.2, 0.7, n), np.where(paid, 1.0, rng.uniform(0.2, 0.6, n)))
        principal = np.where(paid, amount, amount * frac * np.where(bad, 0.8, 0.9)).round(2)
        interest = (interest_full * np.where(paid, 1.0, frac * 0.6)).round(2)
        recov = np.where(bad, (amount - principal) * rng.uniform(0, 0.15, n), 0).round(2)
        outstanding = np.where(outcome == "Current", amount - principal, 0).round(2)
        fico = rng.integers(620, 800, n)
        df = pd.DataFrame({
            "id": [f"SYN{i:06d}" for i in range(n)],
            "member_id": "", "loan_amnt": amount, "funded_amnt": amount, "funded_amnt_inv": amount,
            "term": [f" {t} months" for t in term], "int_rate": [f"{r:.2f}%" for r in rate],
            "installment": (amount * (1 + rate / 100 * term / 12) / term).round(2),
            "grade": grade, "sub_grade": [f"{g}{rng.integers(1, 6)}" for g in grade],
            "emp_length": rng.choice(["< 1 year", "3 years", "5 years", "10+ years", ""], n),
            "home_ownership": rng.choice(["RENT", "MORTGAGE", "OWN"], n), "annual_inc": income,
            "verification_status": rng.choice(["Verified", "Not Verified"], n),
            "issue_d": issue.strftime("%b-%Y"), "loan_status": outcome,
            "purpose": rng.choice(PURPOSES, n), "dti": dti,
            "delinq_2yrs": rng.poisson(0.3, n), "earliest_cr_line": "Jan-2000",
            "fico_range_low": fico, "fico_range_high": fico + 4, "pub_rec": rng.poisson(0.1, n),
            "revol_bal": rng.integers(0, 40000, n), "revol_util": np.clip(rng.normal(50, 25, n), 0, 100).round(1),
            "open_acc": rng.integers(2, 25, n), "total_acc": rng.integers(5, 50, n),
            "out_prncp": outstanding, "total_pymnt": (principal + interest + recov).round(2),
            "total_rec_prncp": principal, "total_rec_int": interest, "total_rec_late_fee": 0.0,
            "recoveries": recov, "collection_recovery_fee": (recov * 0.1).round(2),
            "last_pymnt_d": "Jan-2019", "last_pymnt_amnt": 0.0,
        })
        o["out"].parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(o["out"], index=False)
        self.stdout.write(self.style.SUCCESS(f"Wrote {n} SYNTHETIC rows to {o['out']}"))
