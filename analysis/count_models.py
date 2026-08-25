"""Count models for cyclist injuries, with the specification ladder made explicit.

The point of this file is that the same data supports very different numbers
depending on what you condition on, and only one of those numbers answers the
policy question. Reporting the wrong rung as "the effect of protected lanes"
would be the single most damaging error this study could make, so all four are
estimated and printed together.

  (1) Pooled negative binomial, year + borough effects only.
      This is a CROSS-SECTIONAL association. It compares corridors that have
      lanes to corridors that do not, and DOT does not choose corridors at
      random -- it installs where cyclists are already being hurt. This rung
      measures where the lanes are, not what they do. It is here to be
      *contrasted with*, not quoted.

  (2) Add corridor fixed effects.
      Now the comparison is within a corridor, before versus after its own
      lane. Selection on fixed corridor characteristics is differenced out.
      What remains is selection on *timing* -- the fact that lanes arrive right
      after a corridor's injuries spike.

  (3) Poisson with corridor + year fixed effects, cluster-robust.
      Poisson pseudo-maximum-likelihood is consistent for the conditional mean
      even when the data are overdispersed (Wooldridge 1999), and unlike
      negative binomial it does not suffer the incidental-parameters problem
      with thousands of fixed effects. With variance/mean at 6.5 the standard
      errors must be cluster-robust at the corridor, which is what makes the
      estimate usable rather than the point estimate itself.

  (4) The same, restricted to the CEM-matched sample.
      Fixed effects handle time-invariant selection; matching handles
      comparability of the comparison group. Doing both is belt and braces,
      and if (3) and (4) disagree the matching is doing real work.

Exposure enters every rung as an offset: log(segments) carries corridor length,
log(citywide ridership index) carries the fact that far more people ride now
than in 2014. Without the first, long corridors look dangerous; without the
second, the 44.5% growth in cycling since 2014 is charged to the lanes.

Usage:
    python analysis/count_models.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nycbike import config  # noqa: E402
from nycbike.logging_setup import setup  # noqa: E402


def load() -> pd.DataFrame:
    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    d = con.execute("""
        select p.corridor_id, p.panel_year, p.boro_code, p.n_segments,
               p.first_protected_year, p.treatment_cohort,
               p.cyclist_injured, p.log_segments, p.log_exposure, p.has_exposure,
               m.cem_weight, m.in_common_support
        from main.fct_corridor_year_panel p
        left join (
            select unit_id as corridor_id, max(cem_weight) as cem_weight,
                   bool_or(in_common_support) as in_common_support
            from main.int_matched_corridors
            where in_common_support and cem_weight > 0
            group by unit_id
        ) m on m.corridor_id = p.corridor_id
    """).df()
    con.close()

    d = d[d["has_exposure"] & (d["n_segments"] > 0)].copy()
    d["treated_now"] = (
        d["first_protected_year"].notna()
        & (d["panel_year"] >= d["first_protected_year"])
    ).astype(int)
    d["offset_term"] = d["log_segments"] + d["log_exposure"]
    d["year"] = d["panel_year"].astype(str)
    return d


def report(log, label: str, coef: float, se: float, n: int, extra: str = "") -> None:
    irr = np.exp(coef)
    lo, hi = np.exp(coef - 1.96 * se), np.exp(coef + 1.96 * se)
    z = coef / se if se else np.nan
    log.info("  %-46s n=%-7s", label, f"{n:,}")
    log.info("      coef %+.4f (SE %.4f, z=%+.2f)   IRR %.3f [%.3f, %.3f]  => %+.1f%%%s",
             coef, se, z, irr, lo, hi, 100 * (irr - 1), extra)


def main() -> None:
    log = setup("count_models")
    import pyfixest as pf
    import statsmodels.api as sm

    d = load()
    log.info("corridor-years with exposure: %s", f"{len(d):,}")
    log.info("variance/mean of the outcome: %.2f",
             d["cyclist_injured"].var() / d["cyclist_injured"].mean())
    log.info("")

    # --- (1) pooled NB: association, not effect ---------------------------
    X = pd.get_dummies(d[["year", "boro_code"]], drop_first=True).astype(float)
    X.insert(0, "treated_now", d["treated_now"].to_numpy(dtype=float))
    X = sm.add_constant(X)
    nb = sm.GLM(
        d["cyclist_injured"], X,
        family=sm.families.NegativeBinomial(alpha=1.0),
        offset=d["offset_term"],
    ).fit()
    log.info("=== (1) pooled NB, year + borough only -- CROSS-SECTIONAL ASSOCIATION ===")
    report(log, "treated_now", nb.params["treated_now"], nb.bse["treated_now"], len(d))
    log.info("      This is where lanes ARE, not what they DO. Not a treatment effect.")
    log.info("")

    # --- (2)/(3) Poisson FE, cluster-robust -------------------------------
    log.info("=== (3) Poisson PML, corridor + year FE, clustered by corridor ===")
    m3 = pf.fepois(
        "cyclist_injured ~ treated_now | corridor_id + year",
        data=d.assign(offset_term=d["offset_term"]),
        offset="offset_term",
        vcov={"CRV1": "corridor_id"},
    )
    c3 = float(m3.coef().iloc[0]); s3 = float(m3.se().iloc[0])
    report(log, "treated_now (within corridor)", c3, s3, int(m3._N))
    log.info("")

    # --- (4) same, on the CEM-matched sample ------------------------------
    dm = d[d["in_common_support"].fillna(False)].copy()
    log.info("=== (4) Poisson PML on the CEM-matched sample ===")
    m4 = pf.fepois(
        "cyclist_injured ~ treated_now | corridor_id + year",
        data=dm, offset="offset_term", vcov={"CRV1": "corridor_id"},
        weights="cem_weight",
    )
    c4 = float(m4.coef().iloc[0]); s4 = float(m4.se().iloc[0])
    report(log, "treated_now (matched, within corridor)", c4, s4, int(m4._N))
    log.info("")

    log.info("=== READING THE LADDER ===")
    log.info("  (1) pooled                     %+.1f%%", 100 * (np.exp(nb.params['treated_now']) - 1))
    log.info("  (3) + corridor & year FE       %+.1f%%", 100 * (np.exp(c3) - 1))
    log.info("  (4) + CEM matching             %+.1f%%", 100 * (np.exp(c4) - 1))
    log.info("")
    log.info("  The movement from (1) to (3) is the size of the selection problem:")
    log.info("  how much of the raw association is DOT choosing dangerous corridors")
    log.info("  rather than lanes changing outcomes.")

    out = ROOT / "analysis" / "output"
    out.mkdir(exist_ok=True)
    pd.DataFrame([
        {"spec": "1_pooled_nb", "coef": nb.params["treated_now"], "se": nb.bse["treated_now"],
         "n": len(d), "within_corridor": False, "matched": False},
        {"spec": "3_poisson_fe", "coef": c3, "se": s3, "n": int(m3._N),
         "within_corridor": True, "matched": False},
        {"spec": "4_poisson_fe_matched", "coef": c4, "se": s4, "n": int(m4._N),
         "within_corridor": True, "matched": True},
    ]).to_csv(out / "count_models.csv", index=False)
    log.info("")
    log.info("wrote analysis/output/count_models.csv")


if __name__ == "__main__":
    main()
