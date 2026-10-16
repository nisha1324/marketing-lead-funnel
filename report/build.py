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
    print(write_report(results))


if __name__ == "__main__":
    main()
