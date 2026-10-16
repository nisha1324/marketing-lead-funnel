-- Q2. Conversion by acquisition channel (origin), 2018 cohorts
-- Business question: which channels bring leads that actually sign, and which
-- bring volume that the sales team can't convert?
-- Window: leads first contacted 2018-01-01 .. 2018-05-31 (5,998 leads).
-- The 95% interval is a Wilson score interval, so small channels show how
-- uncertain their rate is instead of looking precise.
WITH by_origin AS (
    SELECT
        origin,
        COUNT(*)                          AS mqls,
        COUNT(*) FILTER (won_90d)         AS won_90d,
        MEDIAN(days_to_close) FILTER (won_90d) AS median_days_to_close
    FROM leads
    WHERE in_window
    GROUP BY origin
),
rates AS (
    SELECT *,
        won_90d::DOUBLE / mqls AS p,
        1.96 AS z
    FROM by_origin
)
SELECT
    origin,
    mqls,
    ROUND(100.0 * mqls / SUM(mqls) OVER (), 1)                 AS pct_of_mqls,
    won_90d,
    ROUND(100.0 * won_90d / SUM(won_90d) OVER (), 1)           AS pct_of_wins,
    ROUND(100 * p, 1)                                          AS pct_won_90d,
    ROUND(100 * (p + z*z/(2*mqls) - z * SQRT(p*(1-p)/mqls + z*z/(4*mqls*mqls)))
          / (1 + z*z/mqls), 1)                                 AS ci95_low,
    ROUND(100 * (p + z*z/(2*mqls) + z * SQRT(p*(1-p)/mqls + z*z/(4*mqls*mqls)))
          / (1 + z*z/mqls), 1)                                 AS ci95_high,
    -- wins per lead relative to the average lead (100 = average)
    ROUND(100 * p / (SUM(won_90d) OVER () / SUM(mqls) OVER ()))  AS conversion_index,
    median_days_to_close
FROM rates
ORDER BY mqls DESC;
