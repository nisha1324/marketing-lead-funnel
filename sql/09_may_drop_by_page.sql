-- Q9. May's drop split by landing page instead of channel
-- Business question: Q4 found that May's fall was within channels, not the
-- channel mix. Pages are finer than channels (a channel can switch to a new
-- page, as social did in March), so does a shift in *page* mix explain more?
-- Same shift-share method as Q4, with pages as the groups: pages with 50+
-- leads in Jan-May 2018 are kept, the rest pooled as 'other pages'.
-- If the mix effect stays small here too, the drop happened on the same pages.
WITH periods AS (
    SELECT
        CASE WHEN COUNT(*) OVER (PARTITION BY landing_page_id) >= 50
             THEN LEFT(landing_page_id, 8) ELSE 'other pages' END AS page,
        CASE WHEN cohort_month = DATE '2018-05-01' THEN 'may' ELSE 'base' END AS period,
        won_90d
    FROM leads
    WHERE in_window
),
agg AS (
    SELECT
        page,
        COUNT(*) FILTER (period = 'base')                       AS base_mqls,
        COUNT(*) FILTER (period = 'base' AND won_90d)           AS base_wins,
        COUNT(*) FILTER (period = 'may')                        AS may_mqls,
        COUNT(*) FILTER (period = 'may' AND won_90d)            AS may_wins
    FROM periods
    GROUP BY page
),
shares AS (
    SELECT *,
        base_mqls::DOUBLE / SUM(base_mqls) OVER ()              AS base_share,
        may_mqls::DOUBLE  / SUM(may_mqls)  OVER ()              AS may_share,
        base_wins::DOUBLE / NULLIF(base_mqls, 0)                AS base_rate,
        may_wins::DOUBLE  / NULLIF(may_mqls, 0)                 AS may_rate,
        SUM(base_wins) OVER ()::DOUBLE / SUM(base_mqls) OVER () AS base_overall_rate
    FROM agg
),
effects AS (
    SELECT *,
        (may_share - base_share) * (COALESCE(base_rate, 0) - base_overall_rate) AS mix_effect,
        may_share * (COALESCE(may_rate, 0) - COALESCE(base_rate, 0))         AS rate_effect
    FROM shares
),
report AS (
SELECT
    page,
    base_mqls,
    may_mqls,
    ROUND(100 * base_share, 1)                AS base_pct_of_mqls,
    ROUND(100 * may_share, 1)                 AS may_pct_of_mqls,
    ROUND(100 * base_rate, 1)                 AS base_pct_won_90d,
    ROUND(100 * may_rate, 1)                  AS may_pct_won_90d,
    ROUND(100 * mix_effect, 2)                AS mix_effect_pts,
    ROUND(100 * rate_effect, 2)               AS rate_effect_pts
FROM effects
UNION ALL
SELECT
    'TOTAL',
    SUM(base_mqls)::BIGINT, SUM(may_mqls)::BIGINT, 100, 100,
    ROUND(100.0 * SUM(base_wins) / SUM(base_mqls), 1),
    ROUND(100.0 * SUM(may_wins) / SUM(may_mqls), 1),
    ROUND(100 * SUM(mix_effect), 2),
    ROUND(100 * SUM(rate_effect), 2)
FROM effects
)
SELECT * FROM report
ORDER BY page = 'TOTAL', base_mqls DESC;
