"""Three maps of the protected lane program.

Built by the pipeline rather than exported by hand from a desktop GIS, so they
regenerate with the data and cannot drift from the numbers in the brief. A QGIS
project file covering the same layers is written alongside them by
scripts/write_qgis_project.py, for anyone who wants to explore interactively.

    1. The build-out    -- where protected lanes went in, and when
    2. The injuries     -- cyclist injury rate by corridor
    3. The disparity    -- lanes over tract income, which is the equity finding
                           in the one form where it needs no explaining

All three are drawn in EPSG:2263 (NAD83 / New York Long Island, feet), the
city's own projection, so shapes are not distorted the way a web-Mercator
basemap would distort them at this latitude.

Usage:
    python analysis/maps.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap
from matplotlib.lines import Line2D
from shapely import wkt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nycbike import config
from nycbike.logging_setup import setup

OUT = ROOT / "analysis" / "output"
LAND = "#eceef1"
LAND_EDGE = "#ffffff"
CONTEXT = "#c9cfd6"
INK = "#1a1a1a"
MUTED = "#6b7480"


# Titles are drawn in figure coordinates above the axes, and legends are
# anchored below them by LEGEND_Y. Drawing both in axes coordinates put the
# legend on top of a two-line subtitle on every map.
LEGEND_Y = 0.86


def _frame(ax, title: str, subtitle: str = "") -> None:
    ax.set_axis_off()
    ax.set_title("")
    fig = ax.get_figure()
    fig.text(0.02, 0.975, title, fontsize=14, color=INK,
             ha="left", va="top", weight="semibold")
    if subtitle:
        fig.text(0.02, 0.945, subtitle, fontsize=9, color=MUTED,
                 ha="left", va="top", linespacing=1.5)


def _source(fig, text: str) -> None:
    fig.text(0.012, 0.012, text, fontsize=7.5, color=MUTED, ha="left", va="bottom")


def load_layers(log):
    tracts = gpd.read_file(config.DATA_EXTERNAL / "acs_tracts.gpkg").to_crs(config.CRS_NYC)
    boros = tracts.dissolve(by="borough")[["geometry"]].reset_index()
    log.info("boroughs: %s", len(boros))

    routes = pd.read_parquet(config.DATA_RAW / "bike_routes.parquet")
    routes = routes[routes["geometry_wkt"].notna()]
    geom = (routes.sort_values("instdate")
                  .drop_duplicates("segmentid", keep="last")[["segmentid", "geometry_wkt"]])

    # segment_corridors.parquet already carries treatment_cohort and
    # first_protected_year. Keep only the join keys, so the merge with the panel
    # below does not produce _x/_y suffixed duplicates of both.
    mapping = pd.read_parquet(config.DATA_INTERIM / "segment_corridors.parquet")[
        ["segmentid", "corridor_id"]
    ]
    segs = mapping.merge(geom, on="segmentid", how="inner")
    segs = gpd.GeoDataFrame(
        segs, geometry=segs["geometry_wkt"].map(wkt.loads), crs=config.CRS_WGS84
    ).to_crs(config.CRS_NYC)

    all_routes = gpd.GeoDataFrame(
        geom, geometry=geom["geometry_wkt"].map(wkt.loads), crs=config.CRS_WGS84
    ).to_crs(config.CRS_NYC)

    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    panel = con.execute("""
        select corridor_id,
               any_value(treatment_cohort)     as treatment_cohort,
               any_value(first_protected_year) as first_protected_year,
               any_value(n_segments)           as n_segments,
               sum(cyclist_injured)            as injuries,
               count(*)                        as corridor_years
        from main.fct_corridor_year_panel group by corridor_id
    """).df()
    con.close()
    panel["inj_per_seg_year"] = panel["injuries"] / (panel["n_segments"] * panel["corridor_years"])

    segs = segs.merge(panel, on="corridor_id", how="left")
    log.info("segments with corridor + panel data: %s", f"{len(segs):,}")
    return boros, all_routes, segs, tracts


def map_buildout(boros, all_routes, segs, log) -> None:
    """Where protected lanes went in, and when."""
    fig, ax = plt.subplots(figsize=(9.5, 10))
    boros.plot(ax=ax, color=LAND, edgecolor=LAND_EDGE, linewidth=1.2, zorder=1)
    all_routes.plot(ax=ax, color=CONTEXT, linewidth=0.35, zorder=2)

    tr = segs[segs["first_protected_year"].between(2013, 2024)].copy()
    cmap = LinearSegmentedColormap.from_list(
        "buildout", ["#9ecae1", "#4292c6", "#2171b5", "#08519c", "#08306b"])
    bounds = [2013, 2016, 2018, 2020, 2022, 2025]
    norm = BoundaryNorm(bounds, cmap.N)
    tr.plot(ax=ax, column="first_protected_year", cmap=cmap, norm=norm,
            linewidth=1.9, zorder=3)

    labels = ["2013-15", "2016-17", "2018-19", "2020-21", "2022-24"]
    handles = [Line2D([], [], color=cmap(norm(b + 0.5)), lw=3, label=lbl)
               for b, lbl in zip(bounds[:-1], labels, strict=True)]
    handles.append(Line2D([], [], color=CONTEXT, lw=1.2, label="other bike route"))
    ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=9,
              title="Protected lane installed", title_fontsize=9,
              alignment="left", bbox_to_anchor=(0.0, LEGEND_Y))

    _frame(ax, "Where New York built its protected bike lanes, 2013-2024",
           f"{len(tr):,} street segments across {tr['corridor_id'].nunique():,} corridors. "
           "Grey lines are the rest of the bike network.")
    _source(fig, "Source: NYC DOT Bike Routes (mzxg-pwib). Projection: NAD83 / New York Long Island (ft).")
    fig.subplots_adjust(top=0.90, bottom=0.03, left=0.02, right=0.98)
    fig.savefig(OUT / "map_buildout.png", dpi=170)
    log.info("wrote map_buildout.png")


def map_injuries(boros, all_routes, segs, log) -> None:
    """Cyclist injury rate by corridor."""
    fig, ax = plt.subplots(figsize=(9.5, 10))
    boros.plot(ax=ax, color=LAND, edgecolor=LAND_EDGE, linewidth=1.2, zorder=1)

    d = segs[segs["inj_per_seg_year"].notna()].copy()
    # Quantile bins: the distribution is heavily right-skewed, and equal-interval
    # bins would put 90% of corridors in the lowest class and say nothing.
    qs = d["inj_per_seg_year"].quantile([0.5, 0.75, 0.9, 0.97]).to_list()
    bounds = [0, *qs, d["inj_per_seg_year"].max()]
    cmap = LinearSegmentedColormap.from_list(
        "inj", ["#dfe3e8", "#fdd0a2", "#fd8d3c", "#e6550d", "#a63603"])
    norm = BoundaryNorm(bounds, cmap.N)
    widths = np.interp(d["inj_per_seg_year"], [bounds[0], bounds[-1]], [0.6, 3.0])
    d.plot(ax=ax, column="inj_per_seg_year", cmap=cmap, norm=norm,
           linewidth=widths, zorder=3)

    labels = ["below median", "50th-75th", "75th-90th", "90th-97th", "top 3%"]
    handles = [Line2D([], [], color=cmap(norm((bounds[i] + bounds[i+1]) / 2)),
                      lw=1 + i * 0.6, label=lbl) for i, lbl in enumerate(labels)]
    ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=9,
              title="Cyclist injuries per segment-year", title_fontsize=9,
              alignment="left", bbox_to_anchor=(0.0, LEGEND_Y))

    _frame(ax, "Where cyclists are hurt",
           "Corridor-level cyclist injuries per segment-year, 2013-2024, on the bike network. "
           "Quantile classes:\nthe distribution is heavily skewed, so equal intervals would "
           "put nearly everything in one class.")
    _source(fig, "Sources: NYPD Motor Vehicle Collisions (h9gi-nx95), NYC DOT Bike Routes (mzxg-pwib).")
    fig.subplots_adjust(top=0.90, bottom=0.03, left=0.02, right=0.98)
    fig.savefig(OUT / "map_injuries.png", dpi=170)
    log.info("wrote map_injuries.png")


def map_equity(boros, tracts, segs, log) -> None:
    """Protected lanes over tract income -- the equity finding, mapped."""
    fig, ax = plt.subplots(figsize=(9.5, 10))

    t = tracts[tracts["median_household_income"].notna()].copy()
    t.plot(ax=ax, column="median_household_income", cmap="Greens", scheme=None,
           linewidth=0, zorder=1, alpha=0.92,
           vmin=t["median_household_income"].quantile(0.02),
           vmax=t["median_household_income"].quantile(0.98))
    boros.plot(ax=ax, facecolor="none", edgecolor="#ffffff", linewidth=1.2, zorder=2)

    prot = segs[segs["treatment_cohort"].isin(["switcher", "always_treated"])]
    prot.plot(ax=ax, color="#7f2704", linewidth=1.6, zorder=4)

    sm = plt.cm.ScalarMappable(
        cmap="Greens",
        norm=plt.Normalize(vmin=t["median_household_income"].quantile(0.02),
                           vmax=t["median_household_income"].quantile(0.98)))
    cb = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.02, shrink=0.72)
    cb.set_label("Median household income (ACS 2018-2022)", fontsize=8.5)
    cb.ax.tick_params(labelsize=8)
    cb.ax.set_yticks(cb.get_ticks())
    cb.ax.set_yticklabels([f"${int(v/1000)}k" for v in cb.get_ticks()])

    ax.legend(handles=[Line2D([], [], color="#7f2704", lw=2.5, label="protected bike lane")],
              loc="upper left", frameon=False, fontsize=9,
              bbox_to_anchor=(0.0, LEGEND_Y))

    _frame(ax, "The protected network is concentrated in Manhattan and inner Brooklyn",
           "Darker tracts are higher income. Those same areas are the densest and most "
           "central, so a map cannot separate\nincome from centrality -- the per-resident and "
           "timing comparisons in the brief hold geography constant and still\nfind a gap. "
           "Note too that the poorest fifth of tracts is not the worst served; the middle "
           "fifth is.")
    _source(fig, "Sources: NYC DOT Bike Routes (mzxg-pwib), ACS 2018-2022 5-year estimates, TIGER 2022 tracts.")
    # Right margin has to clear the colorbar and its dollar labels; 0.98 clipped them.
    fig.subplots_adjust(top=0.88, bottom=0.03, left=0.02, right=0.88)
    fig.savefig(OUT / "map_equity.png", dpi=170)
    log.info("wrote map_equity.png")


def main() -> None:
    log = setup("maps")
    OUT.mkdir(exist_ok=True)
    boros, all_routes, segs, tracts = load_layers(log)
    map_buildout(boros, all_routes, segs, log)
    map_injuries(boros, all_routes, segs, log)
    map_equity(boros, tracts, segs, log)


if __name__ == "__main__":
    main()
