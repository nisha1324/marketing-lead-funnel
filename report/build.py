"""Run every query in sql/ against the DuckDB store and write a report.

Usage:  python -m report.build   (after python -m pipeline.build_db)
Outputs: results/REPORT.md, results/csv/<query>.csv, results/charts/*.png
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
RESULTS = ROOT / "results"
CHARTS = RESULTS / "charts"
CSV_DIR = RESULTS / "csv"

ACCENT = "#2a6fdb"
MUTED = "#9aa5b1"
INK = "#1f2933"
GRID = "#e4e7eb"


def run_queries(con: duckdb.DuckDBPyConnection) -> dict[str, pd.DataFrame]:
    out = {}
    for path in sorted(SQL_DIR.glob("*.sql")):
        out[path.stem] = con.execute(path.read_text()).df()
    return out


def _style(ax, grid_axis: str = "y") -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(MUTED)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=INK)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _save(fig, name: str) -> Path:
    fig.tight_layout()
    path = CHARTS / name
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def chart_cohorts(df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(10, 3.8))
    colors = [MUTED if inc else ACCENT for inc in df["deal_tracking_incomplete"]]
    ax.bar(df["cohort"], df["pct_won_90d"], color=colors, width=0.6)
    for x, (p, n, inc) in enumerate(zip(df["pct_won_90d"], df["mqls"],
                                        df["deal_tracking_incomplete"])):
        rate = "n/a" if inc else f"{p:.1f}%"
        ax.text(x, p + 0.3, f"{rate}\n{n:,} leads", ha="center", color=INK, fontsize=8)
    ax.set_ylim(0, df["pct_won_90d"].max() * 1.35)
    ax.set_ylabel("% signed within 90 days")
    ax.set_title("Lead-to-seller conversion by month of first contact\n"
                 "(grey: 2017 leads; deal records start in Dec 2017, so their wins are missing)",
                 loc="left", color=INK, fontsize=10)
    ax.tick_params(axis="x", labelsize=8)
    _style(ax)
    return _save(fig, "01_cohort_conversion.png")


def chart_channels(df: pd.DataFrame) -> Path:
    df = df.sort_values("pct_won_90d")
    fig, ax = plt.subplots(figsize=(9, 4.8))
    y = range(len(df))
    ax.hlines(y, df["ci95_low"], df["ci95_high"], color=MUTED, linewidth=2)
    ax.scatter(df["pct_won_90d"], y, color=ACCENT, s=40, zorder=3)
    overall = 100 * df["won_90d"].sum() / df["mqls"].sum()
    for yi, (p, hi, n) in enumerate(zip(df["pct_won_90d"], df["ci95_high"], df["mqls"])):
        ax.text(max(hi, overall) + 0.6, yi, f"{p:.1f}%  ({n:,} leads)", va="center", color=INK, fontsize=8)
    ax.axvline(overall, color=INK, linestyle="--", linewidth=1)
    ax.text(overall + 0.3, -0.9, f"all leads {overall:.1f}%", color=INK, fontsize=8)
    ax.set_yticks(list(y), df["origin"])
    ax.set_xlim(0, df["ci95_high"].max() + 10)
    ax.set_ylim(-1.2, len(df) - 0.5)
    ax.set_xlabel("% signed within 90 days (bar = 95% interval), leads from Jan-May 2018")
    ax.set_title("Conversion by acquisition channel", loc="left", color=INK)
    _style(ax, grid_axis="x")
    return _save(fig, "02_channel_conversion.png")


def chart_time_to_close(df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.bar(df["bucket"], df["pct_of_wins"], color=ACCENT, width=0.6)
    for x, (p, cum) in enumerate(zip(df["pct_of_wins"], df["cumulative_pct"])):
        ax.text(x, p + 0.8, f"{p:.1f}%\n(cum. {cum:.0f}%)", ha="center", color=INK, fontsize=8)
    ax.set_ylim(0, df["pct_of_wins"].max() * 1.3)
    ax.set_ylabel("% of won deals")
    ax.set_title("Most deals sign in the first two weeks", loc="left", color=INK)
    _style(ax)
    return _save(fig, "03_time_to_close.png")


def chart_may_bridge(df: pd.DataFrame) -> Path:
    total = df[df["origin"] == "TOTAL"].iloc[0]
    base, may = total["base_pct_won_90d"], total["may_pct_won_90d"]
    mix, rate = total["mix_effect_pts"], total["rate_effect_pts"]
    labels = ["Jan-Apr 2018", "Channel mix", "Within-channel\nconversion", "May 2018"]
    bottoms = [0, base + mix, base + mix + rate, 0]
    heights = [base, -mix, -rate, may]
    colors = [ACCENT, MUTED, MUTED, ACCENT]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.bar(labels, heights, bottom=bottoms, color=colors, width=0.55)
    texts = [f"{base:.1f}%", f"{mix:+.2f} pts", f"{rate:+.2f} pts", f"{may:.1f}%"]
    tops = [base, base, base + mix, may]
    for x, (t, top) in enumerate(zip(texts, tops)):
        ax.text(x, top + 0.25, t, ha="center", color=INK, fontsize=9)
    ax.set_ylim(0, base * 1.2)
    ax.set_ylabel("% signed within 90 days")
    ax.set_title("May's drop came from weaker conversion within channels, not the mix",
                 loc="left", color=INK, fontsize=11)
    _style(ax)
    return _save(fig, "04_may_drop_bridge.png")


def chart_sales_capacity(cap: pd.DataFrame, conc: pd.DataFrame) -> Path:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.9), gridspec_kw={"width_ratios": [1.1, 1]})
    ax1.bar(cap["cohort"], cap["srs_with_a_win"], color=ACCENT, width=0.6)
    for x, (n, w) in enumerate(zip(cap["srs_with_a_win"], cap["wins_per_sr"])):
        ax1.text(x, n + 0.3, f"{n} reps\n{w:.1f} wins each", ha="center", color=INK, fontsize=8)
    ax1.set_ylim(0, cap["srs_with_a_win"].max() * 1.35)
    ax1.set_ylabel("sales reps (SR) with a win")
    ax1.set_title("Reps who closed deals, by lead cohort", loc="left", color=INK, fontsize=10)
    _style(ax1)
    ax2.plot(conc["sr_rank"], conc["cum_pct_of_wins"], color=ACCENT, marker="o", markersize=4)
    ax2.axhline(50, color=MUTED, linestyle="--", linewidth=1)
    ax2.text(conc["sr_rank"].iloc[-1], 52, "50%", ha="right", color=INK, fontsize=8)
    ax2.set_xticks(conc["sr_rank"])
    ax2.set_ylim(0, 105)
    ax2.set_xlabel("reps, ranked by wins")
    ax2.set_ylabel("cumulative % of 2018 wins")
    ax2.set_title("Top reps' share of wins (top 10 shown)", loc="left", color=INK, fontsize=10)
    _style(ax2)
    return _save(fig, "05_sales_capacity.png")


PAGE_CHANNELS = ["organic_search", "paid_search", "social", "unknown"]


def chart_pages_within_channel(df: pd.DataFrame) -> Path:
    df = df[df["origin"].isin(PAGE_CHANNELS)]
    fig, ax = plt.subplots(figsize=(9, 5.6))
    y, ticks, labels = 0.0, [], []
    for origin in PAGE_CHANNELS:
        group = df[df["origin"] == origin]
        ax.text(-0.5, y - 0.15, f"{origin} (all pages {group['channel_pct_won_90d'].iloc[0]:.1f}%)",
                color=INK, fontsize=9, fontweight="bold", va="top")
        y += 0.9
        top = y
        rate = group["channel_pct_won_90d"].iloc[0]
        for _, row in group.iterrows():
            ax.hlines(y, row["ci95_low"], row["ci95_high"], color=MUTED, linewidth=2)
            ax.scatter(row["pct_won_90d"], y, color=ACCENT, s=40, zorder=3)
            ax.text(max(row["ci95_high"], rate) + 0.6, y, f"{row['pct_won_90d']:.1f}%  ({row['mqls']} leads)",
                    va="center", color=INK, fontsize=8)
            ticks.append(y)
            labels.append(f"page {row['page']}")
            y += 1
        ax.vlines(rate, top - 0.4, y - 0.6, color=INK, linestyle="--", linewidth=1)
        y += 0.5
    ax.set_yticks(ticks, labels, fontsize=8)
    ax.set_ylim(y - 0.5, -0.8)
    ax.set_xlim(0, df["ci95_high"].max() + 9)
    ax.set_xlabel("% signed within 90 days (bar = 95% interval; dashed = channel's rate "
                  "across all its pages)", fontsize=9)
    ax.set_title("Same channel, different landing page: pages with 50+ leads from the channel",
                 loc="left", color=INK, fontsize=10)
    _style(ax, grid_axis="x")
    return _save(fig, "06_pages_within_channel.png")


def chart_may_by_lead_type(df: pd.DataFrame) -> Path:
    total = df[df["lead_type"] == "TOTAL"].iloc[0]
    df = df[~df["lead_type"].isin(["TOTAL", "(missing)"])].sort_values("change_per_1k")
    fig, ax = plt.subplots(figsize=(9, 3.8))
    colors = [ACCENT if c < 0 else MUTED for c in df["change_per_1k"]]
    ax.barh(df["lead_type"], df["change_per_1k"], color=colors, height=0.6)
    for yi, (c, b, m) in enumerate(zip(df["change_per_1k"], df["base_wins_per_1k_leads"],
                                       df["may_wins_per_1k_leads"])):
        x = c - 0.6 if c < 0 else c + 0.6
        ax.text(x, yi, f"{c:+.1f}  ({b:.1f} -> {m:.1f})", va="center",
                ha="right" if c < 0 else "left", color=INK, fontsize=8)
    ax.axvline(0, color=INK, linewidth=0.8)
    ax.set_xlim(df["change_per_1k"].min() - 14, df["change_per_1k"].max() + 12)
    ax.set_xlabel("change in 90-day wins per 1,000 leads, May vs Jan-Apr 2018 "
                  "(Jan-Apr -> May in brackets)", fontsize=9)
    ax.set_title(f"May signed {-total['change_per_1k']:.1f} fewer sellers per 1,000 leads: "
                 "which types went missing",
                 loc="left", color=INK, fontsize=10)
    _style(ax, grid_axis="x")
    return _save(fig, "07_may_drop_by_lead_type.png")


def write_report(results: dict[str, pd.DataFrame]) -> Path:
    lines = [
        "# Results",
        "",
        "Generated by `python -m report.build`. Leads first contacted 2017-06-14 to "
        "2018-05-31; deals won 2017-12-05 to 2018-11-14. Queries 2-4 use the 2018 cohorts.",
        "",
    ]
    for name, df in results.items():
        title = (SQL_DIR / f"{name}.sql").read_text().splitlines()[0].lstrip("- ").strip()
        lines += [f"## {title}", "", f"Query: [`sql/{name}.sql`](../sql/{name}.sql)", "",
                  df.to_markdown(index=False), ""]
    path = RESULTS / "REPORT.md"
    path.write_text("\n".join(lines))
    return path


def main() -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(ROOT / "data" / "funnel.duckdb"), read_only=True)
    results = run_queries(con)
    con.close()
    for name, df in results.items():
        df.to_csv(CSV_DIR / f"{name}.csv", index=False)
    print(chart_cohorts(results["01_cohort_conversion"]))
    print(chart_channels(results["02_channel_conversion"]))
    print(chart_time_to_close(results["03_time_to_close"]))
    print(chart_may_bridge(results["04_may_drop_mix_vs_rate"]))
    print(chart_sales_capacity(results["05_sales_capacity"], results["06_rep_concentration"]))
    print(chart_pages_within_channel(results["08_pages_within_channel"]))
    print(chart_may_by_lead_type(results["10_may_drop_by_lead_type"]))
    print(write_report(results))


if __name__ == "__main__":
    main()
