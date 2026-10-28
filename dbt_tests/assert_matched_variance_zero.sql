select transaction_id, variance
from {{ ref('fct_reconciliation') }}
where reconciliation_status = 'MATCHED'
  and abs(coalesce(variance, 0)) > 0.009
