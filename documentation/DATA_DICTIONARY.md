# Data dictionary (`lending_data.Loan`)

Source column names follow the LendingClub layout. Fields absent from a file stay NULL (recorded in `ImportBatch.missing_columns`).

| Field | Source column | Phase | Notes |
|---|---|---|---|
| loan_id | id | origination | unique per source |
| borrower | member_id | origination | anonymised key only; usually absent in public data |
| loan_amount / funded_amount / investor_funded_amount | loan_amnt / funded_amnt / funded_amnt_inv | origination | investor contribution = funded_amnt_inv |
| term_months | term | origination | "36 months" -> 36 |
| interest_rate | int_rate | origination | percent |
| grade / sub_grade / purpose / issue_date | grade / sub_grade / purpose / issue_d | origination | |
| annual_income, dti, employment_years | annual_inc, dti, emp_length | origination | "<1 year"=0, "10+"=10 |
| fico_low / fico_high | fico_range_low / high | origination | |
| delinq_2yrs, public_records, revolving_*, open/total accounts | delinq_2yrs, pub_rec, revol_*, open_acc, total_acc | origination | |
| loan_status_raw / status | loan_status | **outcome** | standardised: fully_paid, current, late, default, charged_off, unknown |
| total_payment, principal_received, interest_received, recoveries, recovery_fees, outstanding_principal, last_payment_* | total_pymnt, total_rec_prncp, total_rec_int, recoveries, collection_recovery_fee, out_prncp, last_pymnt_* | **outcome** | **Never use as ML features** (leakage) |

Not available in LendingClub: payment-by-payment dates (so no XIRR), borrower identity, platform fees to investors beyond collection fees.
