-- Q7. Conversion by landing page, 2018 cohorts
-- Business question: which sign-up pages bring leads that sign, and does each
-- page serve one channel or many? If pages are tied to channels, a "bad page"
-- may really be a bad channel (and the reverse), so the main channel is shown.
-- Pages with 50+ leads are listed; the long tail is grouped into one row.
-- page = first 8 characters of the anonymised landing_page_id.
-- The 95% interval is a Wilson score interval (as in Q2).
WITH by_page AS (
    SELECT
        landing_page_id,
        COUNT(*)                                             AS mqls,
        COUNT(*) FILTER (won_90d)                            AS won_90d,
        MODE(origin)                                         AS main_origin,
        MIN(cohort_month)                                    AS first_cohort,
        MAX(cohort_month)                                    AS last_cohort
    FROM leads
    WHERE in_window
    GROUP BY landing_page_id
),
main_share AS (
    SELECT
        p.landing_page_id,
        COUNT(*) FILTER (l.origin = p.main_origin)::DOUBLE / p.mqls AS main_origin_share
    FROM by_page p
    JOIN leads l ON l.landing_page_id = p.landing_page_id AND l.in_window
    GROUP BY p.landing_page_id, p.mqls
),
labelled AS (
    SELECT
        p.*,
        s.main_origin_share,
        p.mqls < 50                                          AS is_tail,
        CASE WHEN p.mqls >= 50 THEN LEFT(p.landing_page_id, 8)
             ELSE 'other pages' END                          AS page
    FROM by_page p
    JOIN main_share s USING (landing_page_id)
),
grouped AS (
    -- the main channel is only meaningful for a single page, not the tail
    SELECT
        page,
        COUNT(*)                                             AS pages,
        SUM(mqls)::BIGINT                                    AS mqls,
        SUM(won_90d)::BIGINT                                 AS won_90d,
        ANY_VALUE(main_origin) FILTER (NOT is_tail)          AS main_origin,
        ANY_VALUE(main_origin_share) FILTER (NOT is_tail)    AS main_origin_share,
        MIN(first_cohort)                                    AS first_cohort,
        MAX(last_cohort)                                     AS last_cohort
    FROM labelled
    GROUP BY page
),
rates AS (
    SELECT *, won_90d::DOUBLE / mqls AS p, 1.96 AS z
    FROM grouped
)
SELECT
    page,
    pages,
    mqls,
    ROUND(100.0 * mqls / SUM(mqls) OVER (), 1)                 AS pct_of_mqls,
    won_90d,
    ROUND(100.0 * won_90d / SUM(won_90d) OVER (), 1)           AS pct_of_wins,
    ROUND(100 * p, 1)                                          AS pct_won_90d,
    ROUND(100 * (p + z*z/(2*mqls) - z * SQRT(p*(1-p)/mqls + z*z/(4*mqls*mqls)))
          / (1 + z*z/mqls), 1)                                 AS ci95_low,
    ROUND(100 * (p + z*z/(2*mqls) + z * SQRT(p*(1-p)/mqls + z*z/(4*mqls*mqls)))
          / (1 + z*z/mqls), 1)                                 AS ci95_high,
    main_origin,
    ROUND(100 * main_origin_share, 1)                          AS main_origin_pct,
    STRFTIME(first_cohort, '%Y-%m')                            AS first_cohort,
    STRFTIME(last_cohort, '%Y-%m')                             AS last_cohort
FROM rates
ORDER BY page = 'other pages', mqls DESC, page;
