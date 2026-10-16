-- Q6. How concentrated are wins across sales reps? (2018 cohorts)
-- Business question: how much of the 2018 win volume depends on a handful of
-- people? If a few senior reps close most deals, losing one is a capacity risk.
-- Same caveat as Q5: only reps with at least one win are visible.
WITH rep_wins AS (
    SELECT sr_id, COUNT(*) AS wins
    FROM leads
    WHERE in_window AND won
    GROUP BY sr_id
),
ranked AS (
    SELECT
        ROW_NUMBER() OVER (ORDER BY wins DESC, sr_id)        AS rank,
        wins,
        SUM(wins) OVER (ORDER BY wins DESC, sr_id
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_wins,
        SUM(wins) OVER ()                                    AS total_wins,
        COUNT(*)  OVER ()                                    AS reps
    FROM rep_wins
)
SELECT
    rank                                                     AS sr_rank,
    wins,
    ROUND(100.0 * wins / total_wins, 1)                      AS pct_of_wins,
    ROUND(100.0 * cum_wins / total_wins, 1)                  AS cum_pct_of_wins,
    reps                                                     AS srs_with_a_win
FROM ranked
WHERE rank <= 10
ORDER BY rank;
