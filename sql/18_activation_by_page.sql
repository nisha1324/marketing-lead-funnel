-- Q18. Do the best-converting landing pages also bring sellers who sell?
-- Business question: Part 2b found three pages that sign about 20% of their
-- leads. If their sellers then sell less, the A/B test in recommendation 6
-- would trade signatures for inactive sellers. Does the page ranking hold
-- after the deal?
-- Same sellers and definitions as Q12. Pages with fewer than 30 such sellers
-- are pooled; page = first 8 characters of the anonymised landing_page_id.
-- selling_sellers_per_1k_leads chains the page's 90-day lead-to-deal rate
-- (2018 cohorts, Q7) with its activation rate, as in Q14, so it is an
-- estimate, not a direct count.
WITH s AS (
    SELECT * FROM signed_sellers WHERE observed_90d
),
page_group AS (
    SELECT landing_page_id,
           CASE WHEN COUNT(*) >= 30 THEN LEFT(landing_page_id, 8)
                ELSE 'smaller pages (pooled)' END                    AS page,
           MODE(origin)                                              AS main_origin
    FROM s
    GROUP BY landing_page_id
),
sellers AS (
    SELECT
        g.page,
        COUNT(DISTINCT s.landing_page_id)                            AS pages,
        ANY_VALUE(g.main_origin) FILTER (g.page NOT LIKE 'smaller%') AS main_origin,
        COUNT(*)                                                     AS sellers,
        COUNT(*) FILTER (s.sold_90d)                                 AS sold_90d,
        SUM(s.gmv_90d)                                               AS gmv_90d,
        MEDIAN(s.gmv_90d) FILTER (s.sold_90d)                        AS median_gmv_per_active_seller,
        MAX(s.gmv_90d)                                               AS top_seller_gmv
    FROM s JOIN page_group g USING (landing_page_id)
    GROUP BY g.page
),
leads_by_page AS (
    SELECT
        COALESCE(g.page, 'smaller pages (pooled)')                   AS page,
        COUNT(*)                                                     AS leads_2018,
        COUNT(*) FILTER (l.won_90d)                                  AS won_90d_2018
    FROM leads l LEFT JOIN page_group g USING (landing_page_id)
    WHERE l.in_window
    GROUP BY 1
),
rates AS (
    SELECT *, sold_90d::DOUBLE / sellers AS p, 1.96 AS z
    FROM sellers JOIN leads_by_page USING (page)
)
SELECT
    page,
    pages,
    main_origin,
    sellers,
    sold_90d,
    ROUND(100 * p, 1)                                                AS pct_sold_90d,
    ROUND(100 * (p + z*z/(2*sellers) - z * SQRT(p*(1-p)/sellers + z*z/(4*sellers*sellers)))
          / (1 + z*z/sellers), 1)                                    AS ci95_low,
    ROUND(100 * (p + z*z/(2*sellers) + z * SQRT(p*(1-p)/sellers + z*z/(4*sellers*sellers)))
          / (1 + z*z/sellers), 1)                                    AS ci95_high,
    ROUND(100.0 * gmv_90d / SUM(gmv_90d) OVER (), 1)                 AS pct_of_gmv,
    ROUND(median_gmv_per_active_seller, 2)                           AS median_gmv_per_active_seller,
    -- one large seller can dominate a group's sales value; show how much
    ROUND(100.0 * top_seller_gmv / NULLIF(gmv_90d, 0), 1)            AS top_seller_pct_of_gmv,
    leads_2018,
    ROUND(100.0 * won_90d_2018 / leads_2018, 1)                      AS lead_pct_won_90d,
    ROUND(1000.0 * won_90d_2018 / leads_2018 * p, 1)                 AS selling_sellers_per_1k_leads
FROM rates
ORDER BY page LIKE 'smaller%', sellers DESC, page;
