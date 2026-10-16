-- Q5. Sales-team capacity by cohort, 2018 cohorts
-- Business question: did fewer people work the leads in May? If the sales team
-- shrank or wins per rep fell, May's drop is a capacity problem, not a process
-- problem.
-- Caveat: reps are only recorded on won deals, so a rep who won nothing from a
-- cohort is invisible. The rep counts are a lower bound, and "wins per rep"
-- is a workload proxy, not a win rate (leads per rep aren't in the data).
-- Every 2018 cohort is observed for 167+ days, so each cohort's wins are complete.
WITH cohort AS (
    SELECT
        cohort_month,
        COUNT(*)                                             AS leads,
        COUNT(*) FILTER (WHERE won)                          AS wins,
        COUNT(*) FILTER (WHERE won_90d)                      AS wins_90d,
        COUNT(DISTINCT sdr_id) FILTER (WHERE won)            AS sdrs,
        COUNT(DISTINCT sr_id)  FILTER (WHERE won)            AS srs,
        MEDIAN(days_to_close)  FILTER (WHERE won)            AS median_days_to_close
    FROM leads
    WHERE in_window
    GROUP BY cohort_month
)
SELECT
    STRFTIME(cohort_month, '%Y-%m')                          AS cohort,
    leads,
    wins,
    wins_90d,
    sdrs                                                     AS sdrs_with_a_win,
    srs                                                      AS srs_with_a_win,
    ROUND(wins::DOUBLE / srs, 1)                             AS wins_per_sr,
    ROUND(wins_90d::DOUBLE / srs, 1)                         AS wins_90d_per_sr,
    median_days_to_close
FROM cohort
ORDER BY cohort_month;
