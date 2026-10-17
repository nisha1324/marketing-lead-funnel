-- Q13. How long after signing does a seller make its first sale?
-- Business question: how long is the gap between "deal won" and "first
-- revenue", and how many signed sellers never sell? This sets when onboarding
-- should check in and when a silent seller is a churn risk.
-- Same sellers as Q12 (won 2017-12-05 .. 2018-05-23). Each row is the
-- cumulative share of *all* those sellers with a first sale before day N, so
-- sellers who never sold stay in the denominator. The last two rows split the
-- rest: a first sale after day 90 but before 2018-08-22, or none at all.
WITH s AS (
    SELECT won_date, first_sale_at
    FROM signed_sellers
    WHERE observed_90d
),
days AS (
    SELECT UNNEST([7, 14, 30, 45, 60, 90]) AS day
),
curve AS (
    SELECT
        'within ' || d.day || ' days'                                AS milestone,
        d.day                                                        AS sort_key,
        COUNT(*) FILTER (s.first_sale_at < s.won_date + TO_DAYS(d.day)) AS sellers
    FROM days d CROSS JOIN s
    GROUP BY d.day
),
rest AS (
    SELECT 'first sale after day 90' AS milestone, 1000 AS sort_key,
           COUNT(*) FILTER (first_sale_at >= won_date + INTERVAL 90 DAY) AS sellers
    FROM s
    UNION ALL
    SELECT 'no sale in the order data', 1001,
           COUNT(*) FILTER (first_sale_at IS NULL)
    FROM s
)
SELECT
    milestone,
    sellers,
    ROUND(100.0 * sellers / (SELECT COUNT(*) FROM s), 1)             AS pct_of_signed_sellers
FROM (SELECT * FROM curve UNION ALL SELECT * FROM rest)
ORDER BY sort_key;
