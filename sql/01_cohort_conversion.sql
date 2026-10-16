-- Q1. Lead-to-seller conversion by month of first contact
-- Business question: of the marketing-qualified leads (MQLs) we generate each
-- month, how many sign as sellers, and is that rate holding up as volume grows?
-- "Converted" = deal won within 90 days of first contact (every 2018 cohort is
-- observed for 167+ days, so the 90-day window is complete for all of them).
-- 2017 cohorts are shown but flagged: deal records start on 2017-12-05, so any
-- 2017 lead that signed before then is missing and their rates are too low.
SELECT
    STRFTIME(cohort_month, '%Y-%m')                              AS cohort,
    COUNT(*)                                                     AS mqls,
    COUNT(*) FILTER (won_90d)                                    AS won_90d,
    ROUND(100.0 * COUNT(*) FILTER (won_90d) / COUNT(*), 1)       AS pct_won_90d,
    COUNT(*) FILTER (won)                                        AS won_any_time,
    ROUND(100.0 * COUNT(*) FILTER (won) / COUNT(*), 1)           AS pct_won_any_time,
    NOT BOOL_AND(in_window)                                      AS deal_tracking_incomplete
FROM leads
GROUP BY cohort_month
ORDER BY cohort_month;
