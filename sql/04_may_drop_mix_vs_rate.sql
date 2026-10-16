-- Q4. Why did May 2018 convert worse? Channel mix vs channel performance
-- Business question: the 90-day conversion rate fell in May 2018. Is that
-- because more leads came from weak channels (mix), or because leads from the
-- same channels converted worse (rate)? The answer decides the fix: marketing
-- budget allocation vs sales follow-up.
-- Method: shift-share decomposition of the change in overall rate, May vs the
-- Jan-Apr 2018 baseline. For each channel:
--   mix effect  = (May share - base share) * (base rate - base overall rate)
--   rate effect = May share * (May rate - base rate)
-- Measuring mix against the overall rate means a weak channel that gains
-- share shows a negative mix effect. Shares sum to 1 in both periods, so the
-- effects still add up exactly to the total change.
WITH periods AS (
    SELECT
        origin,
        CASE WHEN cohort_month = DATE '2018-05-01' THEN 'may' ELSE 'base' END AS period,
        won_90d
    FROM leads
    WHERE in_window
),
agg AS (
    SELECT
        origin,
        COUNT(*) FILTER (period = 'base')                       AS base_mqls,
        COUNT(*) FILTER (period = 'base' AND won_90d)           AS base_wins,
        COUNT(*) FILTER (period = 'may')                        AS may_mqls,
        COUNT(*) FILTER (period = 'may' AND won_90d)            AS may_wins
    FROM periods
    GROUP BY origin
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
    origin,
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
ORDER BY origin = 'TOTAL', base_mqls DESC;
