-- Q3. How long do leads take to sign?
-- Business question: how quickly do won leads close, and when does a lead that
-- hasn't signed become unlikely to sign at all (so sales can stop chasing it)?
-- Population: 2018-cohort leads that signed within the follow-up every cohort
-- gets (last first contact 2018-05-31 to last recorded win 2018-11-14 = 167
-- days), so early and late cohorts are measured on the same footing.
WITH params AS (
    SELECT DATE_DIFF('day',
                     (SELECT MAX(first_contact_date) FROM leads),
                     (SELECT MAX(won_date)::DATE FROM closed_deals)) AS follow_up_days
),
wins AS (
    SELECT GREATEST(days_to_close, 0) AS days      -- 1 deal is dated 2 days early
    FROM leads, params
    WHERE in_window AND won AND days_to_close <= follow_up_days
),
buckets AS (
    SELECT * FROM (VALUES
        (1, '0-7 days',     0,   7),
        (2, '8-14 days',    8,  14),
        (3, '15-30 days',  15,  30),
        (4, '31-60 days',  31,  60),
        (5, '61-90 days',  61,  90),
        (6, '91-167 days', 91, 167)
    ) AS b(step, bucket, lo, hi)
)
SELECT
    b.step,
    b.bucket,
    COUNT(w.days)                                                   AS wins,
    ROUND(100.0 * COUNT(w.days) / SUM(COUNT(w.days)) OVER (), 1)    AS pct_of_wins,
    ROUND(100.0 * SUM(COUNT(w.days)) OVER (ORDER BY b.step)
          / SUM(COUNT(w.days)) OVER (), 1)                          AS cumulative_pct,
    (SELECT follow_up_days FROM params)                             AS follow_up_days
FROM buckets b
LEFT JOIN wins w ON w.days BETWEEN b.lo AND b.hi
GROUP BY b.step, b.bucket
ORDER BY b.step;
