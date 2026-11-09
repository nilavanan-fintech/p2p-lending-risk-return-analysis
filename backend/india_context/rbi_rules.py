"""India context layer: NBFC-P2P regulatory limits as data + rule checks.

PROVENANCE WARNING: the figures below were taken from secondary press/legal
commentary (Business Standard, Medianama, Mondaq, 1finance) found in research,
NOT read from the RBI text. Each rule carries verified=False until the author
confirms it against the Master Direction - NBFC-P2P (2017) as amended by RBI
circular RBI/2024-25/63 dated 16 Aug 2024. These rules are for ACADEMIC
compliance-checking illustrations only, not legal advice.

Amounts are in INR. They are applied to *synthetic or hypothetical* exposures
supplied by the caller; they are not applied to the (US) LendingClub data.
"""
from __future__ import annotations

from dataclasses import dataclass

LAKH = 100_000


@dataclass(frozen=True)
class Rule:
    code: str
    description: str
    limit_inr: int | None
    verified: bool = False
    source: str = "secondary press/legal commentary; verify vs RBI/2024-25/63"


RULES = {
    "LENDER_AGGREGATE_CAP": Rule("LENDER_AGGREGATE_CAP",
                                 "Aggregate exposure of one lender across all P2P platforms", 50 * LAKH),
    "LENDER_CA_CERT_THRESHOLD": Rule("LENDER_CA_CERT_THRESHOLD",
                                     "Lender exposure above which a CA net-worth certificate (>= INR 50 lakh) is needed",
                                     10 * LAKH),
    "BORROWER_AGGREGATE_CAP": Rule("BORROWER_AGGREGATE_CAP",
                                   "Aggregate borrowing of one borrower across all P2P platforms", 10 * LAKH),
    "LENDER_TO_BORROWER_CAP": Rule("LENDER_TO_BORROWER_CAP",
                                   "One lender's exposure to one borrower on one platform", 50_000),
    "NO_CREDIT_RISK": Rule("NO_CREDIT_RISK",
                           "Platform must not assume credit risk or provide guarantees (qualitative)", None),
}


def check_lender(total_exposure_inr: float, has_ca_certificate: bool = False) -> list[dict]:
    """Return a list of findings for one lender's aggregate exposure."""
    out = []
    r = RULES["LENDER_AGGREGATE_CAP"]
    out.append({"rule": r.code, "passed": total_exposure_inr <= r.limit_inr,
                "detail": f"exposure {total_exposure_inr:,.0f} vs cap {r.limit_inr:,}", "verified": r.verified})
    r = RULES["LENDER_CA_CERT_THRESHOLD"]
    need = total_exposure_inr > r.limit_inr
    out.append({"rule": r.code, "passed": (not need) or has_ca_certificate,
                "detail": "CA certificate required and " + ("present" if has_ca_certificate else "absent")
                if need else "certificate not required at this exposure", "verified": r.verified})
    return out


def check_borrower(total_borrowing_inr: float) -> dict:
    r = RULES["BORROWER_AGGREGATE_CAP"]
    return {"rule": r.code, "passed": total_borrowing_inr <= r.limit_inr,
            "detail": f"borrowing {total_borrowing_inr:,.0f} vs cap {r.limit_inr:,}", "verified": r.verified}


def check_lender_to_borrower(exposure_inr: float) -> dict:
    r = RULES["LENDER_TO_BORROWER_CAP"]
    return {"rule": r.code, "passed": exposure_inr <= r.limit_inr,
            "detail": f"exposure {exposure_inr:,.0f} vs cap {r.limit_inr:,}", "verified": r.verified}


# Press-reported NPA figures (aggregate, NOT loan-level, NOT audited).
PRESS_REPORTED_NPA = [
    {"platform": "Faircent", "period": "c. FY21", "npa_pct": "6-7", "source":
     "https://www.businesstoday.in/personal-finance/investment/story/14-percent-return-in-a-year-p2p-lending-catches-investors-eyes-294575-2021-04-28"},
    {"platform": "LenDenClub", "period": "FY21", "npa_pct": "3.94", "source":
     "https://www.businesstoday.in/personal-finance/investment/story/14-percent-return-in-a-year-p2p-lending-catches-investors-eyes-294575-2021-04-28"},
    {"platform": "LenDenClub", "period": "FY20", "npa_pct": "5.82", "source":
     "https://www.businesstoday.in/personal-finance/investment/story/14-percent-return-in-a-year-p2p-lending-catches-investors-eyes-294575-2021-04-28"},
]
