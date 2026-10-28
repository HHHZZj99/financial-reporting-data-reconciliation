with source as (
    select * from {{ ref('transactions') }}
)

select
    nullif(trim(cast(transaction_id as varchar)), '') as transaction_id,
    try_cast(transaction_date as date) as transaction_date,
    nullif(trim(cast(account_id as varchar)), '') as account_id,
    upper(nullif(trim(cast(currency as varchar)), '')) as currency,
    try_cast(amount as decimal(18, 2)) as amount,
    lower(nullif(trim(cast(status as varchar)), '')) as transaction_status
from source
