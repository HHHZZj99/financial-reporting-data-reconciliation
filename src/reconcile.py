from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"

def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    transactions = pd.read_csv(RAW / "transactions.csv", dtype={"transaction_id": "string", "account_id": "string"})
    payments = pd.read_csv(RAW / "payments.csv", dtype={"payment_id": "string", "transaction_id": "string"})
    for df, date_col in [(transactions, "transaction_date"), (payments, "payment_date")]:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").round(2)
    return transactions, payments

def build_reconciliation(transactions: pd.DataFrame, payments: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    tx = transactions.copy()
    duplicate_mask = tx.duplicated(subset=["transaction_id"], keep="first")
    duplicate_rows = tx.loc[duplicate_mask].copy()
    duplicate_rows["issue_type"] = "DUPLICATE_TRANSACTION_ID"
    tx = tx.loc[~duplicate_mask].copy()

    # Aggregate payment records per transaction so multiple payment rows do not multiply transaction rows.
    pay = payments.copy()
    pay_agg = pay.groupby("transaction_id", dropna=False).agg(
        payment_ids=("payment_id", lambda s: "|".join(s.astype(str))),
        payment_count=("payment_id", "count"),
        payment_amount=("amount", "sum"),
        payment_currency=("currency", "first"),
        payment_status=("payment_status", "first"),
    ).reset_index()

    result = tx.merge(pay_agg, on="transaction_id", how="outer", indicator=True)
    result["variance"] = (result["amount"] - result["payment_amount"]).round(2)
    result["reconciliation_status"] = "MATCHED"
    result.loc[result["_merge"].eq("left_only"), "reconciliation_status"] = "MISSING_PAYMENT"
    result.loc[result["_merge"].eq("right_only"), "reconciliation_status"] = "ORPHAN_PAYMENT"

    both = result["_merge"].eq("both")
    result.loc[both & result["currency"].ne(result["payment_currency"]), "reconciliation_status"] = "CURRENCY_MISMATCH"
    result.loc[both & result["variance"].abs().gt(0.009), "reconciliation_status"] = "AMOUNT_MISMATCH"
    result.loc[both & result["transaction_date"].isna(), "reconciliation_status"] = "INVALID_TRANSACTION_DATE"
    result.loc[both & result["amount"].isna(), "reconciliation_status"] = "INVALID_TRANSACTION_AMOUNT"
    result = result.drop(columns=["_merge"])
    return result, duplicate_rows

def build_daily_summary(reconciliation: pd.DataFrame) -> pd.DataFrame:
    valid = reconciliation[reconciliation["transaction_id"].notna()].copy()
    valid["transaction_date"] = pd.to_datetime(valid["transaction_date"], errors="coerce")
    summary = valid.groupby(["transaction_date", "currency"], dropna=False).agg(
        transaction_count=("transaction_id", "nunique"),
        transaction_amount=("amount", "sum"),
        payment_amount=("payment_amount", "sum"),
        exception_count=("reconciliation_status", lambda s: (s != "MATCHED").sum()),
    ).reset_index()
    summary["variance"] = (summary["transaction_amount"] - summary["payment_amount"]).round(2)
    return summary

def run() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    transactions, payments = load_data()
    reconciliation, duplicates = build_reconciliation(transactions, payments)
    daily = build_daily_summary(reconciliation)
    reconciliation.to_csv(REPORTS / "reconciliation_report.csv", index=False, date_format="%Y-%m-%d")
    duplicates.to_csv(REPORTS / "duplicate_transactions.csv", index=False, date_format="%Y-%m-%d")
    daily.to_csv(REPORTS / "daily_financial_summary.csv", index=False, date_format="%Y-%m-%d")
    print(f"Input transactions: {len(transactions)}")
    print(f"Unique transactions after duplicate handling: {transactions['transaction_id'].nunique()}")
    print(f"Reconciliation rows: {len(reconciliation)}")
    print(f"Exceptions: {(reconciliation['reconciliation_status'] != 'MATCHED').sum()}")
    print(f"Duplicate rows isolated: {len(duplicates)}")
    print(f"Reports written to: {REPORTS}")

if __name__ == "__main__":
    run()
