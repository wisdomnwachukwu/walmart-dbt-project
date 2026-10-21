SELECT COUNT(order_id)
FROM {{ ref('obt_b') }}