# Financial Reporting & Data Reconciliation

A portfolio project demonstrating a reproducible financial reconciliation pipeline using Python, pandas, SQL, and automated tests. The dataset is synthetic and contains intentionally planted exceptions.

## Business problem

Finance teams need to confirm that transactions recorded by an internal system agree with payment-provider records. This project identifies mismatches and produces reporting-ready outputs for investigation.

## Pipeline

1. Load transaction and payment CSV files.
2. isolate duplicate transaction IDs to a separate exception file.
3. Aggregate payment rows by transaction ID to avoid join fan-out.
4. Reconcile transaction and payment records.
5. Classify missing payments, orphan payments, amount mismatches, and currency mismatches.
6. Export reconciliation, duplicate, and daily summary reports.
7. Run automated tests for key reconciliation rules.

## Architecture

```text
data/raw/*.csv
      |
      v
Python ingestion + validation
      |
      v
Deduplicate transactions / aggregate payments
      |
      v
Reconciliation rules
      |
      +--> reports/reconciliation_report.csv
      +--> reports/duplicate_transactions.csv
      +--> reports/daily_financial_summary.csv
      |
      v
pytest automated checks
```

## Quick start

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows
pip install -r requirements.txt
python src/reconcile.py
pytest -q
```

## Outputs

- `reports/reconciliation_report.csv` — one row per transaction or orphan payment, with reconciliation status and variance.
- `reports/duplicate_transactions.csv` — duplicate transaction rows isolated from the main reconciliation.
- `reports/daily_financial_summary.csv` — daily transaction/payment totals by currency and exception counts.

## Reconciliation statuses

| Status | Meaning |
|---|---|
| `MATCHED` | Transaction and payment amounts/currencies agree |
| `MISSING_PAYMENT` | Transaction exists but no payment record was found |
| `ORPHAN_PAYMENT` | Payment references a transaction that does not exist |
| `AMOUNT_MISMATCH` | Transaction and payment amounts differ |
| `CURRENCY_MISMATCH` | Transaction and payment currencies differ |
| `INVALID_TRANSACTION_DATE` | Transaction date could not be parsed |
| `INVALID_TRANSACTION_AMOUNT` | Transaction amount is missing or invalid |

Duplicate transaction IDs are exported separately and only the first occurrence is retained in the reconciliation run. In a production pipeline, the duplicate policy should be explicitly agreed with Finance before any record is excluded.

## Data quality and design choices

- Currency is retained as a grouping dimension; different currencies are never summed together.
- Monetary values are rounded to two decimal places for this demo.
- Payment records are aggregated before joining to avoid accidental row multiplication.
- Exceptions remain visible instead of being silently discarded.
- The sample data is fictional and must not be interpreted as real financial information.

## SQL examples

`sql/reconciliation_checks.sql` contains warehouse-oriented SQL checks that can be adapted to Snowflake or another analytical database.

## Project roadmap

- [x] Synthetic source data and core reconciliation logic
- [x] CSV reporting outputs
- [x] Automated unit tests
- [x] Warehouse SQL check examples
- [ ] Add dbt staging and mart models
- [ ] Add a scheduled orchestration workflow
- [ ] Add dashboard screenshots and documented sample findings

## Limitations

This is a local portfolio demonstration, not a production financial control. It does not handle FX conversion, partial payments, reversals, settlement timing windows, or approval workflows.
