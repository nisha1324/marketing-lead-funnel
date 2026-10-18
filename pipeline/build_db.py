"""Load the raw funnel CSVs into a local DuckDB file and run data-quality checks.

Usage:  python -m pipeline.build_db  [--raw data/raw] [--db data/funnel.duckdb]

Tables: `mqls` (one row per marketing-qualified lead) and `closed_deals` (one
row per lead that signed as a seller). The view `leads` joins them and adds the
fields every query needs: cohort month, days to close and a 90-day win flag.

Part 3 adds `orders` and `order_items` from Olist's public e-commerce data
(only the columns it needs) and the view `signed_sellers`: one row per won
deal with what that seller sold in its first 90 days after signing.

Analysis window: the closed-deals table has no wins before 2017-12-05, so
leads from 2017 can't be scored fairly (a 2017 lead that signed within a few
weeks would be missing). `in_window` marks leads first contacted from
2018-01-01 to 2018-05-31; the data runs to 2018-11-14, so every one of them
has at least 167 days of follow-up and the 90-day window is complete.

Selling window: the order data has 176-372 orders a day in the four weeks to
2018-08-21; from 2018-08-22 it falls almost every day (187, 144, 99 ... 14
orders on 2018-08-29, then 1 a day or none), so the snapshot was taken while
recent orders were still coming in. Orders from OBS_END on are ignored, and a
seller counts as `observed_90d` only if all of its first 90 days fall before
OBS_END (signed by 2018-05-23 in this data). Cancelled and unavailable orders
don't count as sales.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "mqls": "olist_marketing_qualified_leads_dataset.csv",
    "closed_deals": "olist_closed_deals_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
}
WINDOW_START = "2018-01-01"
WIN_DAYS = 90
OBS_END = "2018-08-22"   # first day the order data is incomplete (see above)
SELL_DAYS = 90

# (name, SQL returning a single number, expected value; None = report only)
CHECKS = [
    ("duplicate mql_id in mqls",
     "SELECT COUNT(*) - COUNT(DISTINCT mql_id) FROM mqls", 0),
    ("duplicate mql_id in closed_deals",
     "SELECT COUNT(*) - COUNT(DISTINCT mql_id) FROM closed_deals", 0),
    ("closed deals with no matching lead",
     "SELECT COUNT(*) FROM closed_deals d ANTI JOIN mqls m USING (mql_id)", 0),
    ("duplicate seller_id in closed_deals",
     "SELECT COUNT(*) - COUNT(DISTINCT seller_id) FROM closed_deals", 0),
    ("deals won before the first contact date",
     "SELECT COUNT(*) FROM leads WHERE days_to_close < 0", None),
    ("leads with no origin (channel)",
     "SELECT COUNT(*) FROM mqls WHERE origin IS NULL", None),
    ("deals with a declared monthly revenue above 0",
     "SELECT COUNT(*) FROM closed_deals WHERE declared_monthly_revenue > 0", None),
    ("wins before 2017-12-01 (deal tracking start)",
     "SELECT COUNT(*) FROM closed_deals WHERE won_date < TIMESTAMP '2017-12-01'", 0),
    ("duplicate order lines in order_items",
     "SELECT COUNT(*) - COUNT(DISTINCT (order_id, order_item_id)) FROM order_items", 0),
    ("order lines with no matching order",
     "SELECT COUNT(*) FROM order_items i ANTI JOIN orders o USING (order_id)", 0),
    ("signed sellers with an order before they signed",
     "SELECT COUNT(*) FROM closed_deals d JOIN ("
     "SELECT i.seller_id, MIN(o.order_purchase_timestamp) AS first_order "
     "FROM order_items i JOIN orders o USING (order_id) GROUP BY 1) f USING (seller_id) "
     "WHERE f.first_order < d.won_date", 0),
    ("signed sellers with any order in the e-commerce data",
     "SELECT COUNT(DISTINCT seller_id) FROM closed_deals SEMI JOIN order_items USING (seller_id)", None),
    (f"orders on or after {OBS_END} (ignored: data incomplete)",
     f"SELECT COUNT(*) FROM orders WHERE order_purchase_timestamp >= TIMESTAMP '{OBS_END}'", None),
]


def build(raw: Path, db: Path) -> duckdb.DuckDBPyConnection:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db))
    con.execute(
        "CREATE OR REPLACE TABLE mqls AS SELECT * FROM read_csv(?, header = true, "
        "columns = {'mql_id': 'VARCHAR', 'first_contact_date': 'DATE', "
        "'landing_page_id': 'VARCHAR', 'origin': 'VARCHAR'})",
        [str(raw / FILES["mqls"])],
    )
    con.execute(
        "CREATE OR REPLACE TABLE closed_deals AS "
        "SELECT * REPLACE (CAST(won_date AS TIMESTAMP) AS won_date) "
        "FROM read_csv_auto(?, header = true, all_varchar = true)",
        [str(raw / FILES["closed_deals"])],
    )
    con.execute("""
        ALTER TABLE closed_deals ALTER declared_monthly_revenue TYPE DOUBLE;
        ALTER TABLE closed_deals ALTER declared_product_catalog_size TYPE DOUBLE;
    """)
    con.execute(f"""
        CREATE OR REPLACE VIEW leads AS
        SELECT
            m.mql_id,
            m.first_contact_date,
            DATE_TRUNC('month', m.first_contact_date)::DATE           AS cohort_month,
            m.landing_page_id,
            COALESCE(m.origin, '(missing)')                           AS origin,
            d.seller_id,
            d.sdr_id,
            d.sr_id,
            d.won_date,
            d.business_segment,
            d.lead_type,
            d.business_type,
            d.mql_id IS NOT NULL                                      AS won,
            DATE_DIFF('day', m.first_contact_date, d.won_date::DATE)  AS days_to_close,
            COALESCE(DATE_DIFF('day', m.first_contact_date, d.won_date::DATE)
                     <= {WIN_DAYS}, false)                            AS won_{WIN_DAYS}d,
            m.first_contact_date >= DATE '{WINDOW_START}'             AS in_window
        FROM mqls m
        LEFT JOIN closed_deals d USING (mql_id)
    """)
    con.execute(
        "CREATE OR REPLACE TABLE orders AS SELECT order_id, order_status, "
        "order_purchase_timestamp FROM read_csv(?, header = true, columns = {"
        "'order_id': 'VARCHAR', 'customer_id': 'VARCHAR', 'order_status': 'VARCHAR', "
        "'order_purchase_timestamp': 'TIMESTAMP', 'order_approved_at': 'VARCHAR', "
        "'order_delivered_carrier_date': 'VARCHAR', 'order_delivered_customer_date': 'VARCHAR', "
        "'order_estimated_delivery_date': 'VARCHAR'})",
        [str(raw / FILES["orders"])],
    )
    con.execute(
        "CREATE OR REPLACE TABLE order_items AS SELECT order_id, order_item_id, seller_id, "
        "price FROM read_csv(?, header = true, columns = {"
        "'order_id': 'VARCHAR', 'order_item_id': 'INTEGER', 'product_id': 'VARCHAR', "
        "'seller_id': 'VARCHAR', 'shipping_limit_date': 'VARCHAR', 'price': 'DOUBLE', "
        "'freight_value': 'VARCHAR'})",
        [str(raw / FILES["order_items"])],
    )
    # sold_<n>d flags use exact timestamps: a sale counts for day n only if it
    # was placed less than n x 24 hours after the deal was won.
    con.execute(f"""
        CREATE OR REPLACE VIEW signed_sellers AS
        WITH sales AS (
            SELECT i.seller_id, i.order_id, i.price, o.order_purchase_timestamp AS purchased_at
            FROM order_items i
            JOIN orders o USING (order_id)
            WHERE o.order_status NOT IN ('canceled', 'unavailable')
              AND o.order_purchase_timestamp < TIMESTAMP '{OBS_END}'
        ),
        per_seller AS (
            SELECT
                d.seller_id,
                MIN(s.purchased_at)                                        AS first_sale_at,
                COUNT(DISTINCT s.order_id) FILTER (
                    s.purchased_at < d.won_date + INTERVAL {SELL_DAYS} DAY)  AS orders_{SELL_DAYS}d,
                SUM(s.price) FILTER (
                    s.purchased_at < d.won_date + INTERVAL {SELL_DAYS} DAY)  AS gmv_{SELL_DAYS}d
            FROM closed_deals d
            JOIN sales s USING (seller_id)
            GROUP BY d.seller_id
        )
        SELECT
            l.mql_id,
            l.seller_id,
            l.origin,
            l.landing_page_id,
            l.lead_type,
            l.business_segment,
            l.business_type,
            l.cohort_month,
            l.in_window,
            l.days_to_close,
            l.won_date,
            DATE_TRUNC('month', l.won_date)::DATE                          AS signed_month,
            l.won_date + INTERVAL {SELL_DAYS} DAY <= TIMESTAMP '{OBS_END}'  AS observed_{SELL_DAYS}d,
            p.first_sale_at,
            COALESCE(p.orders_{SELL_DAYS}d, 0)                             AS orders_{SELL_DAYS}d,
            COALESCE(p.gmv_{SELL_DAYS}d, 0)                                AS gmv_{SELL_DAYS}d,
            COALESCE(p.orders_{SELL_DAYS}d, 0) > 0                         AS sold_{SELL_DAYS}d
        FROM leads l
        LEFT JOIN per_seller p USING (seller_id)
        WHERE l.won
    """)
    return con


def run_checks(con: duckdb.DuckDBPyConnection) -> list[tuple[str, int, str]]:
    results = []
    for name, sql, expected in CHECKS:
        value = con.execute(sql).fetchone()[0]
        if expected is None:
            status = "info"
        else:
            status = "ok" if value == expected else "FAIL"
        results.append((name, value, status))
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "funnel.duckdb")
    args = parser.parse_args()

    con = build(args.raw, args.db)
    print("rows loaded:")
    for table, where in [("mqls", ""), ("closed_deals", ""), ("leads", "WHERE in_window"),
                         ("orders", ""), ("order_items", ""),
                         ("signed_sellers", f"WHERE observed_{SELL_DAYS}d")]:
        n = con.execute(f"SELECT COUNT(*) FROM {table} {where}").fetchone()[0]
        label = table + (f" ({where.split()[-1]})" if where else "")
        print(f"  {label:<30} {n:>7,}")
    first, last = con.execute("SELECT MIN(won_date), MAX(won_date) FROM closed_deals").fetchone()
    print(f"  wins recorded {first:%Y-%m-%d} .. {last:%Y-%m-%d}")
    print("data-quality checks:")
    results = run_checks(con)
    for name, value, status in results:
        print(f"  [{status:>4}] {name}: {value:,}")
    con.close()
    if any(status == "FAIL" for _, _, status in results):
        raise SystemExit("data-quality check failed")


if __name__ == "__main__":
    main()
