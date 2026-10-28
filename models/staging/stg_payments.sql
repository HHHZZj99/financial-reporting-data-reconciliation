with source as (
    select * from {{ ref('payments') }}
)

select
    nullif(trim(cast(payment_id as varchar)), '') as payment_id,
    nullif(trim(cast(transaction_id as varchar)), '') as transaction_id,
    try_cast(payment_date as date) as payment_date,
    upper(nullif(trim(cast(currency as varchar)), '')) as currency,
    try_cast(amount as decimal(18, 2)) as amount,
    lower(nullif(trim(cast(payment_status as varchar)), '')) as payment_status
from source
