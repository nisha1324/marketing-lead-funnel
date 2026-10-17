-- Q8. Landing pages compared within the same channel, 2018 cohorts
-- Business question: holding the channel fixed, does the page a lead signs up
-- on change how often it converts? Comparing pages inside one channel removes
-- the channel effect that Q7 can't separate. A page can still stand for a
-- campaign or a target audience, so a gap here is a reason to A/B test the
-- page, not proof that the page design causes it.
-- Rows: every (channel, page) pair with 50+ leads, plus the channel's overall
-- rate across all its pages for reference. Wilson 95% intervals as in Q2.
WITH pairs AS (
    SELECT
        origin,
        landing_page_id,
        COUNT(*)                                             AS mqls,
        COUNT(*) FILTER (won_90d)                            AS won_90d
    FROM leads
    WHERE in_window
    GROUP BY origin, landing_page_id
),
channel AS (
    SELECT
        origin,
        SUM(mqls)                                            AS channel_mqls,
        SUM(won_90d)                                         AS channel_won_90d
    FROM pairs
    GROUP BY origin
),
rates AS (
    SELECT
        p.origin,
        LEFT(p.landing_page_id, 8)                           AS page,
        p.mqls,
        p.won_90d,
        p.won_90d::DOUBLE / p.mqls                           AS p,
        1.96                                                 AS z,
        c.channel_mqls,
        c.channel_won_90d::DOUBLE / c.channel_mqls           AS channel_rate
    FROM pairs p
    JOIN channel c USING (origin)
    WHERE p.mqls >= 50
)
SELECT
    origin,
    page,
    mqls,
    ROUND(100.0 * mqls / channel_mqls, 1)                      AS pct_of_channel_mqls,
    won_90d,
    ROUND(100 * p, 1)                                          AS pct_won_90d,
    ROUND(100 * (p + z*z/(2*mqls) - z * SQRT(p*(1-p)/mqls + z*z/(4*mqls*mqls)))
          / (1 + z*z/mqls), 1)                                 AS ci95_low,
    ROUND(100 * (p + z*z/(2*mqls) + z * SQRT(p*(1-p)/mqls + z*z/(4*mqls*mqls)))
          / (1 + z*z/mqls), 1)                                 AS ci95_high,
    ROUND(100 * channel_rate, 1)                               AS channel_pct_won_90d
FROM rates
ORDER BY channel_mqls DESC, origin, mqls DESC, page;
