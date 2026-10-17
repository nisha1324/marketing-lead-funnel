-- Q15. Which kinds of seller start selling? Activation by lead type
-- Business question: the sales rep records a lead type when a deal is won
-- (e.g. online_medium, offline, industry). Which types turn into active
-- sellers, and which sign but don't sell? This tells sales which deals need
-- onboarding help and which types to prioritise.
-- Same sellers and definitions as Q12. Lead types with fewer than 30 sellers
-- are pooled; the Wilson 95% interval shows how uncertain each rate is.
WITH s AS (
    SELECT COALESCE(lead_type, '(missing)') AS lead_type, sold_90d, gmv_90d
    FROM signed_sellers
    WHERE observed_90d
),
type_group AS (
    SELECT lead_type,
           CASE WHEN COUNT(*) >= 30 THEN lead_type ELSE 'other types (pooled)' END AS type_group
    FROM s
    GROUP BY lead_type
),
grouped AS (
    SELECT
        g.type_group                                                 AS lead_type,
        COUNT(*)                                                     AS sellers,
        COUNT(*) FILTER (s.sold_90d)                                 AS sold_90d,
        SUM(s.gmv_90d)                                               AS gmv_90d,
        MEDIAN(s.gmv_90d) FILTER (s.sold_90d)                        AS median_gmv_per_active_seller,
        MAX(s.gmv_90d)                                               AS top_seller_gmv
    FROM s JOIN type_group g USING (lead_type)
    GROUP BY g.type_group
),
rates AS (
    SELECT *, sold_90d::DOUBLE / sellers AS p, 1.96 AS z FROM grouped
)
SELECT
    lead_type,
    sellers,
    ROUND(100.0 * sellers / SUM(sellers) OVER (), 1)                 AS pct_of_sellers,
    sold_90d,
    ROUND(100 * p, 1)                                                AS pct_sold_90d,
    ROUND(100 * (p + z*z/(2*sellers) - z * SQRT(p*(1-p)/sellers + z*z/(4*sellers*sellers)))
          / (1 + z*z/sellers), 1)                                    AS ci95_low,
    ROUND(100 * (p + z*z/(2*sellers) + z * SQRT(p*(1-p)/sellers + z*z/(4*sellers*sellers)))
          / (1 + z*z/sellers), 1)                                    AS ci95_high,
    ROUND(gmv_90d, 2)                                                AS gmv_90d,
    ROUND(100.0 * gmv_90d / SUM(gmv_90d) OVER (), 1)                 AS pct_of_gmv,
    ROUND(median_gmv_per_active_seller, 2)                           AS median_gmv_per_active_seller,
    ROUND(100.0 * top_seller_gmv / NULLIF(gmv_90d, 0), 1)            AS top_seller_pct_of_gmv
FROM rates
ORDER BY lead_type LIKE 'other types%', sellers DESC;
