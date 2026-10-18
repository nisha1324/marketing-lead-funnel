-- Q17. Do manufacturers start selling as often as resellers?
-- Business question: the sales rep records whether a seller makes its own
-- products (manufacturer) or resells. If manufacturers sign but don't sell,
-- they need different onboarding, or a different pitch.
-- Same sellers and definitions as Q12. Manufacturers are more often offline or
-- industry leads (Q15), which start selling less, so a raw gap could just be
-- lead-type mix. pct_sold_90d_type_adjusted removes that: it is the group's
-- rate within each lead type, weighted by how common that lead type is among
-- all sellers (direct standardisation). Lead types with fewer than 30 sellers
-- are pooled into one stratum; strata a group has no sellers in are skipped
-- and the weights rescaled over the rest (adjusted_weight_pct shows how much
-- of the overall mix that covers).
WITH s AS (
    SELECT COALESCE(business_type, '(missing)') AS business_type,
           COALESCE(lead_type, '(missing)')     AS lead_type,
           sold_90d, gmv_90d
    FROM signed_sellers
    WHERE observed_90d
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
    SELECT s.business_type, g.stratum, AVG(s.sold_90d::INT) AS rate
    FROM s JOIN strata g USING (lead_type)
    GROUP BY s.business_type, g.stratum
),
adjusted AS (
    SELECT business_type,
           SUM(c.rate * w.weight) / SUM(w.weight)                    AS p_adj,
           SUM(w.weight)                                             AS weight_covered
    FROM cell c JOIN weights w USING (stratum)
    GROUP BY business_type
),
grouped AS (
    SELECT
        business_type,
        COUNT(*)                                                     AS sellers,
        COUNT(*) FILTER (sold_90d)                                   AS sold_90d,
        SUM(gmv_90d)                                                 AS gmv_90d,
        MEDIAN(gmv_90d) FILTER (sold_90d)                            AS median_gmv_per_active_seller,
        MAX(gmv_90d)                                                 AS top_seller_gmv
    FROM s
    GROUP BY business_type
),
rates AS (
    SELECT *, sold_90d::DOUBLE / sellers AS p, 1.96 AS z
    FROM grouped JOIN adjusted USING (business_type)
)
SELECT
    business_type,
    sellers,
    ROUND(100.0 * sellers / SUM(sellers) OVER (), 1)                 AS pct_of_sellers,
    sold_90d,
    ROUND(100 * p, 1)                                                AS pct_sold_90d,
    ROUND(100 * (p + z*z/(2*sellers) - z * SQRT(p*(1-p)/sellers + z*z/(4*sellers*sellers)))
          / (1 + z*z/sellers), 1)                                    AS ci95_low,
    ROUND(100 * (p + z*z/(2*sellers) + z * SQRT(p*(1-p)/sellers + z*z/(4*sellers*sellers)))
          / (1 + z*z/sellers), 1)                                    AS ci95_high,
    ROUND(100 * p_adj, 1)                                            AS pct_sold_90d_type_adjusted,
    ROUND(100 * weight_covered, 1)                                   AS adjusted_weight_pct,
    ROUND(100.0 * gmv_90d / SUM(gmv_90d) OVER (), 1)                 AS pct_of_gmv,
    ROUND(median_gmv_per_active_seller, 2)                           AS median_gmv_per_active_seller,
    -- one large seller can dominate a group's sales value; show how much
    ROUND(100.0 * top_seller_gmv / NULLIF(gmv_90d, 0), 1)            AS top_seller_pct_of_gmv
FROM rates
ORDER BY business_type = '(missing)', sellers DESC;
