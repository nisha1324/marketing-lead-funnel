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
ORDER_COLS = ["order_id", "customer_id", "order_status", "order_purchase_timestamp",
              "order_approved_at", "order_delivered_carrier_date",
              "order_delivered_customer_date", "order_estimated_delivery_date"]
ITEM_COLS = ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date",
             "price", "freight_value"]


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
    # orders: (order_id, seller, purchased at, status, [item prices])
    orders = [
        ("o1", "s_l2", "2018-01-20 10:00:00", "delivered", [100.0]),     # day 5
        ("o2", "s_l2", "2018-03-01 10:00:00", "delivered", [30.0, 20.0]),  # day 45, 2 lines
        ("o3", "s_l2", "2018-05-01 10:00:00", "delivered", [999.0]),     # day 106: too late
        ("o4", "s_l2", "2018-02-01 10:00:00", "canceled", [500.0]),      # not a sale
        ("o5", "s_l5", "2018-07-29 11:00:00", "delivered", [40.0]),      # 1 h inside day 90
        ("o6", "s_l5", "2018-07-29 13:00:00", "delivered", [7.0]),       # 1 h after day 90
        ("o7", "s_l6", "2018-08-25 10:00:00", "delivered", [60.0]),      # after OBS_END
        ("o8", "s_l1", "2018-03-20 10:00:00", "delivered", [10.0]),      # day 64
        ("o9", "s_other", "2018-02-02 10:00:00", "delivered", [5.0]),    # not a funnel seller
        ("o10", "s_l3", "2018-08-01 10:00:00", "delivered", [25.0]),     # day 102
    ]
    pd.DataFrame(
        [[oid, f"c_{oid}", status, ts, None, None, None, None] for oid, _, ts, status, _ in orders],
        columns=ORDER_COLS,
    ).to_csv(raw / FILES["orders"], index=False)
    pd.DataFrame(
        [[oid, n, f"p_{oid}", seller, None, price, 1.0]
         for oid, seller, _, _, prices in orders for n, price in enumerate(prices, start=1)],
        columns=ITEM_COLS,
    ).to_csv(raw / FILES["order_items"], index=False)
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


def test_sales_capacity_by_cohort(con):
    df = run(con, "05_sales_capacity").set_index("cohort")
    jan = df.loc["2018-01"]
    # l2 and l3 won in January's cohort, both with sr1 and sdr1
    assert (jan["leads"], jan["wins"], jan["wins_90d"]) == (2, 2, 1)
    assert (jan["srs_with_a_win"], jan["sdrs_with_a_win"]) == (1, 1)
    assert jan["wins_per_sr"] == 2.0
    assert df["wins"].sum() == 4                     # l2, l3, l5, l6 in the window


def test_rep_concentration_sums_to_wins(con):
    df = run(con, "06_rep_concentration")
    assert df["wins"].sum() == 4                     # all in-window wins belong to sr1
    assert df.loc[0, "pct_of_wins"] == 100.0 and df.loc[0, "cum_pct_of_wins"] == 100.0
    assert df["srs_with_a_win"].iloc[0] == 1


def add_page_leads(con, page: str, origin: str, n: int, wins: int, month: str = "2018-02") -> None:
    """Insert n leads on one landing page; the first `wins` sign 5 days later."""
    for i in range(n):
        mql = f"{page}_{i}"
        con.execute("INSERT INTO mqls VALUES (?, ?::DATE, ?, ?)", [mql, f"{month}-01", page, origin])
        if i < wins:
            con.execute("INSERT INTO closed_deals (mql_id, seller_id, won_date) VALUES (?, ?, ?::TIMESTAMP)",
                        [mql, f"s_{mql}", f"{month}-06 10:00:00"])


def test_landing_pages_keep_big_pages_and_pool_the_tail(con):
    add_page_leads(con, "bigpage_long_id", "paid_search", n=50, wins=10)
    df = run(con, "07_landing_pages").set_index("page")
    big = df.loc["bigpage_"]                         # ids are cut to 8 characters
    assert (big["mqls"], big["won_90d"], big["pct_won_90d"]) == (50, 10, 20.0)
    assert (big["main_origin"], big["main_origin_pct"]) == ("paid_search", 100.0)
    assert big["ci95_low"] < 20.0 < big["ci95_high"]
    tail = df.loc["other pages"]                     # lp1, lp2, lp3 have < 50 leads
    assert (tail["pages"], tail["mqls"], tail["won_90d"]) == (3, 6, 3)
    assert pd.isna(tail["main_origin"])
    assert df.index[-1] == "other pages"
    assert df["pct_of_mqls"].sum() == pytest.approx(100, abs=0.2)


