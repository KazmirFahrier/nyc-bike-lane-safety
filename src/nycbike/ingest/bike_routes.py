"""Pull the NYC Bike Routes layer -- the treatment variable.

This dataset needs more care than the others, and the care is the analysis.

**Geometry.** Socrata serves `the_geom` as a nested GeoJSON dict, which
parquet cannot hold. We convert to WKT on the way in and land both a parquet
(for dbt/DuckDB) and a GeoPackage (for PostGIS and QGIS).

**What counts as treated.** "Protected" in this file covers two physically
different things:

    onoffst = 'ON'   parking- or barrier-protected lane in the roadbed. This
                     is what DOT means by a protected bike lane, and it is
                     the treatment.
    onoffst = 'OFF'  greenway and park paths, also coded Protected. These are
                     not a street treatment at all -- they have their own
                     ridership population and no adjacent motor traffic.
                     Excluded from treatment, and excluded from the control
                     pool too, since they are not comparable streets.

Collapsing those two would attribute greenway safety to street redesign. The
split is 5,220 on-street vs 3,215 off-street Current segments, so this is not
a rounding decision.

**Install dates are not all real.** 1,500+ segments carry instdate values
before 1990 (1894, 1900, 1909...), which are inherited from the underlying
street centerline, not the date a bike facility was built. Anything installed
before the study window is treated as always-treated and dropped from the
DiD -- it can be neither a clean control nor a clean switcher. We report the
count rather than quietly filtering.

**Retired segments matter.** 434 on-street protected segments are Retired.
A corridor that gained a lane and later lost it is not "treated" for the
whole panel. `prevbikeid` chains versions; D6 reconstructs per-segment
treatment history from it rather than assuming the current snapshot held
for twelve years.

Usage:
    python -m nycbike.ingest.bike_routes
"""

from __future__ import annotations

import json

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape

from .. import config, socrata
from ..logging_setup import setup


def _to_geometry(val) -> object | None:
    """Socrata hands back a GeoJSON dict (or a JSON string). Both appear."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, str):
        try:
            val = json.loads(val)
        except json.JSONDecodeError:
            return None
    try:
        return shape(val)
    except (ValueError, AttributeError, TypeError):
        return None


def main() -> None:
    log = setup("ingest_bike_routes")

    df, receipt = socrata.fetch("bike_routes")
    log.info("pulled %s route segments", f"{len(df):,}")

    df["geometry"] = df["the_geom"].map(_to_geometry)
    n_bad = int(df["geometry"].isna().sum())
    if n_bad:
        log.warning("%s segments have unparseable geometry", n_bad)

    gdf = gpd.GeoDataFrame(
        df.drop(columns=["the_geom"]), geometry="geometry", crs=config.CRS_WGS84
    )

    gdf["instdate"] = pd.to_datetime(gdf["instdate"], errors="coerce")
    gdf["is_protected"] = (gdf.get("ft_facilit") == "Protected") | (
        gdf.get("tf_facilit") == "Protected"
    )
    gdf["is_onstreet"] = gdf["onoffst"] == "ON"
    # The treatment flag. Note this says nothing about *when* -- D6 builds the
    # per-segment, per-year treatment history including retirements.
    gdf["is_treated_facility"] = gdf["is_protected"] & gdf["is_onstreet"]

    # --- profile what we landed, into the log, for the data dictionary ---
    in_window = gdf["instdate"].between(config.STUDY_START, config.STUDY_END)
    pre_window = gdf["instdate"] < config.STUDY_START
    log.info("protected & on-street:            %s", f"{int(gdf['is_treated_facility'].sum()):,}")
    log.info("  installed in window (switchers): %s",
             f"{int((gdf['is_treated_facility'] & in_window).sum()):,}")
    log.info("  installed pre-2013 (always-tr.): %s",
             f"{int((gdf['is_treated_facility'] & pre_window).sum()):,}")
    log.info("  suspect instdate < 1990:         %s",
             f"{int((gdf['is_treated_facility'] & (gdf['instdate'].dt.year < 1990)).sum()):,}")
    log.info("  Retired status:                  %s",
             f"{int((gdf['is_treated_facility'] & (gdf['status'] == 'Retired')).sum()):,}")
    log.info("off-street protected (excluded):   %s",
             f"{int((gdf['is_protected'] & ~gdf['is_onstreet']).sum()):,}")

    gpkg = config.DATA_RAW / "bike_routes.gpkg"
    gdf.to_file(gpkg, layer="bike_routes", driver="GPKG")

    flat = gdf.copy()
    flat["geometry_wkt"] = flat.geometry.to_wkt()
    pq = config.DATA_RAW / "bike_routes.parquet"
    pd.DataFrame(flat.drop(columns=["geometry"])).to_parquet(pq, index=False)

    receipt.output_path = str(pq.relative_to(config.PROJECT_ROOT))
    receipt.write(config.DATA_RAW / "bike_routes.receipt.json")
    log.info("wrote %s and %s", pq.name, gpkg.name)


if __name__ == "__main__":
    main()
