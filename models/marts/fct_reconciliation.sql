select
    transaction_id,
    transaction_date,
    account_id,
    transaction_currency,
    transaction_amount,
    transaction_status,
    payment_ids,
    payment_count,
    payment_amount,
    payment_currency,
    payment_currency_count,
    payment_statuses,
    variance,
    reconciliation_status
from {{ ref('int_transaction_payment_reconciliation') }}
