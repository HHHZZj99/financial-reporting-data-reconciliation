from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load source CSVs, normalising keys, dates, currencies and monetary values."""
    transactions = pd.read_csv(
        RAW / "transactions.csv",
        dtype={"transaction_id": "string", "account_id": "string"},
    )
    payments = pd.read_csv(
        RAW / "payments.csv",
        dtype={"payment_id": "string", "transaction_id": "string"},
    )

    transactions["transaction_id"] = transactions["transaction_id"].str.strip()
    payments["payment_id"] = payments["payment_id"].str.strip()
    payments["transaction_id"] = payments["transaction_id"].str.strip()
    transactions["currency"] = transactions["currency"].astype("string").str.strip().str.upper()
    payments["currency"] = payments["currency"].astype("string").str.strip().str.upper()
    transactions["transaction_date"] = pd.to_datetime(
        transactions["transaction_date"], errors="coerce"
    )
    payments["payment_date"] = pd.to_datetime(payments["payment_date"], errors="coerce")
    transactions["amount"] = pd.to_numeric(transactions["amount"], errors="coerce").round(2)
    payments["amount"] = pd.to_numeric(payments["amount"], errors="coerce").round(2)
    return transactions, payments


def _is_blank(values: pd.Series) -> pd.Series:
    """Return a mask for null or empty/whitespace identifiers."""
    as_string = values.astype("string").str.strip()
    return as_string.isna() | as_string.eq("")


def build_reconciliation(
    transactions: pd.DataFrame, payments: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return one row per reconcilable transaction key and a data-quality exception set.

    Duplicate transaction IDs are isolated and only the first source record is retained
    for this demo. Payment rows are aggregated before joining to prevent join fan-out.
    """
    tx = transactions.copy()
    pay = payments.copy()
    tx["transaction_id"] = tx["transaction_id"].astype("string").str.strip()
    pay["transaction_id"] = pay["transaction_id"].astype("string").str.strip()
    pay["payment_id"] = pay["payment_id"].astype("string").str.strip()

    exception_frames: list[pd.DataFrame] = []

    missing_tx_id = _is_blank(tx["transaction_id"])
    if missing_tx_id.any():
        rows = tx.loc[missing_tx_id].copy()
        rows["source_name"] = "transactions"
        rows["issue_type"] = "MISSING_TRANSACTION_ID"
        exception_frames.append(rows)
    tx = tx.loc[~missing_tx_id].copy()

    duplicate_mask = tx.duplicated(subset=["transaction_id"], keep="first")
    if duplicate_mask.any():
        rows = tx.loc[duplicate_mask].copy()
        rows["source_name"] = "transactions"
        rows["issue_type"] = "DUPLICATE_TRANSACTION_ID"
        exception_frames.append(rows)
    tx = tx.loc[~duplicate_mask].copy()

    missing_payment_id = _is_blank(pay["payment_id"])
    if missing_payment_id.any():
        rows = pay.loc[missing_payment_id].copy()
        rows["source_name"] = "payments"
        rows["issue_type"] = "MISSING_PAYMENT_ID"
        exception_frames.append(rows)
    pay = pay.loc[~missing_payment_id].copy()

    missing_payment_tx_id = _is_blank(pay["transaction_id"])
    if missing_payment_tx_id.any():
        rows = pay.loc[missing_payment_tx_id].copy()
        rows["source_name"] = "payments"
        rows["issue_type"] = "MISSING_TRANSACTION_REFERENCE"
        exception_frames.append(rows)
    pay = pay.loc[~missing_payment_tx_id].copy()

    tx["currency"] = tx["currency"].astype("string").str.strip().str.upper()
    pay["currency"] = pay["currency"].astype("string").str.strip().str.upper()

    # Aggregate payment records first so a one-to-many payment relationship cannot
    # accidentally multiply transaction amounts in downstream reporting.
    pay_agg = pay.groupby("transaction_id", dropna=False).agg(
        payment_ids=("payment_id", lambda s: "|".join(s.astype(str))),
        payment_count=("payment_id", "count"),
        payment_amount=("amount", lambda s: s.sum(min_count=1)),
        payment_currency_count=("currency", "nunique"),
        payment_currency=("currency", "first"),
        payment_status=("payment_status", "first"),
        invalid_payment_amount=("amount", lambda s: s.isna().any()),
        invalid_payment_currency=("currency", lambda s: s.isna().any() or s.astype("string").str.strip().eq("").any()),
    ).reset_index()

    result = tx.merge(
        pay_agg, on="transaction_id", how="outer", indicator=True, validate="one_to_one"
    )
    result["amount"] = pd.to_numeric(result["amount"], errors="coerce").astype("float64")
    result["payment_amount"] = pd.to_numeric(
        result["payment_amount"], errors="coerce"
    ).astype("float64")
    result["variance"] = (result["amount"] - result["payment_amount"]).round(2)
    result["reconciliation_status"] = "MATCHED"
    result.loc[result["_merge"].eq("left_only"), "reconciliation_status"] = "MISSING_PAYMENT"
    result.loc[result["_merge"].eq("right_only"), "reconciliation_status"] = "ORPHAN_PAYMENT"

    both = result["_merge"].eq("both")
    # Apply lower-priority rules first; data-quality failures take precedence over
    # amount variance, so one row receives the most actionable high-priority status.
    result.loc[
        both & result["variance"].abs().gt(0.009), "reconciliation_status"
    ] = "AMOUNT_MISMATCH"
    invalid_currency_flags = (
        result["invalid_payment_currency"].fillna(False).astype(bool)
    )
    invalid_amount_flags = (
        result["invalid_payment_amount"].fillna(False).astype(bool)
    )
    currency_problem = (
        result["payment_currency_count"].fillna(0).gt(1)
        | invalid_currency_flags
        | result["currency"].isna()
        | result["payment_currency"].isna()
        | result["currency"].ne(result["payment_currency"])
    )
    result.loc[both & currency_problem, "reconciliation_status"] = "CURRENCY_MISMATCH"
    result.loc[
        both & invalid_amount_flags, "reconciliation_status"
    ] = "INVALID_PAYMENT_AMOUNT"
    result.loc[
        both & result["amount"].isna(), "reconciliation_status"
    ] = "INVALID_TRANSACTION_AMOUNT"
    result.loc[
        both & result["transaction_date"].isna(), "reconciliation_status"
    ] = "INVALID_TRANSACTION_DATE"

    result = result.drop(columns=["_merge"])
    result["payment_currency_count"] = result["payment_currency_count"].fillna(0).astype(int)
    result["payment_count"] = result["payment_count"].fillna(0).astype(int)

    exceptions = (
        pd.concat(exception_frames, ignore_index=True, sort=False)
        if exception_frames
        else pd.DataFrame(columns=["source_name", "issue_type"])
    )
    return result, exceptions


