import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from reconcile import build_reconciliation, build_daily_summary

def test_duplicate_transaction_is_not_double_counted():
    tx = pd.DataFrame([
        {"transaction_id":"T1","transaction_date":pd.Timestamp("2026-10-01"),"account_id":"A1","currency":"USD","amount":10.0,"status":"settled"},
        {"transaction_id":"T1","transaction_date":pd.Timestamp("2026-10-01"),"account_id":"A1","currency":"USD","amount":10.0,"status":"settled"},
    ])
    pay = pd.DataFrame([
        {"payment_id":"P1","transaction_id":"T1","payment_date":pd.Timestamp("2026-10-01"),"currency":"USD","amount":10.0,"payment_status":"captured"}
    ])
    result, duplicates = build_reconciliation(tx, pay)
    assert len(result) == 1
    assert len(duplicates) == 1
    assert result.iloc[0]["reconciliation_status"] == "MATCHED"

def test_amount_mismatch_is_flagged():
    tx = pd.DataFrame([
        {"transaction_id":"T2","transaction_date":pd.Timestamp("2026-10-01"),"account_id":"A1","currency":"USD","amount":15.0,"status":"settled"}
    ])
    pay = pd.DataFrame([
        {"payment_id":"P2","transaction_id":"T2","payment_date":pd.Timestamp("2026-10-01"),"currency":"USD","amount":12.0,"payment_status":"captured"}
    ])
    result, _ = build_reconciliation(tx, pay)
    assert result.iloc[0]["reconciliation_status"] == "AMOUNT_MISMATCH"
    assert result.iloc[0]["variance"] == 3.0

def test_orphan_payment_is_flagged():
    tx = pd.DataFrame(columns=["transaction_id","transaction_date","account_id","currency","amount","status"])
    pay = pd.DataFrame([
        {"payment_id":"P3","transaction_id":"UNKNOWN","payment_date":pd.Timestamp("2026-10-01"),"currency":"USD","amount":4.0,"payment_status":"captured"}
    ])
    result, _ = build_reconciliation(tx, pay)
    assert result.iloc[0]["reconciliation_status"] == "ORPHAN_PAYMENT"
