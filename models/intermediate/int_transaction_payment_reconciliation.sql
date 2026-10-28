with ranked_transactions as (
    select
        *,
        row_number() over (
            partition by transaction_id
            order by transaction_date nulls last, account_id nulls last
        ) as source_row_number
    from {{ ref('stg_transactions') }}
    where transaction_id is not null
),
transactions_deduplicated as (
    select * exclude (source_row_number)
    from ranked_transactions
    where source_row_number = 1
),
payment_aggregates as (
    select
        transaction_id,
        string_agg(payment_id, '|' order by payment_id) as payment_ids,
        count(payment_id) as payment_count,
        sum(amount) as payment_amount,
        count(distinct currency) as payment_currency_count,
        min(currency) as payment_currency,
        count(*) filter (where amount is null) as invalid_payment_amount_count,
        count(*) filter (where currency is null) as invalid_payment_currency_count,
        string_agg(distinct payment_status, '|' order by payment_status) as payment_statuses
    from {{ ref('stg_payments') }}
    where transaction_id is not null
      and payment_id is not null
    group by transaction_id
),
joined as (
    select
        coalesce(t.transaction_id, p.transaction_id) as transaction_id,
        t.transaction_date,
        t.account_id,
        t.currency as transaction_currency,
        t.amount as transaction_amount,
        t.transaction_status,
        p.payment_ids,
        p.payment_count,
        p.payment_amount,
        p.payment_currency,
        p.payment_currency_count,
        p.invalid_payment_amount_count,
        p.invalid_payment_currency_count,
        p.payment_statuses,
        round(t.amount - p.payment_amount, 2) as variance,
        t.transaction_id is not null as has_transaction,
        p.transaction_id is not null as has_payment
    from transactions_deduplicated t
    full outer join payment_aggregates p
        on t.transaction_id = p.transaction_id
)

select
    *,
    case
        when not has_transaction then 'ORPHAN_PAYMENT'
        when not has_payment then 'MISSING_PAYMENT'
        when transaction_date is null then 'INVALID_TRANSACTION_DATE'
        when transaction_amount is null then 'INVALID_TRANSACTION_AMOUNT'
        when invalid_payment_amount_count > 0 then 'INVALID_PAYMENT_AMOUNT'
        when payment_currency_count > 1
          or invalid_payment_currency_count > 0
          or transaction_currency is null
          or payment_currency is null
          or transaction_currency <> payment_currency then 'CURRENCY_MISMATCH'
        when abs(variance) > 0.009 then 'AMOUNT_MISMATCH'
        else 'MATCHED'
    end as reconciliation_status
from joined
