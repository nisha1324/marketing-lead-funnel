-- Q10. Which kind of seller went missing in May? Wins by lead type, 2018 cohorts
-- Business question: May signed fewer sellers per lead. Was the shortfall
-- spread evenly, or concentrated in one kind of business (e.g. established
-- online sellers vs offline shops)? That tells sales which pitch stopped working.
-- Caveat: lead_type is recorded by the sales rep only when a deal is won, so
-- a lost lead has no type and a conversion rate per type can't be computed.
-- Instead each type's wins are scaled to the cohort's total leads:
--   wins per 1,000 leads = 90-day wins of that type / all leads in the period * 1000
-- These add up across types to the overall rate, so the change per type shows
-- how much of May's fall came from each kind of seller.
WITH periods AS (
    SELECT
        COALESCE(lead_type, '(missing)')                     AS lead_type,
        CASE WHEN cohort_month = DATE '2018-05-01' THEN 'may' ELSE 'base' END AS period,
        won_90d,
        days_to_close
    FROM leads
    WHERE in_window
),
totals AS (
    SELECT
        COUNT(*) FILTER (period = 'base')                    AS base_mqls,
        COUNT(*) FILTER (period = 'may')                     AS may_mqls
    FROM periods
),
by_type AS (
    SELECT
        lead_type,
        COUNT(*) FILTER (won_90d AND period = 'base')        AS base_wins,
        COUNT(*) FILTER (won_90d AND period = 'may')         AS may_wins,
        COUNT(*) FILTER (won_90d)                            AS wins,
        MEDIAN(days_to_close) FILTER (won_90d)               AS median_days_to_close
    FROM periods
    WHERE won_90d
    GROUP BY lead_type
),
scaled AS (
    SELECT
        b.*,
        1000.0 * b.base_wins / t.base_mqls                   AS base_per_1k,
        1000.0 * b.may_wins  / t.may_mqls                    AS may_per_1k
    FROM by_type b, totals t
),
report AS (
SELECT
    lead_type,
    wins,
    ROUND(100.0 * wins / SUM(wins) OVER (), 1)               AS pct_of_wins,
    base_wins,
    may_wins,
    ROUND(base_per_1k, 1)                                    AS base_wins_per_1k_leads,
    ROUND(may_per_1k, 1)                                     AS may_wins_per_1k_leads,
    ROUND(may_per_1k - base_per_1k, 1)                       AS change_per_1k,
    ROUND(100 * (may_per_1k - base_per_1k)
              / SUM(may_per_1k - base_per_1k) OVER (), 1)    AS pct_of_drop,
    median_days_to_close
FROM scaled
UNION ALL
SELECT
    'TOTAL',
    SUM(wins)::BIGINT, 100,
    SUM(base_wins)::BIGINT, SUM(may_wins)::BIGINT,
    ROUND(SUM(base_per_1k), 1), ROUND(SUM(may_per_1k), 1),
    ROUND(SUM(may_per_1k - base_per_1k), 1), 100,
    NULL
FROM scaled
)
SELECT * FROM report
ORDER BY lead_type = 'TOTAL', wins DESC, lead_type;
