"""Load the raw funnel CSVs into a local DuckDB file and run data-quality checks.

Usage:  python -m pipeline.build_db  [--raw data/raw] [--db data/funnel.duckdb]

Tables: `mqls` (one row per marketing-qualified lead) and `closed_deals` (one
row per lead that signed as a seller). The view `leads` joins them and adds the
fields every query needs: cohort month, days to close and a 90-day win flag.

Analysis window: the closed-deals table has no wins before 2017-12-05, so
leads from 2017 can't be scored fairly (a 2017 lead that signed within a few
weeks would be missing). `in_window` marks leads first contacted from
2018-01-01 to 2018-05-31; the data runs to 2018-11-14, so every one of them
has at least 167 days of follow-up and the 90-day window is complete.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "mqls": "olist_marketing_qualified_leads_dataset.csv",
    "closed_deals": "olist_closed_deals_dataset.csv",
}
WINDOW_START = "2018-01-01"
WIN_DAYS = 90

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
            d.mql_id IS NOT NULL                                      AS won,
            DATE_DIFF('day', m.first_contact_date, d.won_date::DATE)  AS days_to_close,
            COALESCE(DATE_DIFF('day', m.first_contact_date, d.won_date::DATE)
                     <= {WIN_DAYS}, false)                            AS won_{WIN_DAYS}d,
            m.first_contact_date >= DATE '{WINDOW_START}'             AS in_window
        FROM mqls m
        LEFT JOIN closed_deals d USING (mql_id)
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
    for table, where in [("mqls", ""), ("closed_deals", ""), ("leads", "WHERE in_window")]:
        n = con.execute(f"SELECT COUNT(*) FROM {table} {where}").fetchone()[0]
        label = table + (" (in window)" if where else "")
        print(f"  {label:<20} {n:>7,}")
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
