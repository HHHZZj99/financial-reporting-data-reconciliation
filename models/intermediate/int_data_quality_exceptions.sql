with transaction_rows as (
    select
        *,
        row_number() over (
            partition by transaction_id
            order by transaction_date nulls last, account_id nulls last
        ) as source_row_number,
        row_number() over () as source_row_id
    from {{ ref('stg_transactions') }}
),
payment_rows as (
    select *, row_number() over () as source_row_id
    from {{ ref('stg_payments') }}
),
exceptions as (
    select
        'transactions' as source_name,
        coalesce(transaction_id, 'row_' || cast(source_row_id as varchar)) as record_key,
        'MISSING_TRANSACTION_ID' as issue_type,
        transaction_date as event_date,
        currency,
        amount
    from transaction_rows
    where transaction_id is null

    union all

    select
        'transactions', transaction_id, 'DUPLICATE_TRANSACTION_ID',
        transaction_date, currency, amount
    from transaction_rows
    where transaction_id is not null and source_row_number > 1

    union all

    select
        'transactions', transaction_id, 'INVALID_TRANSACTION_AMOUNT',
        transaction_date, currency, amount
    from transaction_rows
    where transaction_id is not null and amount is null

    union all

    select
        'payments', coalesce(payment_id, 'row_' || cast(source_row_id as varchar)),
        'MISSING_PAYMENT_ID', payment_date, currency, amount
    from payment_rows
    where payment_id is null

    union all

    select
        'payments', coalesce(payment_id, 'row_' || cast(source_row_id as varchar)),
        'MISSING_TRANSACTION_REFERENCE', payment_date, currency, amount
    from payment_rows
    where transaction_id is null

    union all

    select
        'payments', payment_id, 'INVALID_PAYMENT_AMOUNT',
        payment_date, currency, amount
    from payment_rows
    where payment_id is not null and amount is null
)
select * from exceptions
