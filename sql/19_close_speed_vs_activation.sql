-- Q19. Do deals that close fast become better sellers?
-- Business question: Part 1 found most deals sign within two weeks. Is a
-- quick "yes" also a sign of a seller ready to sell, so that sales should
-- move on from slow leads sooner, or do slow deals sell just as well?
-- Same sellers and definitions as Q12; days to close = first contact -> deal
-- won (the one deal dated 2 days before its first contact counts as day 0).
-- Two checks before reading a gap as real:
--   z_vs_first_14d: two-proportion z statistic against the 0-14 day group
--     (pooled standard error); |z| below 1.96 is not significant at the 5% level.
--   pct_sold_90d_type_adjusted: the rate within each lead type, weighted by
--     the overall lead-type mix (direct standardisation, as in Q17), so a gap
--     isn't just slow deals being a different kind of seller.
-- The last row pools every deal that took more than 14 days.
WITH s AS (
    SELECT GREATEST(days_to_close, 0) AS days, COALESCE(lead_type, '(missing)') AS lead_type,
           sold_90d, gmv_90d, DATE_DIFF('hour', won_date, first_sale_at) / 24.0 AS days_to_first_sale
    FROM signed_sellers
    WHERE observed_90d
),
bucketed AS (
    SELECT *,
           CASE WHEN days <= 14 THEN '0-14 days'
                WHEN days <= 30 THEN '15-30 days'
                WHEN days <= 60 THEN '31-60 days'
                ELSE '61+ days' END                                  AS bucket
    FROM s
),
labelled AS (
    -- every seller once in its bucket, and the slow ones again in the pooled row
    SELECT bucket, * EXCLUDE (bucket) FROM bucketed
    UNION ALL
    SELECT 'over 14 days (pooled)', * EXCLUDE (bucket) FROM bucketed WHERE days > 14
),
strata AS (
    SELECT lead_type,
           CASE WHEN COUNT(*) >= 30 THEN lead_type ELSE 'other types (pooled)' END AS stratum
    FROM s
    GROUP BY lead_type
),
weights AS (
    SELECT g.stratum, COUNT(*)::DOUBLE / SUM(COUNT(*)) OVER () AS weight
    FROM s JOIN strata g USING (lead_type)
    GROUP BY g.stratum
),
cell AS (
    SELECT l.bucket, g.stratum, AVG(l.sold_90d::INT) AS rate
    FROM labelled l JOIN strata g USING (lead_type)
    GROUP BY l.bucket, g.stratum
),
adjusted AS (
    SELECT bucket, SUM(c.rate * w.weight) / SUM(w.weight) AS p_adj
    FROM cell c JOIN weights w USING (stratum)
    GROUP BY bucket
),
grouped AS (
    SELECT
        bucket,
        MIN(days)                                                    AS min_days,
        MAX(days)                                                    AS max_days,
        COUNT(*)                                                     AS sellers,
        COUNT(*) FILTER (sold_90d)                                   AS sold_90d,
        MEDIAN(days_to_first_sale) FILTER (sold_90d)                 AS median_days_to_first_sale,
        MEDIAN(gmv_90d) FILTER (sold_90d)                            AS median_gmv_per_active_seller
    FROM labelled
    GROUP BY bucket
),
rates AS (
    SELECT g.*, a.p_adj, g.sold_90d::DOUBLE / g.sellers AS p, 1.96 AS z,
           f.sold_90d AS f_sold, f.sellers AS f_n
    FROM grouped g
    JOIN adjusted a USING (bucket)
    CROSS JOIN (SELECT sold_90d, sellers FROM grouped WHERE bucket = '0-14 days') f
)
SELECT
    bucket,
    min_days,
    max_days,
    sellers,
    sold_90d,
    ROUND(100 * p, 1)                                                AS pct_sold_90d,
    ROUND(100 * (p + z*z/(2*sellers) - z * SQRT(p*(1-p)/sellers + z*z/(4*sellers*sellers)))
          / (1 + z*z/sellers), 1)                                    AS ci95_low,
    ROUND(100 * (p + z*z/(2*sellers) + z * SQRT(p*(1-p)/sellers + z*z/(4*sellers*sellers)))
          / (1 + z*z/sellers), 1)                                    AS ci95_high,
    ROUND(100 * p_adj, 1)                                            AS pct_sold_90d_type_adjusted,
    CASE WHEN bucket = '0-14 days' THEN NULL ELSE ROUND(
        (p - f_sold::DOUBLE / f_n)
        / SQRT(((sold_90d + f_sold)::DOUBLE / (sellers + f_n))
               * (1 - (sold_90d + f_sold)::DOUBLE / (sellers + f_n))
               * (1.0 / sellers + 1.0 / f_n)), 2) END                AS z_vs_first_14d,
    ROUND(median_days_to_first_sale, 1)                              AS median_days_to_first_sale,
    ROUND(median_gmv_per_active_seller, 2)                           AS median_gmv_per_active_seller
FROM rates
ORDER BY bucket LIKE 'over%', min_days;