def test_pages_within_channel_compare_to_channel_rate(con):
    add_page_leads(con, "bigpage_long_id", "paid_search", n=50, wins=10)
    con.execute("INSERT INTO mqls VALUES ('l10', DATE '2018-02-03', 'lp1', 'paid_search')")
    df = run(con, "08_pages_within_channel")
    assert len(df) == 1                              # only one (channel, page) pair has 50+
    row = df.iloc[0]
    assert (row["origin"], row["page"], row["mqls"]) == ("paid_search", "bigpage_", 50)
    assert row["pct_of_channel_mqls"] == pytest.approx(100 * 50 / 51, abs=0.05)
    assert row["channel_pct_won_90d"] == pytest.approx(100 * 10 / 51, abs=0.05)


def test_may_drop_by_page_matches_channel_split_total(con):
    add_page_leads(con, "bigpage_long_id", "paid_search", n=50, wins=10, month="2018-05")
    by_page = run(con, "09_may_drop_by_page").set_index("page")
    by_channel = run(con, "04_may_drop_mix_vs_rate").set_index("origin")
    page_total, channel_total = by_page.loc["TOTAL"], by_channel.loc["TOTAL"]
    # same leads, different grouping: the overall change must be identical
    change = channel_total["mix_effect_pts"] + channel_total["rate_effect_pts"]
    assert page_total["mix_effect_pts"] + page_total["rate_effect_pts"] == pytest.approx(change, abs=0.02)
    assert page_total["may_mqls"] == 53
    body = by_page.drop(index="TOTAL")
    assert body["mix_effect_pts"].sum() == pytest.approx(page_total["mix_effect_pts"], abs=0.02)


def test_may_drop_by_lead_type_adds_up(con):
    con.execute("UPDATE closed_deals SET lead_type = 'industry' WHERE mql_id = 'l6'")
    con.execute("INSERT INTO mqls VALUES ('l11', DATE '2018-03-01', 'lp1', 'email')")
    df = run(con, "10_may_drop_by_lead_type").set_index("lead_type")
    # Jan-Apr: 4 leads, 1 win in 90 days (l2); May: 3 leads, 2 wins (l5, l6).
    # Each period is scaled by its own lead count.
    om, ind, total = df.loc["online_medium"], df.loc["industry"], df.loc["TOTAL"]
    assert (om["base_wins"], om["may_wins"]) == (1, 1)
    assert (om["base_wins_per_1k_leads"], om["may_wins_per_1k_leads"]) == (250.0, pytest.approx(333.3, abs=0.1))
    assert (ind["base_wins"], ind["may_wins"]) == (0, 1)
    assert ind["pct_of_drop"] == pytest.approx(80.0, abs=0.1)     # 333.3 of 416.7
    assert total["change_per_1k"] == pytest.approx(1000 * (2 / 3 - 1 / 4), abs=0.1)
    assert df.drop(index="TOTAL")["wins"].sum() == total["wins"] == 3


def test_won_segments_profile(con):
    con.execute("UPDATE closed_deals SET business_segment = 'toys' WHERE mql_id = 'l3'")
    con.execute("UPDATE closed_deals SET business_type = 'manufacturer' WHERE mql_id IN ('l2', 'l3')")
    df = run(con, "11_won_segments").set_index("segment")
    # in-window wins: l2, l5, l6 are pet (l1 is a 2017 lead); l3 is toys
    assert list(df.index) == ["pet", "toys"]
    pet = df.loc["pet"]
    assert (pet["wins"], pet["pct_manufacturers"]) == (3, pytest.approx(33.3, abs=0.1))
    assert pet["pct_closed_in_14d"] == 100.0         # 10, -2 and 0 days
    assert df.loc["toys", "pct_closed_in_14d"] == 0.0  # 91 days
    assert df["cum_pct_of_wins"].iloc[-1] == 100.0


def test_signed_sellers_count_only_valid_sales_inside_90_days(con):
    df = con.execute("SELECT * FROM signed_sellers").df().set_index("mql_id")
    assert len(df) == 5 and df["observed_90d"].all()  # l6 won 2018-05-10: day 90 is 2018-08-08
    l2 = df.loc["l2"]                                 # o1 + o2; o3 too late, o4 cancelled
    assert (l2["orders_90d"], l2["gmv_90d"], l2["sold_90d"]) == (2, 150.0, True)
    l5 = df.loc["l5"]                                 # o5 counts, o6 is an hour too late
    assert (l5["orders_90d"], l5["gmv_90d"]) == (1, 40.0)
    assert not df.loc["l6", "sold_90d"] and pd.isna(df.loc["l6", "first_sale_at"])  # o7 ignored
    assert not df.loc["l3", "sold_90d"] and df.loc["l3", "gmv_90d"] == 0  # first sale day 102


