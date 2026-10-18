-- Q16. Which business segments start selling?
-- Business question: Part 2b profiled the segments the funnel signs. Do some
-- product categories sign sellers that don't then sell, so the marketplace
-- gets the signature but not the stock?
-- Same sellers and definitions as Q12. Segments with fewer than 20 sellers are
-- pooled; the Wilson 95% interval shows how uncertain each rate is. With 20-80
-- sellers per segment the intervals are wide, so only clear gaps are findings.
-- pct_manufacturers is shown because manufacturers start selling less often
-- than resellers (Q17), and some segments are mostly manufacturers.
WITH s AS (
    SELECT COALESCE(business_segment, '(missing)') AS segment, business_type, sold_90d, gmv_90d
    FROM signed_sellers
    WHERE observed_90d
),
segment_group AS (
    SELECT segment,
           CASE WHEN COUNT(*) >= 20 THEN segment ELSE 'smaller segments (pooled)' END AS segment_group
    FROM s
    GROUP BY segment
),
grouped AS (
    SELECT
        g.segment_group                                              AS segment,
        COUNT(DISTINCT s.segment)                                    AS segments,
        COUNT(*)                                                     AS sellers,
        COUNT(*) FILTER (s.sold_90d)                                 AS sold_90d,
        COUNT(*) FILTER (s.business_type = 'manufacturer')           AS manufacturers,
        SUM(s.gmv_90d)                                               AS gmv_90d,
        MEDIAN(s.gmv_90d) FILTER (s.sold_90d)                        AS median_gmv_per_active_seller,
        MAX(s.gmv_90d)                                               AS top_seller_gmv
    FROM s JOIN segment_group g USING (segment)
    GROUP BY g.segment_group
),
rates AS (
    SELECT *, sold_90d::DOUBLE / sellers AS p, 1.96 AS z FROM grouped
)
SELECT
    segment,
    segments,
    sellers,
    ROUND(100.0 * sellers / SUM(sellers) OVER (), 1)                 AS pct_of_sellers,
    sold_90d,
    ROUND(100 * p, 1)                                                AS pct_sold_90d,
    ROUND(100 * (p + z*z/(2*sellers) - z * SQRT(p*(1-p)/sellers + z*z/(4*sellers*sellers)))
          / (1 + z*z/sellers), 1)                                    AS ci95_low,
    ROUND(100 * (p + z*z/(2*sellers) + z * SQRT(p*(1-p)/sellers + z*z/(4*sellers*sellers)))
          / (1 + z*z/sellers), 1)                                    AS ci95_high,
    ROUND(100.0 * manufacturers / sellers, 1)                        AS pct_manufacturers,
    ROUND(100.0 * gmv_90d / SUM(gmv_90d) OVER (), 1)                 AS pct_of_gmv,
    ROUND(median_gmv_per_active_seller, 2)                           AS median_gmv_per_active_seller,
    -- one large seller can dominate a group's sales value; show how much
    ROUND(100.0 * top_seller_gmv / NULLIF(gmv_90d, 0), 1)            AS top_seller_pct_of_gmv
FROM rates
ORDER BY segment LIKE 'smaller%', sellers DESC, segment;
