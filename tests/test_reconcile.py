import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reconcile import build_daily_summary, build_reconciliation  # noqa: E402


def _transaction(transaction_id="T1", amount=10.0, currency="USD", date="2026-10-01"):
    return {
        "transaction_id": transaction_id,
        "transaction_date": pd.Timestamp(date) if date else pd.NaT,
        "account_id": "A1",
        "currency": currency,
        "amount": amount,
        "status": "settled",
    }


def _payment(payment_id="P1", transaction_id="T1", amount=10.0, currency="USD"):
    return {
        "payment_id": payment_id,
        "transaction_id": transaction_id,
        "payment_date": pd.Timestamp("2026-10-01"),
        "currency": currency,
        "amount": amount,
        "payment_status": "captured",
    }


def test_duplicate_transaction_is_not_double_counted():
    tx = pd.DataFrame([_transaction(), _transaction()])
    pay = pd.DataFrame([_payment()])
    result, exceptions = build_reconciliation(tx, pay)
    assert len(result) == 1
    assert len(exceptions) == 1
    assert exceptions.iloc[0]["issue_type"] == "DUPLICATE_TRANSACTION_ID"
    assert result.iloc[0]["reconciliation_status"] == "MATCHED"


def test_amount_mismatch_is_flagged():
    result, _ = build_reconciliation(pd.DataFrame([_transaction(amount=15.0)]), pd.DataFrame([_payment(amount=12.0)]))
    assert result.iloc[0]["reconciliation_status"] == "AMOUNT_MISMATCH"
    assert result.iloc[0]["variance"] == 3.0


def test_orphan_payment_is_flagged():
    result, _ = build_reconciliation(pd.DataFrame(columns=["transaction_id", "transaction_date", "account_id", "currency", "amount", "status"]), pd.DataFrame([_payment(transaction_id="UNKNOWN")]))
    assert result.iloc[0]["reconciliation_status"] == "ORPHAN_PAYMENT"


def test_missing_payment_is_flagged():
    result, _ = build_reconciliation(pd.DataFrame([_transaction()]), pd.DataFrame(columns=["payment_id", "transaction_id", "payment_date", "currency", "amount", "payment_status"]))
    assert result.iloc[0]["reconciliation_status"] == "MISSING_PAYMENT"


def test_currency_mismatch_is_flagged_even_when_amount_also_differs():
    result, _ = build_reconciliation(pd.DataFrame([_transaction(amount=15.0)]), pd.DataFrame([_payment(amount=12.0, currency="EUR")]))
    assert result.iloc[0]["reconciliation_status"] == "CURRENCY_MISMATCH"


def test_multiple_payment_currencies_are_not_silently_ignored():
    payments = pd.DataFrame([_payment(payment_id="P1", amount=5.0, currency="USD"), _payment(payment_id="P2", amount=5.0, currency="EUR")])
    result, _ = build_reconciliation(pd.DataFrame([_transaction()]), payments)
    assert result.iloc[0]["reconciliation_status"] == "CURRENCY_MISMATCH"


def test_invalid_transaction_date_is_flagged():
    result, _ = build_reconciliation(pd.DataFrame([_transaction(date=None)]), pd.DataFrame([_payment()]))
    assert result.iloc[0]["reconciliation_status"] == "INVALID_TRANSACTION_DATE"


def test_missing_source_ids_are_isolated_as_data_quality_exceptions():
    tx = pd.DataFrame([_transaction(transaction_id=None)])
    pay = pd.DataFrame([_payment(payment_id=None)])
    result, exceptions = build_reconciliation(tx, pay)
    assert result.empty
    assert set(exceptions["issue_type"]) == {"MISSING_TRANSACTION_ID", "MISSING_PAYMENT_ID"}


def test_daily_summary_excludes_orphan_payments_and_keeps_currency_separate():
    rows = pd.DataFrame([
        {"transaction_id": "T1", "transaction_date": pd.Timestamp("2026-10-01"), "currency": "USD", "amount": 10.0, "payment_amount": 10.0, "reconciliation_status": "MATCHED"},
        {"transaction_id": "T2", "transaction_date": pd.Timestamp("2026-10-01"), "currency": "USD", "amount": 5.0, "payment_amount": None, "reconciliation_status": "MISSING_PAYMENT"},
        {"transaction_id": "T3", "transaction_date": pd.Timestamp("2026-10-01"), "currency": "GBP", "amount": 8.0, "payment_amount": 8.0, "reconciliation_status": "MATCHED"},
        {"transaction_id": "ORPHAN", "transaction_date": pd.NaT, "currency": None, "amount": None, "payment_amount": 4.0, "reconciliation_status": "ORPHAN_PAYMENT"},
    ])
    summary = build_daily_summary(rows)
    assert len(summary) == 2
    usd = summary.loc[summary["currency"].eq("USD")].iloc[0]
    assert usd["transaction_count"] == 2
    assert usd["transaction_amount"] == 15.0
    assert usd["payment_amount"] == 10.0
    assert usd["variance"] == 5.0