def test_sale_before_signing_fails_check(con):
    results = {name: (value, status) for name, value, status in run_checks(con)}
    assert results["signed sellers with an order before they signed"] == (0, "ok")
    assert results["signed sellers with any order in the e-commerce data"] == (5, "info")
    con.execute("INSERT INTO orders VALUES ('o11', 'delivered', TIMESTAMP '2018-04-01 10:00:00')")
    con.execute("INSERT INTO order_items VALUES ('o11', 1, 's_l3', 9.0)")  # l3 won 2018-04-21
    results = {name: status for name, _, status in run_checks(con)}
    assert results["signed sellers with an order before they signed"] == "FAIL"


def test_seller_activation_by_month_and_total(con):
    df = run(con, "12_seller_activation").set_index("signed_month")
    total = df.loc["TOTAL"]
    assert (total["sellers"], total["sold_30d"], total["sold_60d"], total["sold_90d"]) == (5, 1, 1, 3)
    assert (total["pct_sold_90d"], total["orders_90d"], total["gmv_90d"]) == (60.0, 4, 200.0)
    assert total["median_days_to_first_sale"] == 64.0   # 5, 64 and 89.96 days
    assert total["median_gmv_per_active_seller"] == 40.0
    assert total["top_seller_pct_of_gmv"] == 75.0       # l2's 150 of 200
    jan = df.loc["2018-01"]                             # l1 and l2
    assert (jan["sellers"], jan["sold_90d"], jan["gmv_90d"]) == (2, 2, 160.0)
    assert df.index[-1] == "TOTAL"
    assert df.drop(index="TOTAL")["sellers"].sum() == 5


def test_time_to_first_sale_keeps_non_sellers_in_denominator(con):
    df = run(con, "13_time_to_first_sale").set_index("milestone")
    assert df.loc["within 7 days", "sellers"] == 1
    assert df.loc["within 60 days", "sellers"] == 1
    assert df.loc["within 90 days", "sellers"] == 3
    assert df.loc["within 90 days", "pct_of_signed_sellers"] == 60.0
    assert df.loc["first sale after day 90", "sellers"] == 1     # l3, day 102
    assert df.loc["no sale in the order data", "sellers"] == 1   # l6
    assert df.loc[["within 90 days", "first sale after day 90",
                   "no sale in the order data"], "sellers"].sum() == 5


def test_activation_by_channel_pools_small_channels_and_chains_rates(con):
    # 30 paid-search wins with no sales: big enough for their own row
    add_page_leads(con, "paidpage", "paid_search", n=40, wins=30)
    df = run(con, "14_activation_by_channel").set_index("channel")
    paid = df.loc["paid_search"]
    assert (paid["sellers"], paid["sold_90d"], paid["pct_sold_90d"]) == (30, 0, 0.0)
    assert paid["ci95_low"] == 0 and paid["ci95_high"] > 0
    assert (paid["lead_pct_won_90d"], paid["selling_sellers_per_1k_leads"]) == (75.0, 0.0)
    pooled = df.loc["smaller channels (pooled)"]       # the 5 fixture sellers
    assert (pooled["sellers"], pooled["sold_90d"], pooled["pct_sold_90d"]) == (5, 3, 60.0)
    # pooled leads: 6 in-window fixture leads, 3 won in 90 days -> 50% x 60%
    assert (pooled["lead_pct_won_90d"], pooled["selling_sellers_per_1k_leads"]) == (50.0, 300.0)
    assert df.index[-1] == "smaller channels (pooled)"
    assert df["pct_of_gmv"].sum() == pytest.approx(100, abs=0.1)


def test_activation_by_lead_type(con):
    con.execute("UPDATE closed_deals SET lead_type = 'offline' WHERE mql_id IN ('l3', 'l6')")
    add_page_leads(con, "bigpage", "paid_search", n=30, wins=30)
    con.execute("UPDATE closed_deals SET lead_type = 'online_big' WHERE mql_id LIKE 'bigpage%'")
    df = run(con, "15_activation_by_lead_type").set_index("lead_type")
    assert list(df.index) == ["online_big", "other types (pooled)"]
    big, other = df.loc["online_big"], df.loc["other types (pooled)"]
    assert (big["sellers"], big["sold_90d"]) == (30, 0)
    assert (other["sellers"], other["sold_90d"], other["gmv_90d"]) == (5, 3, 200.0)
    assert other["pct_of_sellers"] == pytest.approx(100 * 5 / 35, abs=0.05)
