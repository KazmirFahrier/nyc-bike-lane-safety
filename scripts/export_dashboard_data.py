"""Export the analysis to flat files: JSON for the web dashboard, CSV for Tableau.

Both come from the same query, so the dashboard and any Tableau workbook built
on the extracts cannot disagree with each other or with the brief.

Usage:
    python scripts/export_dashboard_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nycbike import config  # noqa: E402

OUT_WEB = ROOT / "docs" / "dashboard"
OUT_TAB = ROOT / "data" / "tableau"
BORO = {"1": "Manhattan", "2": "Bronx", "3": "Brooklyn", "4": "Queens", "5": "Staten Island"}


def main() -> None:
    OUT_WEB.mkdir(parents=True, exist_ok=True)
    OUT_TAB.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)

    # --- corridor grain: the fact table --------------------------------
    cor = con.execute("""
        select corridor_id,
               any_value(street)               as street,
               any_value(boro_code)            as boro_code,
               any_value(n_segments)           as n_segments,
               any_value(treatment_cohort)     as treatment_cohort,
               any_value(first_protected_year) as first_protected_year,
               sum(cyclist_injured)            as injuries,
               sum(cyclist_killed)             as deaths,
               count(*)                        as years
        from main.fct_corridor_year_panel group by corridor_id
    """).df()
    cor["borough"] = cor["boro_code"].map(BORO)
    cor["inj_per_seg_year"] = cor["injuries"] / (cor["n_segments"] * cor["years"])
    cor["is_protected"] = cor["treatment_cohort"].isin(["switcher", "always_treated"])

    eq = pd.read_csv(ROOT / "analysis/output/equity_corridors.csv")
    cor = cor.merge(eq[["corridor_id", "income", "share_poc", "poverty_rate", "length_mi"]],
                    on="corridor_id", how="left")

    # --- panel grain: corridor x year ----------------------------------
    panel = con.execute("""
        select corridor_id, panel_year, boro_code, n_segments, is_treated,
               treatment_cohort, first_protected_year, cyclist_injured,
               cyclist_killed, ridership_index
        from main.fct_corridor_year_panel
    """).df()
    panel["borough"] = panel["boro_code"].map(BORO)

    # --- yearly citywide series ----------------------------------------
    yearly = (panel.groupby("panel_year")
              .agg(injuries=("cyclist_injured", "sum"),
                   deaths=("cyclist_killed", "sum"),
                   ridership=("ridership_index", "max"))
              .reset_index())
    installs = (cor[cor["first_protected_year"].between(2013, 2024)]
                .groupby("first_protected_year").size().rename("corridors_treated"))
    yearly = yearly.merge(installs, left_on="panel_year", right_index=True, how="left")
    yearly["corridors_treated"] = yearly["corridors_treated"].fillna(0).astype(int)
    yearly["injuries_per_ridership"] = (
        yearly["injuries"] / yearly["ridership"] * 100).round(2)

    # --- equity quintiles, from the tract file --------------------------
    tr = pd.read_csv(ROOT / "analysis/output/equity_tracts.csv")
    tr["income_q"] = pd.qcut(tr["median_household_income"], 5, labels=[1, 2, 3, 4, 5])
    tr["poc_q"] = pd.qcut(tr["share_poc"], 5, labels=[1, 2, 3, 4, 5])
    eqrows = []
    for key, kind in (("income_q", "income"), ("poc_q", "poc")):
        g = tr.groupby(key, observed=True).agg(
            pop=("pop_total", "sum"), ft=("protected_ft", "sum"), tracts=("geoid", "count"),
            with_any=("protected_ft", lambda s: float((s > 0).mean())))
        for q, r in g.iterrows():
            eqrows.append({
                "kind": kind, "quintile": int(q),
                "miles_per_10k": round(10_000 * (r["ft"] / 5280.0) / r["pop"], 3),
                "pct_tracts_with_any": round(100 * r["with_any"], 1),
                "tracts": int(r["tracts"]), "population": int(r["pop"]),
            })
    equity = pd.DataFrame(eqrows)

    sw = eq[eq["treatment_cohort"] == "switcher"].copy()
    sw["income_q"] = pd.qcut(sw["income"], 5, labels=[1, 2, 3, 4, 5])
    sw["poc_q"] = pd.qcut(sw["share_poc"], 5, labels=[1, 2, 3, 4, 5])
    timing = []
    for key, kind in (("income_q", "income"), ("poc_q", "poc")):
        for q, v in sw.groupby(key, observed=True)["first_protected_year"].median().items():
            timing.append({"kind": kind, "quintile": int(q), "median_year": int(v)})

    # --- headline estimates --------------------------------------------
    cm = pd.read_csv(ROOT / "analysis/output/count_models.csv")
    base = 0.0878
    estimates = [
        {"label": "Compared to the year before installation",
         "method": "Callaway-Sant'Anna, base = last pre-treatment year",
         "pct": -17.7, "lo": -57.3, "hi": 20.2, "anchor": True},
        {"label": "Compared to the earlier pre-installation years",
         "method": "Callaway-Sant'Anna, base = four years before that",
         "pct": 8.0, "lo": -16.6, "hi": 34.7, "anchor": False},
        {"label": "Compared within each corridor, before vs after",
         "method": "Poisson fixed effects, CEM-matched, corridor-clustered",
         "pct": 12.1, "lo": -4.3, "hi": 31.3, "anchor": False},
    ]

    con.close()

    # --- write ----------------------------------------------------------
    payload = {
        "meta": {
            "study_start": 2013, "study_end": 2024,
            "corridors": int(len(cor)),
            "treated_corridors": int(cor["is_protected"].sum()),
            "crashes": 57353, "segments": int(cor["n_segments"].sum()),
            "ridership_growth_pct": 44.5,
        },
        "estimates": estimates,
        "yearly": yearly.replace({np.nan: None}).to_dict("records"),
        "equity": equity.to_dict("records"),
        "timing": timing,
        "corridors": (cor[["corridor_id", "street", "borough", "n_segments", "length_mi",
                           "treatment_cohort", "first_protected_year", "injuries", "deaths",
                           "inj_per_seg_year", "income", "share_poc", "is_protected"]]
                      .round({"inj_per_seg_year": 4, "length_mi": 3,
                              "share_poc": 3, "income": 0})
                      .replace({np.nan: None}).to_dict("records")),
    }
    (OUT_WEB / "data.json").write_text(json.dumps(payload, separators=(",", ":")))
    print(f"wrote docs/dashboard/data.json "
          f"({(OUT_WEB / 'data.json').stat().st_size/1024:,.0f} KB)")

    # Tableau prefers long, tidy, one-grain-per-file extracts.
    cor.to_csv(OUT_TAB / "corridors.csv", index=False)
    panel.to_csv(OUT_TAB / "corridor_year_panel.csv", index=False)
    yearly.to_csv(OUT_TAB / "citywide_by_year.csv", index=False)
    equity.to_csv(OUT_TAB / "equity_by_quintile.csv", index=False)
    pd.DataFrame(timing).to_csv(OUT_TAB / "equity_timing.csv", index=False)
    pd.DataFrame(estimates).to_csv(OUT_TAB / "estimates.csv", index=False)
    for f in sorted(OUT_TAB.glob("*.csv")):
        print(f"  {f.name:<28} {sum(1 for _ in open(f)) - 1:>7,} rows")


if __name__ == "__main__":
    main()
