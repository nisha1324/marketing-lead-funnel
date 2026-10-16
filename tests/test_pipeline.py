"""Offline tests: build a tiny DuckDB from fixture CSVs and run the SQL."""
from pathlib import Path

import pandas as pd
import pytest

from pipeline.build_db import FILES, build, run_checks

SQL = Path(__file__).resolve().parents[1] / "sql"
DEAL_COLS = ["mql_id", "seller_id", "sdr_id", "sr_id", "won_date", "business_segment",
             "lead_type", "lead_behaviour_profile", "has_company", "has_gtin",
             "average_stock", "business_type", "declared_product_catalog_size",
             "declared_monthly_revenue"]


def deal(mql_id: str, won_date: str) -> list:
    return [mql_id, f"s_{mql_id}", "sdr1", "sr1", won_date, "pet", "online_medium",
            None, None, None, None, "reseller", None, 0.0]


@pytest.fixture
def con(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    pd.DataFrame(
        [
            ["l1", "2017-08-10", "lp1", "social"],          # 2017: outside the window
            ["l2", "2018-01-05", "lp1", "organic_search"],  # won in 10 days
            ["l3", "2018-01-20", "lp2", "organic_search"],  # won after 91 days
            ["l4", "2018-02-01", "lp2", "social"],          # never won
            ["l5", "2018-05-02", "lp1", "organic_search"],  # won 2 days *before* contact
            ["l6", "2018-05-10", "lp3", None],              # no origin, won day 0
            ["l7", "2018-05-31", "lp3", "social"],          # never won
        ],
        columns=["mql_id", "first_contact_date", "landing_page_id", "origin"],
    ).to_csv(raw / FILES["mqls"], index=False)
    pd.DataFrame(
        [
            deal("l1", "2018-01-15 10:00:00"),
            deal("l2", "2018-01-15 10:00:00"),
            deal("l3", "2018-04-21 09:00:00"),
            deal("l5", "2018-04-30 12:00:00"),
            deal("l6", "2018-05-10 18:00:00"),
        ],
        columns=DEAL_COLS,
    ).to_csv(raw / FILES["closed_deals"], index=False)
    con = build(raw, tmp_path / "test.duckdb")
    yield con
    con.close()


def run(con, name: str) -> pd.DataFrame:
    return con.execute((SQL / f"{name}.sql").read_text()).df()


def test_leads_view_flags(con):
    df = con.execute("SELECT * FROM leads ORDER BY mql_id").df().set_index("mql_id")
    assert df.loc["l2", "days_to_close"] == 10 and df.loc["l2", "won_90d"]
    assert df.loc["l3", "won"] and not df.loc["l3", "won_90d"]     # 91 days is too late
    assert not df.loc["l4", "won"] and not df.loc["l4", "won_90d"]
    assert df.loc["l5", "days_to_close"] == -2 and df.loc["l5", "won_90d"]
    assert df.loc["l6", "origin"] == "(missing)"
    assert not df.loc["l1", "in_window"] and df["in_window"].sum() == 6


def test_checks_pass_and_report_early_deal(con):
    results = {name: (value, status) for name, value, status in run_checks(con)}
    assert all(status != "FAIL" for _, status in results.values())
    assert results["deals won before the first contact date"] == (1, "info")
    assert results["leads with no origin (channel)"] == (1, "info")


def test_orphan_deal_fails_check(con):
    con.execute("INSERT INTO closed_deals (mql_id, seller_id) VALUES ('ghost', 's_ghost')")
    results = {name: status for name, _, status in run_checks(con)}
    assert results["closed deals with no matching lead"] == "FAIL"


def test_cohort_conversion(con):
    df = run(con, "01_cohort_conversion").set_index("cohort")
    assert df.loc["2017-08", "deal_tracking_incomplete"]
    jan = df.loc["2018-01"]
    assert (jan["mqls"], jan["won_90d"], jan["won_any_time"]) == (2, 1, 2)
    assert jan["pct_won_90d"] == 50.0 and not jan["deal_tracking_incomplete"]
    may = df.loc["2018-05"]
    assert (may["mqls"], may["won_90d"]) == (3, 2)


def test_channel_conversion_and_interval(con):
    df = run(con, "02_channel_conversion").set_index("origin")
    assert df["mqls"].sum() == 6 and df["won_90d"].sum() == 3
    org = df.loc["organic_search"]
    assert (org["mqls"], org["won_90d"]) == (3, 2)
    assert org["ci95_low"] < org["pct_won_90d"] < org["ci95_high"]
    # a channel with no wins still gets an interval starting at 0
    social = df.loc["social"]
    assert social["won_90d"] == 0 and social["ci95_low"] == 0 and social["ci95_high"] > 0
    assert df["pct_of_mqls"].sum() == pytest.approx(100, abs=0.2)


def test_time_to_close_buckets(con):
    # follow-up = last first contact (2018-05-31) -> last recorded win; add a
    # slow deal so the last win is 2018-07-01, giving every cohort 31 days
    con.execute("INSERT INTO mqls VALUES ('l8', DATE '2018-01-02', 'lp1', 'email')")
    con.execute("INSERT INTO closed_deals (mql_id, seller_id, won_date) "
                "VALUES ('l8', 's_l8', TIMESTAMP '2018-07-01 10:00:00')")
    df = run(con, "03_time_to_close").set_index("bucket")
    assert df["follow_up_days"].iloc[0] == 31
    # l2 (10 d), l5 (-2 d, counted as 0), l6 (0 d); l3 (91 d) and l8 are beyond it
    assert df.loc["0-7 days", "wins"] == 2 and df.loc["8-14 days", "wins"] == 1
    assert df["wins"].sum() == 3 and df["cumulative_pct"].iloc[-1] == 100.0


def test_may_decomposition_adds_up(con):
    df = run(con, "04_may_drop_mix_vs_rate").set_index("origin")
    total = df.loc["TOTAL"]
    change = 100 * (2 / 3 - 1 / 3)      # Jan-Apr: 1 of 3 won in 90 days; May: 2 of 3
    assert total["mix_effect_pts"] + total["rate_effect_pts"] == pytest.approx(change, abs=0.01)
    assert (total["base_mqls"], total["may_mqls"]) == (3, 3)
    # per-channel effects sum to the totals
    body = df.drop(index="TOTAL")
    assert body["mix_effect_pts"].sum() == pytest.approx(total["mix_effect_pts"], abs=0.02)
    assert body["rate_effect_pts"].sum() == pytest.approx(total["rate_effect_pts"], abs=0.02)


def test_weak_channel_gaining_share_has_negative_mix_effect(con):
    # social converts 0% in Jan-Apr (overall 33%); give it more of May's leads
    con.execute("INSERT INTO mqls VALUES ('l9', DATE '2018-05-20', 'lp1', 'social')")
    df = run(con, "04_may_drop_mix_vs_rate").set_index("origin")
    assert df.loc["social", "may_pct_of_mqls"] > df.loc["social", "base_pct_of_mqls"]
    assert df.loc["social", "mix_effect_pts"] < 0