def build_daily_summary(reconciliation: pd.DataFrame) -> pd.DataFrame:
    """Build daily totals from transaction-side records; orphan payments are excluded."""
    valid = reconciliation.loc[reconciliation["transaction_date"].notna()].copy()
    valid["transaction_date"] = pd.to_datetime(valid["transaction_date"], errors="coerce")
    summary = valid.groupby(["transaction_date", "currency"], dropna=False).agg(
        transaction_count=("transaction_id", "nunique"),
        transaction_amount=("amount", lambda s: s.sum(min_count=1)),
        payment_amount=("payment_amount", lambda s: s.fillna(0).sum()),
        exception_count=("reconciliation_status", lambda s: (s != "MATCHED").sum()),
        matched_count=("reconciliation_status", lambda s: (s == "MATCHED").sum()),
    ).reset_index()
    summary["variance"] = (summary["transaction_amount"] - summary["payment_amount"]).round(2)
    return summary


def run() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    transactions, payments = load_data()
    reconciliation, data_quality_exceptions = build_reconciliation(transactions, payments)
    daily = build_daily_summary(reconciliation)

    reconciliation.to_csv(
        REPORTS / "reconciliation_report.csv", index=False, date_format="%Y-%m-%d"
    )
    data_quality_exceptions.to_csv(
        REPORTS / "data_quality_exceptions.csv", index=False, date_format="%Y-%m-%d"
    )
    daily.to_csv(
        REPORTS / "daily_financial_summary.csv", index=False, date_format="%Y-%m-%d"
    )

    print(f"Input transaction rows: {len(transactions)}")
    print(f"Input payment rows: {len(payments)}")
    print(f"Reconciliation rows: {len(reconciliation)}")
    print(
        "Reconciliation exceptions: "
        f"{(reconciliation['reconciliation_status'] != 'MATCHED').sum()}"
    )
    print(f"Data-quality exception rows: {len(data_quality_exceptions)}")
    print(f"Reports written to: {REPORTS}")


if __name__ == "__main__":
    run()
