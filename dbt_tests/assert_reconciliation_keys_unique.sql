select transaction_id
from {{ ref('fct_reconciliation') }}
group by transaction_id
having count(*) > 1
