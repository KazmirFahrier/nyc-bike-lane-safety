"""Figures for the policy brief.

The event-study plot is the one that matters. It is the chart that lets a
reader decide for themselves whether the design is credible, because it shows
the pre-treatment years alongside the post-treatment ones. A brief that
reports only the headline number is asking to be trusted; a brief that prints
the pre-trend is showing its work.

It is published whatever it shows -- including, as here, when it undermines
the design.

Usage:
    python analysis/figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "analysis" / "output"

INK = "#1a1a1a"
ACCENT = "#0b5394"
WARN = "#b45309"
GRID = "#d9d9d9"


def _style(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=INK, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)


def event_study() -> None:
    ev = pd.read_csv(OUT / "event_study.csv")
    fig, ax = plt.subplots(figsize=(8.6, 5.4))
    fig.subplots_adjust(top=0.80, left=0.13, right=0.97, bottom=0.13)
    _style(ax)

    pre = ev[ev["event_time"] < 0]
    post = ev[ev["event_time"] >= 0]

    ax.axhline(0, color=INK, linewidth=0.9)
    ax.axvline(-0.5, color=WARN, linewidth=1.1, linestyle="--")

    for d, c, lbl in ((pre, WARN, "before installation"), (post, ACCENT, "after")):
        ax.fill_between(d["event_time"], d["ci_lo"], d["ci_hi"], color=c, alpha=0.15)
        ax.plot(d["event_time"], d["att"], color=c, linewidth=1.8, marker="o",
                markersize=5, label=lbl)

    ax.annotate("lane installed", xy=(-0.5, ax.get_ylim()[1]), xycoords="data",
                xytext=(4, -12), textcoords="offset points",
                color=WARN, fontsize=9, ha="left", va="top")

    ax.set_xlabel("Years since protected lane installed", fontsize=10, color=INK)
    ax.set_ylabel("Cyclist injuries per segment-year\nvs matched control corridors",
                  fontsize=10, color=INK)
    ax.legend(frameon=False, fontsize=9, loc="lower left", ncol=2)

    # Sign convention matters here and is easy to state backwards. Estimates
    # are measured against e=-1, so a NEGATIVE pre-period point means the
    # treated corridors sat below their base-year level -- i.e. they were
    # rising into the year the lane was installed, not falling.
    fig.text(0.13, 0.945, "No break at installation: after-estimates match the before-trend",
             fontsize=13, color=INK, ha="left", va="top", weight="medium")
    fig.text(0.13, 0.885,
             "Measured against the year before installation. A point below zero means injuries were lower\n"
             "than in that base year, so the rising pre-period line is a corridor getting more dangerous\n"
             "in the run-up to the lane -- which is why DOT installed one.",
             fontsize=8.6, color="#555555", ha="left", va="top", linespacing=1.45)

    fig.savefig(OUT / "event_study.png", dpi=180)
    print("wrote event_study.png")


def raw_trends() -> None:
    """The un-differenced series. Shows the selection directly."""
    import duckdb
    from nycbike import config
    import numpy as np

    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    panel = con.execute("""select corridor_id, panel_year, n_segments,
        cyclist_injured::double/n_segments as ips from main.fct_corridor_year_panel""").df()
    m = con.execute("""select cohort_year, unit_id as corridor_id, is_treated_here, cem_weight
        from main.int_matched_corridors where in_common_support and cem_weight>0""").df()
    con.close()

    d = m.merge(panel, on="corridor_id")
    d["e"] = d["panel_year"] - d["cohort_year"]
    d = d[d["e"].between(-5, 5)]
    rows = []
    for e, g in d.groupby("e"):
        t, c = g[g["is_treated_here"]], g[~g["is_treated_here"]]
        rows.append({
            "e": e,
            "treated": np.average(t["ips"], weights=t["cem_weight"]) if len(t) else np.nan,
            "control": np.average(c["ips"], weights=c["cem_weight"]) if len(c) else np.nan,
        })
    r = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(8, 4.8))
    _style(ax)
    ax.axvline(-0.5, color=WARN, linewidth=1.1, linestyle="--")
    ax.plot(r["e"], r["treated"], color=ACCENT, marker="o", markersize=5,
            linewidth=1.8, label="corridors that got a protected lane")
    ax.plot(r["e"], r["control"], color="#888888", marker="s", markersize=4,
            linewidth=1.6, label="matched comparison corridors")
    ax.annotate("lane installed", xytext=(-0.35, 0.94), xy=(-0.5, 0),
                textcoords="axes fraction", color=WARN, fontsize=9)
    ax.set_xlabel("Years since protected lane installed", fontsize=10)
    ax.set_ylabel("Cyclist injuries per segment-year", fontsize=10)
    ax.set_title("Injuries on treated corridors rose 55% in the five years before the lane",
                 fontsize=12, color=INK, loc="left", pad=14)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "raw_trends.png", dpi=180)
    print("wrote raw_trends.png")


def spec_ladder() -> None:
    import numpy as np
    cm = pd.read_csv(OUT / "count_models.csv")
    labels = {"1_pooled_nb": "Pooled\n(year + borough only)",
              "3_poisson_fe": "+ corridor and\nyear fixed effects",
              "4_poisson_fe_matched": "+ CEM matching"}
    cm["pct"] = 100 * (np.exp(cm["coef"]) - 1)
    cm["lo"] = 100 * (np.exp(cm["coef"] - 1.96 * cm["se"]) - 1)
    cm["hi"] = 100 * (np.exp(cm["coef"] + 1.96 * cm["se"]) - 1)

    fig, ax = plt.subplots(figsize=(7.5, 4))
    _style(ax)
    y = range(len(cm))
    ax.axvline(0, color=INK, linewidth=0.9)
    ax.errorbar(cm["pct"], y, xerr=[cm["pct"] - cm["lo"], cm["hi"] - cm["pct"]],
                fmt="o", color=ACCENT, capsize=4, markersize=7, linewidth=1.5)
    ax.set_yticks(list(y))
    ax.set_yticklabels([labels.get(s, s) for s in cm["spec"]], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Estimated change in cyclist injuries (%)", fontsize=10)
    ax.set_title("What you condition on changes the answer",
                 fontsize=12, color=INK, loc="left", pad=14)
    fig.tight_layout()
    fig.savefig(OUT / "spec_ladder.png", dpi=180)
    print("wrote spec_ladder.png")


def equity() -> None:
    """Two panels: how much protected lane each group has, and when they got it.

    Per-resident rather than network-conditioned, because conditioning on the
    existing bike network hides neighborhoods the network never reached.
    """
    import numpy as np
    tr = pd.read_csv(OUT / "equity_tracts.csv")
    cor = pd.read_csv(OUT / "equity_corridors.csv")

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.4))

    panels = [
        ("income_q", "Median household income", ["Q1\nlowest", "Q2", "Q3", "Q4", "Q5\nhighest"]),
        ("poc_q", "Share people of color", ["Q1\nleast", "Q2", "Q3", "Q4", "Q5\nmost"]),
    ]
    for ax, (key, title, ticks) in zip(axes, panels):
        _style(ax)
        g = tr.groupby(key, observed=True).agg(
            pop=("pop_total", "sum"), ft=("protected_ft", "sum"))
        g = g.reindex([c for c in tr[key].dropna().unique().tolist()
                       if c in g.index]) if False else g.sort_index()
        mi_per_10k = 10_000 * (g["ft"] / 5280.0) / g["pop"]

        # Color by rank so the disparity reads without needing the axis.
        vals = mi_per_10k.to_numpy()
        norm = (vals - vals.min()) / (vals.max() - vals.min() + 1e-9)
        colors = [plt.cm.Blues(0.35 + 0.5 * n) for n in norm]
        ax.bar(range(len(vals)), vals, color=colors, edgecolor=ACCENT, linewidth=.7)
        for i, v in enumerate(vals):
            ax.text(i, v, f"{v:.2f}", ha="center", va="bottom", fontsize=8.5, color=INK)
        ax.set_xticks(range(len(vals)))
        ax.set_xticklabels(ticks, fontsize=8.5)
        ax.set_title(title, fontsize=10.5, color=INK, loc="left", pad=8)
        ax.set_ylim(0, vals.max() * 1.22)
        ax.set_ylabel("Protected lane miles\nper 10,000 residents", fontsize=9)

    # Not "richer and whiter" as a clean gradient -- neither panel is monotone.
    # On income the *middle* quintile is worst served, not the poorest; on POC
    # share the fourth quintile is worst, not the fifth. What is true, and
    # what the title says, is the spread.
    fig.suptitle("Protected lane miles per resident vary threefold across neighborhoods",
                 fontsize=12.5, color=INK, x=0.055, ha="left", y=0.985)
    fig.text(0.055, 0.925,
             "Richest fifth of tracts: 0.40 mi per 10,000 residents. Middle fifth: 0.12. "
             "The pattern is a gap, not a gradient.",
             fontsize=9, color="#555555", ha="left")
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(OUT / "equity.png", dpi=180)
    print("wrote equity.png")

    # --- timing ---
    # Two panels rather than two series on shared rows. On one series Q1 means
    # lowest income; on the other it means *least* people of color -- opposite
    # ends of their distributions. Plotting them against shared row labels put
    # 2022 and 2019 on a row called "Q1" and invited exactly the wrong reading.
    sw = cor[cor["treatment_cohort"] == "switcher"]
    fig2, axes2 = plt.subplots(1, 2, figsize=(10.5, 3.5), sharex=True)
    specs = [
        ("income_q", ACCENT, "By median household income",
         ["Q1 lowest", "Q2", "Q3", "Q4", "Q5 highest"]),
        ("poc_q", WARN, "By share people of color",
         ["Q1 least", "Q2", "Q3", "Q4", "Q5 most"]),
    ]
    for ax, (key, c, title, ticks) in zip(axes2, specs):
        _style(ax)
        med = sw.groupby(key, observed=True)["first_protected_year"].median().sort_index()
        ax.barh(range(len(med)), med - 2013, left=2013, height=.55,
                color=c, alpha=.85)
        for i, v in enumerate(med):
            ax.text(v + .1, i, f"{int(v)}", va="center", fontsize=9, color=INK)
        ax.set_yticks(range(len(med)))
        ax.set_yticklabels(ticks, fontsize=8.5)
        ax.invert_yaxis()
        ax.set_xlim(2013, 2024.5)
        ax.set_title(title, fontsize=10, color=INK, loc="left", pad=8)
        ax.set_xlabel("Median year the corridor got its lane", fontsize=9)

    fig2.suptitle("The poorest and the most-POC corridors were treated last",
                  fontsize=12.5, color=INK, x=0.055, ha="left", y=0.99)
    fig2.tight_layout(rect=[0, 0, 1, 0.90])
    fig2.savefig(OUT / "equity_timing.png", dpi=180)
    print("wrote equity_timing.png")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    raw_trends()
    spec_ladder()
    try:
        event_study()
    except FileNotFoundError:
        print("event_study.csv not present yet -- run analysis/did.py")
    try:
        equity()
    except FileNotFoundError:
        print("equity_*.csv not present yet -- run analysis/equity.py")
