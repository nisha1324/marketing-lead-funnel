-- Q11. What kind of sellers does the funnel sign? Business segment of 2018 wins
-- Business question: which product categories do the signed sellers bring to
-- the marketplace, and do some close faster than others? This is the profile
-- Part 3 checks against what the sellers actually sold.
-- Like lead_type, business_segment and business_type exist only for won deals,
-- so this describes wins, not conversion rates. All wins from the Jan-May 2018
-- cohorts are counted (each is observed for 167+ days). The top 10 segments
-- are listed; the rest are pooled.
WITH wins AS (
    SELECT l.business_segment, l.days_to_close, d.business_type
    FROM leads l
    JOIN closed_deals d USING (mql_id)
    WHERE l.in_window
),
by_segment AS (
    SELECT
        COALESCE(business_segment, '(missing)')              AS segment,
        COUNT(*)                                             AS wins,
        COUNT(*) FILTER (business_type = 'manufacturer')     AS manufacturers,
        COUNT(*) FILTER (days_to_close <= 14)                AS closed_in_14d
    FROM wins
    GROUP BY 1
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (ORDER BY wins DESC, segment) AS rank
    FROM by_segment
),
grouped AS (
    SELECT
        CASE WHEN rank <= 10 THEN segment
             ELSE 'other (' || (SELECT COUNT(*) - 10 FROM ranked) || ' segments)' END AS segment,
        MIN(rank)                                            AS rank,
        SUM(wins)                                            AS wins,
        SUM(manufacturers)                                   AS manufacturers,
        SUM(closed_in_14d)                                   AS closed_in_14d
    FROM ranked
    GROUP BY 1
)
SELECT
    segment,
    wins::BIGINT                                             AS wins,
    ROUND(100.0 * wins / SUM(wins) OVER (), 1)               AS pct_of_wins,
    ROUND(100.0 * SUM(wins) OVER (ORDER BY rank) / SUM(wins) OVER (), 1) AS cum_pct_of_wins,
    ROUND(100.0 * manufacturers / wins, 1)                   AS pct_manufacturers,
    ROUND(100.0 * closed_in_14d / wins, 1)                   AS pct_closed_in_14d
FROM grouped
ORDER BY rank;
