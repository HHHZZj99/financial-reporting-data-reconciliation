select
    transaction_date,
    transaction_currency as currency,
    count(distinct transaction_id) as transaction_count,
    sum(transaction_amount) as transaction_amount,
    sum(coalesce(payment_amount, 0)) as payment_amount,
    sum(case when reconciliation_status = 'MATCHED' then 1 else 0 end) as matched_count,
    sum(case when reconciliation_status <> 'MATCHED' then 1 else 0 end) as exception_count,
    round(sum(transaction_amount) - sum(coalesce(payment_amount, 0)), 2) as variance
from {{ ref('fct_reconciliation') }}
where transaction_date is not null
group by transaction_date, transaction_currency
