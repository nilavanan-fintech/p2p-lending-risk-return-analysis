# P2P Lending Risk & Return Analysis

Django backend + Microsoft Power BI analytics for peer-to-peer lending risk and
investor-return research. **Academic analysis only - not credit approval or
investment advice.**

## Data provenance (read first)
| Layer | Source | Status |
|---|---|---|
| Loan-level analytics | LendingClub public dataset (US, 2007-2018) - *you supply the file* | Observed, US, proxy for methodology |
| India context | RBI NBFC-P2P directions + press-reported NPA (`india_context/`) | Rules unverified until checked vs RBI/2024-25/63; aggregate only |
| Demo data | `generate_sample_data` | **SYNTHETIC** - never report as results |

No public loan-level Indian P2P dataset was found. Missing fields are left empty, never fabricated.

## Quick start (local, SQLite)
```bash
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
cd backend
python manage.py migrate
python manage.py createsuperuser
python manage.py generate_sample_data --rows 2000          # synthetic demo CSV -> data/sample/
python manage.py import_loans ../data/sample/synthetic_loans.csv --source "Synthetic demo" --kind synthetic
python manage.py import_loans ../data/raw/accepted_loans.csv --source "LendingClub" --kind observed --country US
python manage.py runserver
pytest
```

## Analytics API (authenticated, read-only; `?source=<name>`, `?export=csv`)
`/api/analytics/` -> `status-summary/`, `default-rate/{grade|purpose|term|interest|dti|income|amount|fico}/`,
`vintage/`, `returns/{overall|grade|term_months|purpose}/`, `portfolio/{dim}/`, `concentration/{dim}/`,
`default-exposure/`, `india-rules/`, `loans.csv` (Power BI fact table).

## Metric definitions
- **Default rate** = (default + charged off) / resolved loans. Current/late loans are excluded (outcome unknown).
- **Delinquency rate** = late / (current + late). **Charge-off rate** = charged off / resolved.
- **Recovery rate** = recoveries / (funded - principal received) on bad loans.
- **Returns** use resolved loans only. IRR/XIRR are computed only from real dated cash flows
  (LendingClub publishes totals, so XIRR is not derivable from it). See `return_analysis/calculations.py`.

## Layout
`backend/` Django apps (`lending_data`, `borrowers`, `risk_analysis`, `return_analysis`, `portfolio_analysis`,
`reporting`, `india_context`) - `powerbi/` DAX, Power Query, theme - `data/` - `documentation/` - `deployment/`.

## Docker
```bash
cp .env.example .env     # set POSTGRES_PASSWORD and DJANGO_SECRET_KEY
docker compose up --build
```
Power BI Desktop runs on the Windows host (not in a container) and connects to `http://localhost:8000/api/analytics`.

## Status
See `documentation/ROADMAP.md`.
