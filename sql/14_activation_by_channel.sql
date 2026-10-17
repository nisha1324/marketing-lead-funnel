-- Q14. Which channels bring sellers who actually sell?
-- Business question: Part 1 ranked channels by how many leads sign. Does the
-- ranking hold once we ask whether the signed seller then sells?
-- Sellers: deals won 2017-12-05 .. 2018-05-23, each followed for 90 days after
-- signing (as in Q12). Channels with fewer than 30 such sellers are pooled.
-- The 95% interval on the activation rate is a Wilson score interval.
-- selling_sellers_per_1k_leads chains the two steps: the channel's 90-day
-- lead-to-deal conversion (2018 cohorts, Q2) x its 90-day activation rate. The
-- two rates come from overlapping but not identical groups of leads, so it is
-- an estimate of "sellers who sell, per 1,000 leads", not a direct count.
WITH s AS (
    SELECT * FROM signed_sellers WHERE observed_90d
),
channel_group AS (
    SELECT origin,
           CASE WHEN COUNT(*) >= 30 THEN origin ELSE 'smaller channels (pooled)' END AS channel
    FROM s
    GROUP BY origin
),
sellers AS (
    SELECT
        g.channel,
        COUNT(*)                                                     AS sellers,
        COUNT(*) FILTER (s.sold_90d)                                 AS sold_90d,
        SUM(s.gmv_90d)                                               AS gmv_90d,
        MEDIAN(s.gmv_90d) FILTER (s.sold_90d)                        AS median_gmv_per_active_seller,
        MAX(s.gmv_90d)                                               AS top_seller_gmv
    FROM s JOIN channel_group g USING (origin)
    GROUP BY g.channel
),
leads_by_channel AS (
    SELECT
        COALESCE(g.channel, 'smaller channels (pooled)')             AS channel,
        COUNT(*)                                                     AS leads_2018,
        COUNT(*) FILTER (l.won_90d)                                  AS won_90d_2018
    FROM leads l LEFT JOIN channel_group g USING (origin)
    WHERE l.in_window
    GROUP BY 1
),
rates AS (
    SELECT *, sold_90d::DOUBLE / sellers AS p, 1.96 AS z
    FROM sellers JOIN leads_by_channel USING (channel)
)
SELECT
    channel,
    sellers,
    sold_90d,
    ROUND(100 * p, 1)                                                AS pct_sold_90d,
    ROUND(100 * (p + z*z/(2*sellers) - z * SQRT(p*(1-p)/sellers + z*z/(4*sellers*sellers)))
          / (1 + z*z/sellers), 1)                                    AS ci95_low,
    ROUND(100 * (p + z*z/(2*sellers) + z * SQRT(p*(1-p)/sellers + z*z/(4*sellers*sellers)))
          / (1 + z*z/sellers), 1)                                    AS ci95_high,
    ROUND(gmv_90d, 2)                                                AS gmv_90d,
    ROUND(100.0 * gmv_90d / SUM(gmv_90d) OVER (), 1)                 AS pct_of_gmv,
    ROUND(median_gmv_per_active_seller, 2)                           AS median_gmv_per_active_seller,
    ROUND(100.0 * top_seller_gmv / NULLIF(gmv_90d, 0), 1)            AS top_seller_pct_of_gmv,
    ROUND(100.0 * won_90d_2018 / leads_2018, 1)                      AS lead_pct_won_90d,
    ROUND(1000.0 * won_90d_2018 / leads_2018 * p, 1)                 AS selling_sellers_per_1k_leads
FROM rates
ORDER BY channel LIKE 'smaller%', sellers DESC;
