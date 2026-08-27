"""Staggered difference-in-differences: did protected lanes cut cyclist injuries?

**Estimator.** Callaway & Sant'Anna (2021) group-time average treatment
effects, implemented directly. Two-way fixed effects is *not* used as the
headline, because with staggered adoption and effects that change over time,
TWFE weights some 2x2 comparisons negatively -- already-treated corridors serve
as controls for later-treated ones, and the estimate can carry the wrong sign
even when every underlying effect is negative (Goodman-Bacon 2021). The naive
TWFE number is computed anyway and reported beside the main one, so the size of
that problem is visible rather than asserted.

For each cohort g and period t:

    ATT(g,t) = [Y_treated(t) - Y_treated(g-1)] - [Y_control(t) - Y_control(g-1)]

Controls are never-treated plus not-yet-treated corridors, CEM-weighted within
borough x pre-period-injury stratum. The base period is g-1, the last year
before the lane went in.

**Outcome** is cyclist injuries per segment-year. Corridors vary from 1 to 105
segments; using raw counts would let long corridors dominate and would confound
corridor length with effect size.

**On exposure.** A DiD against contemporaneous controls differences out
citywide ridership growth automatically -- both groups live through the same
years. What it cannot difference out is *differential* ridership change: if a
protected lane itself attracts riders, treated corridors gain exposure that
controls do not, and the estimate understates the per-rider safety gain. With
41 counters this study cannot measure that, and the brief says so rather than
implying the exposure offset in the negative binomial fixes it.

**Inference** is a corridor-level block bootstrap. Injuries within a corridor
are correlated across years; treating corridor-years as independent would
produce standard errors that are far too small.

Usage:
    python analysis/did.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nycbike import config
from nycbike.logging_setup import setup

# 1,000 replications for published numbers. Override for a fast smoke run:
#   NYCBIKE_N_BOOT=50 python analysis/did.py
# The clean-room reproduction uses a low value to check that the pipeline runs,
# not to reproduce the confidence intervals.
N_BOOT = int(os.environ.get("NYCBIKE_N_BOOT", "1000"))
RNG_SEED = 20260824  # fixed so the numbers in the brief are reproducible
EVENT_WINDOW = (-5, 5)


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    panel = con.execute("""
        select corridor_id, panel_year, boro_code, n_segments,
               treatment_cohort, first_protected_year,
               cyclist_injured, cyclist_killed, crash_count,
               cyclist_injured::double / n_segments as injuries_per_segment
        from main.fct_corridor_year_panel
    """).df()
    matched = con.execute("""
        select cohort_year, unit_id as corridor_id, is_treated_here,
               is_eligible_control, in_common_support, cem_weight, boro_code, injury_bin
        from main.int_matched_corridors
        where in_common_support and cem_weight > 0
    """).df()
    con.close()
    return panel, matched


def att_gt(panel: pd.DataFrame, matched: pd.DataFrame,
           base_window: tuple[int, ...] = (-1,)) -> pd.DataFrame:
    """Group-time ATTs. One row per (cohort, year).

    `base_window` is the set of event times averaged to form the pre-treatment
    reference. The canonical choice is (-1,), the last year before treatment.
    That choice is not innocent here: treated corridors' injury rate rises 55%
    over the five years before the lane goes in, so e=-1 is close to a local
    peak, and anchoring on it credits the lane with the mean reversion that
    would have followed anyway. Passing (-5,-4,-3,-2) anchors on the earlier,
    calmer stretch of the pre-period instead. The gap between the two answers
    is the size of the selection problem.
    """
    y = panel.set_index(["corridor_id", "panel_year"])["injuries_per_segment"]
    rows = []

    for g, mg in matched.groupby("cohort_year"):
        base_years = [g + e for e in base_window]
        treated = mg[mg["is_treated_here"]]
        controls = mg[~mg["is_treated_here"]]
        if treated.empty or controls.empty:
            continue

        for t in sorted(panel["panel_year"].unique()):
            if t in base_years:
                continue
            # A not-yet-treated corridor stops being a valid control once its
            # own lane goes in. Dropping it then is what keeps already-treated
            # units out of the control group -- the whole point of using this
            # estimator instead of TWFE.
            ctrl = controls.merge(
                panel[["corridor_id", "first_protected_year"]].drop_duplicates(),
                on="corridor_id", how="left",
            )
            ctrl = ctrl[
                ctrl["first_protected_year"].isna()
                | (ctrl["first_protected_year"] > max(t, g))
            ]
            if ctrl.empty:
                continue

            def wdiff(units: pd.DataFrame, t=t, base_years=base_years) -> float | None:
                # t and base_years bound as defaults: the closure is only called
                # within this iteration, but binding makes that explicit rather
                # than load-bearing.
                idx_t = list(zip(units["corridor_id"], [t] * len(units), strict=True))
                yt = y.reindex(idx_t).to_numpy(dtype=float)
                # Average the outcome across every year in the base window.
                bs = [
                    y.reindex(list(zip(units["corridor_id"], [b] * len(units), strict=True)))
                     .to_numpy(dtype=float)
                    for b in base_years
                ]
                yb = np.nanmean(np.vstack(bs), axis=0) if len(bs) > 1 else bs[0]
                w = units["cem_weight"].to_numpy(dtype=float)
                ok = ~(np.isnan(yt) | np.isnan(yb))
                if ok.sum() == 0 or w[ok].sum() == 0:
                    return None
                return float(np.average((yt - yb)[ok], weights=w[ok]))

            dt, dc = wdiff(treated), wdiff(ctrl)
            if dt is None or dc is None:
                continue
            rows.append({
                "cohort": g, "year": t, "event_time": t - g,
                "att": dt - dc, "n_treated": len(treated), "n_control": len(ctrl),
            })

    return pd.DataFrame(rows)


def aggregate_event_study(gt: pd.DataFrame) -> pd.DataFrame:
    """Average ATT(g,t) by event time, weighting cohorts by size."""
    lo, hi = EVENT_WINDOW
    w = gt[gt["event_time"].between(lo, hi)]
    out = (
        w.groupby("event_time")
        .apply(lambda d: pd.Series({
            "att": np.average(d["att"], weights=d["n_treated"]),
            "n_cohorts": d["cohort"].nunique(),
            "n_treated": d["n_treated"].sum(),
        }), include_groups=False)
        .reset_index()
    )
    return out


def bootstrap_pvalue(draws: np.ndarray, observed: float) -> float:
    """Two-sided bootstrap p-value for `observed` against a null of zero.

    The subtlety that cost a real bug: the bootstrap distribution is centred on
    the observed statistic, so comparing |draw| against |observed| directly
    returns ~0.5 whatever the data say. The distribution has to be recentred
    first -- then the question is how often a draw falls at least as far from
    the centre as zero does.
    """
    draws = np.asarray(draws, dtype=float)
    draws = draws[~np.isnan(draws)]
    if draws.size == 0:
        return float("nan")
    centred = draws - draws.mean()
    return float(np.mean(np.abs(centred) >= abs(observed)))


def aggregate_overall(gt: pd.DataFrame) -> float:
    post = gt[gt["event_time"] >= 0]
    if post.empty:
        return np.nan
    return float(np.average(post["att"], weights=post["n_treated"]))


BASE_SPECS = {
    "last_pre_year": (-1,),
    "early_pre_window": (-5, -4, -3, -2),
}


def bootstrap(panel: pd.DataFrame, matched: pd.DataFrame, n_boot: int = N_BOOT):
    """Corridor-level block bootstrap. Resamples corridors, not corridor-years.

    Both base-period specifications are computed on the same resamples, so the
    difference between them is not itself bootstrap noise.
    """
    rng = np.random.default_rng(RNG_SEED)
    corridors = matched["corridor_id"].unique()
    overall, events = [], []
    overall_alt = []

    for b in range(n_boot):
        draw = rng.choice(corridors, size=len(corridors), replace=True)
        # Re-label duplicates so a corridor drawn twice contributes twice.
        rep = pd.DataFrame({"corridor_id": draw})
        rep["boot_id"] = rep["corridor_id"] + "#" + rep.groupby("corridor_id").cumcount().astype(str)

        m = matched.merge(rep, on="corridor_id")
        p = panel.merge(rep, on="corridor_id")
        m = m.drop(columns="corridor_id").rename(columns={"boot_id": "corridor_id"})
        p = p.drop(columns="corridor_id").rename(columns={"boot_id": "corridor_id"})

        gt = att_gt(p, m, BASE_SPECS["last_pre_year"])
        if gt.empty:
            continue
        overall.append(aggregate_overall(gt))
        ev = aggregate_event_study(gt).set_index("event_time")["att"]
        events.append(ev)

        gt_alt = att_gt(p, m, BASE_SPECS["early_pre_window"])
        overall_alt.append(aggregate_overall(gt_alt) if not gt_alt.empty else np.nan)

        if (b + 1) % 100 == 0:
            print(f"    bootstrap {b + 1}/{n_boot}", flush=True)

    return np.array(overall), pd.DataFrame(events), np.array(overall_alt)


def twfe(panel: pd.DataFrame, matched: pd.DataFrame) -> float:
    """The naive two-way fixed effects estimate, for comparison only."""
    import statsmodels.formula.api as smf

    units = matched[["corridor_id", "cem_weight"]].drop_duplicates("corridor_id")
    d = panel.merge(units, on="corridor_id")
    d["treated_now"] = (
        d["first_protected_year"].notna()
        & (d["panel_year"] >= d["first_protected_year"])
    ).astype(int)
    d = d.dropna(subset=["injuries_per_segment"])
    m = smf.wls(
        "injuries_per_segment ~ treated_now + C(corridor_id) + C(panel_year)",
        data=d, weights=d["cem_weight"],
    ).fit()
    return float(m.params["treated_now"])


def main() -> None:
    log = setup("did")
    panel, matched = load()
    log.info("corridors in matched design: %s", f"{matched['corridor_id'].nunique():,}")

    gt = att_gt(panel, matched)
    log.info("group-time ATTs estimated: %s", len(gt))

    ev = aggregate_event_study(gt)
    overall = aggregate_overall(gt)

    log.info("running %s bootstrap replications (corridor-level)...", N_BOOT)
    boot_overall, boot_events, boot_alt = bootstrap(panel, matched)

    se = float(np.nanstd(boot_overall, ddof=1))
    lo, hi = np.nanpercentile(boot_overall, [2.5, 97.5])

    ev["se"] = ev["event_time"].map(boot_events.std(ddof=1))
    ev["ci_lo"] = ev["event_time"].map(boot_events.quantile(0.025))
    ev["ci_hi"] = ev["event_time"].map(boot_events.quantile(0.975))

    # --- the pre-trend test, which is what makes or breaks the design -----
    # The bootstrap distribution is centered on the observed statistic, so
    # comparing |bootstrap| against |observed| returns ~0.5 whatever the data
    # say. The test has to be built on the *recentered* distribution: how often
    # does a draw fall as far from the observed value as zero does.
    pre = ev[ev["event_time"] < 0]
    pre_boot = boot_events[[c for c in boot_events.columns if c < 0]]
    pre_mean = float(pre["att"].mean())
    pre_draws = pre_boot.mean(axis=1).to_numpy(dtype=float)
    pre_draws = pre_draws[~np.isnan(pre_draws)]
    pre_se = float(np.std(pre_draws, ddof=1))
    centered = pre_draws - pre_draws.mean()
    joint = float(np.mean(np.abs(centered) >= abs(pre_mean)))
    pre_ci = np.percentile(pre_draws, [2.5, 97.5])

    out = ROOT / "analysis" / "output"
    out.mkdir(exist_ok=True)
    gt.to_csv(out / "att_gt.csv", index=False)
    ev.to_csv(out / "event_study.csv", index=False)


    tw = twfe(panel, matched)

    gt_alt = att_gt(panel, matched, BASE_SPECS["early_pre_window"])
    overall_alt = aggregate_overall(gt_alt)
    lo_alt, hi_alt = np.nanpercentile(boot_alt, [2.5, 97.5])

    # Persist the headline numbers rather than only logging them. The dashboard
    # quotes these, and anything reading them from a log -- or worse, having
    # them typed in by hand -- goes stale silently the first time the analysis
    # is re-run. Written here rather than beside the other CSVs above because
    # every value below has to exist first.
    pd.DataFrame([
        {"spec": "cs_did_base_last_pre_year", "att": overall, "ci_lo": lo, "ci_hi": hi, "se": se},
        {"spec": "cs_did_base_early_window", "att": overall_alt, "ci_lo": lo_alt,
         "ci_hi": hi_alt, "se": float(np.nanstd(boot_alt, ddof=1))},
        {"spec": "twfe_naive", "att": tw, "ci_lo": None, "ci_hi": None, "se": None},
        {"spec": "pretrend_mean", "att": pre_mean, "ci_lo": pre_ci[0],
         "ci_hi": pre_ci[1], "se": pre_se},
    ]).to_csv(out / "did_summary.csv", index=False)

    log.info("")
    log.info("=== EVENT STUDY (injuries per segment-year) ===")
    for _, r in ev.iterrows():
        star = "  <- base" if r["event_time"] == -1 else ""
        log.info("  e=%+d  ATT=%+.4f  [%+.4f, %+.4f]  cohorts=%d%s",
                 int(r["event_time"]), r["att"], r["ci_lo"], r["ci_hi"],
                 int(r["n_cohorts"]), star)
    log.info("")
    log.info("=== HEADLINE ===")
    log.info("  Callaway-Sant'Anna ATT (post-treatment): %+.4f", overall)
    log.info("    bootstrap SE %.4f, 95%% CI [%+.4f, %+.4f]", se, lo, hi)
    log.info("  naive TWFE (biased under staggered adoption): %+.4f", tw)
    log.info("")
    log.info("=== BASE-PERIOD SENSITIVITY ===")
    log.info("  base = last pre-year (e=-1):        ATT %+.4f  [%+.4f, %+.4f]",
             overall, lo, hi)
    log.info("  base = early pre-window (e=-5..-2): ATT %+.4f  [%+.4f, %+.4f]",
             overall_alt, lo_alt, hi_alt)
    log.info("  Treated corridors' injury rate rises 55%% across the pre-period,")
    log.info("  so e=-1 sits near a local peak.")
    if np.sign(overall) != np.sign(overall_alt):
        log.info("")
        log.info("  *** THE SIGN FLIPS. *** The two base periods are both defensible")
        log.info("  and they disagree about the direction of the effect. The headline")
        log.info("  estimate is therefore not identifying the lane -- it is measuring")
        log.info("  reversion from the injury spike that caused DOT to install it.")
        log.info("  Do not report either number as the effect of a protected lane.")
    log.info("")
    log.info("=== PRE-TREND TEST ===")
    log.info("  mean pre-treatment ATT: %+.4f (SE %.4f, 95%% CI [%+.4f, %+.4f])",
             pre_mean, pre_se, pre_ci[0], pre_ci[1])
    log.info("  bootstrap p-value for zero pre-trend: %.3f", joint)
    # Failing to reject a flat pre-trend is NOT evidence that the pre-trend is
    # flat. With four pre-period estimates on a sparse count outcome this test
    # has very little power, and reporting a non-rejection as "parallel trends
    # holds" is how underpowered designs get published. What the pre-trend
    # must be judged against is the effect it is supposed to identify.
    log.info("  NOTE: this test is underpowered. A non-rejection is not evidence")
    log.info("        of parallel trends; judge the pre-trend against the effect size.")
    # The comparison that actually matters for a causal reading: an estimated
    # effect no larger than the pre-existing trend is not evidence of an effect.
    log.info("  pre-trend as a share of the post-treatment ATT: %.0f%%",
             100 * abs(pre_mean) / abs(overall) if overall else float("nan"))
    if abs(pre_mean) >= 0.5 * abs(overall):
        log.info("  WARNING: the pre-treatment trend is at least half the size of the")
        log.info("           estimated effect. The effect cannot be cleanly separated")
        log.info("           from a trend that was already underway before the lane.")

    # Relative effect, which is what a policy reader needs. Baseline is the
    # treated corridors' own pre-treatment mean.
    base_rate = float(
        panel.merge(matched[matched["is_treated_here"]][["corridor_id", "cohort_year"]]
                    .drop_duplicates(), on="corridor_id")
        .query("panel_year < cohort_year")["injuries_per_segment"].mean()
    )
    log.info("")
    log.info("=== IN RELATIVE TERMS ===")
    log.info("  treated corridors' pre-treatment mean: %.4f injuries/segment-year", base_rate)
    log.info("  ATT as %% of that baseline: %+.1f%% (95%% CI %+.1f%% to %+.1f%%)",
             100 * overall / base_rate, 100 * lo / base_rate, 100 * hi / base_rate)
    log.info("")
    log.info("wrote %s and %s", "att_gt.csv", "event_study.csv")


if __name__ == "__main__":
    main()
