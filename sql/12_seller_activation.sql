-- Q12. After the deal: how many signed sellers start selling, by month signed
-- Business question: signing a seller only pays off when it sells. What share
-- of signed sellers make a sale in their first 90 days, and how much do they
-- sell? Joins the won deals to Olist's public e-commerce orders by seller_id.
-- Sellers: every deal won 2017-12-05 .. 2018-05-23, so each has a full 90 days
-- before the order data thins out on 2018-08-22 (see pipeline/build_db.py).
-- A sale is an order that wasn't cancelled or unavailable; GMV is the item
-- price, without freight. "No sale" means no sale in the public order data,
-- which may not hold every Olist order, so rates are a lower bound.
WITH s AS (
    SELECT
        *,
        COALESCE(first_sale_at < won_date + INTERVAL 30 DAY, false) AS sold_30d,
        COALESCE(first_sale_at < won_date + INTERVAL 60 DAY, false) AS sold_60d,
        DATE_DIFF('hour', won_date, first_sale_at) / 24.0           AS days_to_first_sale
    FROM signed_sellers
    WHERE observed_90d
),
grouped AS (
    SELECT
        COALESCE(STRFTIME(signed_month, '%Y-%m'), 'TOTAL')           AS signed_month,
        COUNT(*)                                                     AS sellers,
        COUNT(*) FILTER (sold_30d)                                   AS sold_30d,
        COUNT(*) FILTER (sold_60d)                                   AS sold_60d,
        COUNT(*) FILTER (sold_90d)                                   AS sold_90d,
        MEDIAN(days_to_first_sale) FILTER (sold_90d)                 AS median_days_to_first_sale,
        SUM(orders_90d)                                              AS orders_90d,
        SUM(gmv_90d)                                                 AS gmv_90d,
        MEDIAN(gmv_90d) FILTER (sold_90d)                            AS median_gmv_per_active_seller,
        MAX(gmv_90d)                                                 AS top_seller_gmv
    FROM s
    GROUP BY ROLLUP (signed_month)
)
SELECT
    signed_month,
    sellers,
    sold_30d,
    sold_60d,
    sold_90d,
    ROUND(100.0 * sold_90d / sellers, 1)                             AS pct_sold_90d,
    ROUND(median_days_to_first_sale, 1)                              AS median_days_to_first_sale,
    orders_90d::BIGINT                                               AS orders_90d,
    ROUND(gmv_90d, 2)                                                AS gmv_90d,
    ROUND(median_gmv_per_active_seller, 2)                           AS median_gmv_per_active_seller,
    -- one large seller can dominate a month's GMV; show how much
    ROUND(100.0 * top_seller_gmv / NULLIF(gmv_90d, 0), 1)            AS top_seller_pct_of_gmv
FROM grouped
ORDER BY signed_month = 'TOTAL', signed_month;
