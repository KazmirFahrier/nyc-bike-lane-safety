"""Were protected bike lanes distributed evenly across New York's neighborhoods?

This is the question the DOHMH framing asks, and unlike the causal question it
is answerable. "Did the lane reduce injuries" needs a counterfactual the data
cannot supply. "Who got lanes" needs only a careful join, because distribution
is observed rather than inferred.

Two denominators, because they answer different questions and can disagree:

  Network share  -- among corridors that already carry *some* bike facility,
      what fraction were upgraded to a protected lane? This holds constant the
      fact that DOT had already identified the street as a cycling route, and
      isolates the upgrade decision.

  Per resident   -- protected lane miles per 10,000 residents, over all tracts.
      This does not condition on the existing network, so it also captures
      neighborhoods the network never reached in the first place. A place can
      look fine on network share and badly served here, which is exactly the
      pattern that a network-conditioned statistic hides.

Corridors are assigned tract characteristics by *length-weighted overlay*: a
corridor crossing three tracts contributes to each in proportion to the length
that falls inside it. Assigning each corridor to a single tract by midpoint
would misattribute long avenues, which are precisely the corridors that get
protected lanes.

Usage:
    python analysis/equity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import wkt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nycbike import config
from nycbike.logging_setup import setup

FT_PER_MILE = 5280.0


def wavg(g: pd.DataFrame, col: str, weight_col: str = "len_ft") -> float:
    """Length-weighted mean of `col`, ignoring rows with a missing value.

    A corridor crossing three tracts takes each tract's characteristics in
    proportion to the length inside it. Assigning the corridor to one tract by
    its midpoint would misattribute exactly the long avenues that tend to
    receive protected lanes -- which is the whole population of interest.
    """
    v, w = g[col], g[weight_col]
    m = v.notna() & (w > 0)
    return float(np.average(v[m], weights=w[m])) if m.any() else float("nan")


def corridor_geometries(log) -> gpd.GeoDataFrame:
    routes = pd.read_parquet(config.DATA_RAW / "bike_routes.parquet")
    routes = routes[routes["geometry_wkt"].notna()]
    geom = (routes.sort_values("instdate")
                  .drop_duplicates("segmentid", keep="last")[["segmentid", "geometry_wkt"]])
    mapping = pd.read_parquet(config.DATA_INTERIM / "segment_corridors.parquet")
    g = mapping.merge(geom, on="segmentid", how="inner")

    gdf = gpd.GeoDataFrame(
        g, geometry=g["geometry_wkt"].map(wkt.loads), crs=config.CRS_WGS84
    ).to_crs(config.CRS_NYC)
    log.info("corridor segments with geometry: %s", f"{len(gdf):,}")
    return gdf


def main() -> None:
    log = setup("equity")

    tracts = gpd.read_file(config.DATA_EXTERNAL / "acs_tracts.gpkg").to_crs(config.CRS_NYC)
    log.info("tracts: %s", f"{len(tracts):,}")

    segs = corridor_geometries(log)

    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    panel = con.execute("""
        select corridor_id,
               any_value(treatment_cohort)     as treatment_cohort,
               any_value(first_protected_year) as first_protected_year,
               sum(cyclist_injured)            as cyclist_injured,
               any_value(n_segments)           as n_segments
        from main.fct_corridor_year_panel group by corridor_id
    """).df()
    con.close()

    # --- length-weighted overlay: segment length inside each tract ---------
    segs["seg_len_ft"] = segs.geometry.length
    ov = gpd.overlay(
        segs[["segmentid", "corridor_id", "geometry"]],
        tracts[["geoid", "borough", "median_household_income", "share_poc",
                "poverty_rate", "pop_total", "geometry"]],
        how="intersection", keep_geom_type=False,
    )
    ov = ov[ov.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
    ov["len_ft"] = ov.geometry.length
    ov = ov[ov["len_ft"] > 0]
    log.info("corridor-tract overlay pieces: %s", f"{len(ov):,}")

    # --- corridor-level demographics, weighted by length in each tract ----
    cor = ov.groupby("corridor_id").apply(
        lambda g: pd.Series({
            "length_ft": g["len_ft"].sum(),
            "income": wavg(g, "median_household_income"),
            "share_poc": wavg(g, "share_poc"),
            "poverty_rate": wavg(g, "poverty_rate"),
            "borough": g.loc[g["len_ft"].idxmax(), "borough"],
        }), include_groups=False,
    ).reset_index()

    cor = cor.merge(panel, on="corridor_id", how="inner")
    cor["is_protected"] = cor["treatment_cohort"].isin(["switcher", "always_treated"])
    cor["length_mi"] = cor["length_ft"] / FT_PER_MILE
    cor = cor[cor["income"].notna()]
    log.info("corridors with demographics: %s", f"{len(cor):,}")

    # --- 1. network share, by income quintile -----------------------------
    cor["income_q"] = pd.qcut(cor["income"], 5,
                              labels=["Q1 lowest", "Q2", "Q3", "Q4", "Q5 highest"])
    cor["poc_q"] = pd.qcut(cor["share_poc"], 5,
                           labels=["Q1 least POC", "Q2", "Q3", "Q4", "Q5 most POC"])

    log.info("")
    log.info("=== 1. NETWORK SHARE: of corridors already in the bike network, ===")
    log.info("===    what share were upgraded to a protected lane?            ===")
    for key, name in (("income_q", "median household income"), ("poc_q", "share people of color")):
        log.info("")
        log.info("  by %s:", name)
        t = cor.groupby(key, observed=True).agg(
            corridors=("corridor_id", "count"),
            protected=("is_protected", "sum"),
            miles=("length_mi", "sum"),
            protected_miles=("length_mi", lambda s: s[cor.loc[s.index, "is_protected"]].sum()),
        )
        t["pct_corridors"] = 100 * t["protected"] / t["corridors"]
        t["pct_miles"] = 100 * t["protected_miles"] / t["miles"]
        for q, r in t.iterrows():
            log.info("    %-14s %4d corridors  %5.1f%% protected  %5.1f%% of miles",
                     q, int(r["corridors"]), r["pct_corridors"], r["pct_miles"])

    # --- 2. per resident, over all tracts ---------------------------------
    log.info("")
    log.info("=== 2. PER RESIDENT: protected lane miles per 10,000 people, ===")
    log.info("===    over ALL tracts, not only those already in the network ===")
    prot = ov.merge(cor[["corridor_id", "is_protected"]], on="corridor_id", how="left")
    prot = prot[prot["is_protected"].fillna(False)]
    by_tract = prot.groupby("geoid")["len_ft"].sum().rename("protected_ft")

    tr = tracts.merge(by_tract, left_on="geoid", right_index=True, how="left")
    tr["protected_ft"] = tr["protected_ft"].fillna(0.0)
    tr = tr[tr["pop_total"].fillna(0) > 0].copy()
    tr["income_q"] = pd.qcut(tr["median_household_income"], 5,
                             labels=["Q1 lowest", "Q2", "Q3", "Q4", "Q5 highest"])
    tr["poc_q"] = pd.qcut(tr["share_poc"], 5,
                          labels=["Q1 least POC", "Q2", "Q3", "Q4", "Q5 most POC"])

    for key, name in (("income_q", "median household income"), ("poc_q", "share people of color")):
        log.info("")
        log.info("  by %s:", name)
        t = tr.groupby(key, observed=True).agg(
            tracts=("geoid", "count"),
            pop=("pop_total", "sum"),
            protected_mi=("protected_ft", lambda s: s.sum() / FT_PER_MILE),
        )
        t["mi_per_10k"] = 10_000 * t["protected_mi"] / t["pop"]
        t["pct_tracts_with_any"] = 100 * tr.groupby(key, observed=True)["protected_ft"] \
                                              .apply(lambda s: (s > 0).mean())
        for q, r in t.iterrows():
            log.info("    %-14s %4d tracts  %8s people  %5.1f mi  %.3f mi/10k  "
                     "%4.1f%% of tracts have any",
                     q, int(r["tracts"]), f"{int(r['pop']):,}", r["protected_mi"],
                     r["mi_per_10k"], r["pct_tracts_with_any"])

    # --- 3. timing ---------------------------------------------------------
    log.info("")
    log.info("=== 3. TIMING: when did each group get its lanes? ===")
    sw = cor[cor["treatment_cohort"] == "switcher"]
    for key in ("income_q", "poc_q"):
        log.info("")
        t = sw.groupby(key, observed=True)["first_protected_year"].agg(["count", "median", "mean"])
        for q, r in t.iterrows():
            log.info("    %-14s n=%3d  median year %d  mean %.1f",
                     q, int(r["count"]), int(r["median"]), r["mean"])

    out = ROOT / "analysis" / "output"
    out.mkdir(exist_ok=True)
    cor.to_csv(out / "equity_corridors.csv", index=False)
    tr.drop(columns=["geometry"]).to_csv(out / "equity_tracts.csv", index=False)
    log.info("")
    log.info("wrote equity_corridors.csv and equity_tracts.csv")


if __name__ == "__main__":
    main()
