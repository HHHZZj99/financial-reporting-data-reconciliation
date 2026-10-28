-- Illustrative SQL checks for a warehouse implementation.
-- Expected input tables: stg_transactions, stg_payments

-- 1. Duplicate transaction IDs
SELECT transaction_id, COUNT(*) AS row_count
FROM stg_transactions
GROUP BY transaction_id
HAVING COUNT(*) > 1;

-- 2. Transaction IDs without a payment
SELECT t.transaction_id, t.amount, t.currency
FROM stg_transactions t
LEFT JOIN stg_payments p USING (transaction_id)
WHERE p.transaction_id IS NULL;

-- 3. Amount / currency mismatches
SELECT
    t.transaction_id,
    t.amount AS transaction_amount,
    p.amount AS payment_amount,
    t.currency AS transaction_currency,
    p.currency AS payment_currency
FROM stg_transactions t
JOIN stg_payments p USING (transaction_id)
WHERE ABS(t.amount - p.amount) > 0.009
   OR t.currency <> p.currency;
