"""Attribute each cyclist crash to the street segment it happened on.

This is the step the whole panel rests on. If crashes land on the wrong
segments, every downstream estimate is noise dressed as a finding.

**Nearest segment, not every nearby segment.** At an intersection a crash
point sits within 100 ft of several centerlines. Joining to all of them would
count one crash four times and would systematically over-weight intersections,
which is precisely where cyclist crashes concentrate -- so the bias would not
wash out. Each crash is therefore assigned to its single nearest centerline
within the buffer, and the number of crashes that were ambiguous (2+ segments
within 100 ft) is reported as a QA figure rather than hidden.

**Coordinates are validated, not trusted.** 4,056 crash records carry a null
latitude and 217 carry exactly 0.0, which is the Gulf of Guinea rather than
Queens. Records outside the NYC bounding box are dropped and counted. The
geocoding rate runs 86.3% (2016) to 94.8% (2023); that variation is a
data-quality finding that belongs in the brief, and D9 re-runs the headline
estimate on the subset of years with the highest geocoding to check that the
2016 dip is not driving anything.

**Projection.** All distance work happens in EPSG:2263, NAD83 / New York Long
Island (US survey feet) -- the city's own projection. Buffering in degrees
would make a 100 ft buffer mean different distances at different latitudes.

Usage:
    python -m nycbike.spatial_join
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import wkt

from . import config
from .logging_setup import setup
from .street_names import normalize_series

# The five boroughs, generously bounded. Anything outside is a bad geocode.
NYC_BBOX = {"lat": (40.47, 40.93), "lon": (-74.30, -73.68)}

# Two centerlines whose distances differ by less than this are treated as tied.
# NYPD geocodes crashes onto the street centerline (median distance to the
# nearest line is 1.3 ft), so sub-foot differences carry no information about
# which street the crash was actually on -- they are floating-point noise.
TIE_TOLERANCE_FT = 1.0


def load_crashes() -> tuple[gpd.GeoDataFrame, dict[str, int]]:
    df = pd.read_parquet(config.DATA_RAW / "crashes_cyclist.parquet")
    n_total = len(df)

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    ok = df["latitude"].between(*NYC_BBOX["lat"]) & df["longitude"].between(*NYC_BBOX["lon"])

    stats = {
        "crashes_total": n_total,
        "null_coords": int(df["latitude"].isna().sum()),
        "zero_coords": int((df["latitude"] == 0).sum()),
        "outside_nyc_bbox": int((~ok).sum()),
        "geocoded_usable": int(ok.sum()),
    }

    gdf = gpd.GeoDataFrame(
        df[ok].copy(),
        geometry=gpd.points_from_xy(df.loc[ok, "longitude"], df.loc[ok, "latitude"]),
        crs=config.CRS_WGS84,
    ).to_crs(config.CRS_NYC)
    return gdf, stats


def load_segments() -> gpd.GeoDataFrame:
    df = pd.read_parquet(config.DATA_RAW / "bike_routes.parquet")
    df = df[df["geometry_wkt"].notna()].copy()
    gdf = gpd.GeoDataFrame(
        df, geometry=df["geometry_wkt"].map(wkt.loads), crs=config.CRS_WGS84
    ).to_crs(config.CRS_NYC)
    # One row per segment version. Keep the version key so treatment history
    # (install, retirement) can be reconstructed downstream from bikeid.
    return gdf.drop(columns=["geometry_wkt"])


def main() -> None:
    log = setup("spatial_join")
    buf = config.CORRIDOR_BUFFER_FT

    crashes, stats = load_crashes()
    log.info("crashes: %s total", f"{stats['crashes_total']:,}")
    log.info("  null coordinates:   %s", f"{stats['null_coords']:,}")
    log.info("  zero coordinates:   %s", f"{stats['zero_coords']:,}")
    log.info("  outside NYC bbox:   %s", f"{stats['outside_nyc_bbox']:,}")
    log.info("  usable (%.1f%%):     %s",
             100 * stats["geocoded_usable"] / stats["crashes_total"],
             f"{stats['geocoded_usable']:,}")

    segs = load_segments()
    log.info("segments: %s (CRS %s, distances in feet)", f"{len(segs):,}", segs.crs.to_string())

    # --- every (crash, segment) pair inside the buffer, with true distance ---
    pairs = gpd.sjoin(
        crashes[["collision_id", "geometry"]].assign(geometry=crashes.geometry.buffer(buf)),
        segs[["segmentid", "geometry"]],
        how="inner",
        predicate="intersects",
    )[["collision_id", "segmentid"]]

    pt = crashes.set_index("collision_id").geometry
    ln = segs.drop_duplicates("segmentid").set_index("segmentid").geometry
    pairs["d_ft"] = gpd.GeoSeries(
        pairs["collision_id"].map(pt).values, crs=segs.crs
    ).distance(gpd.GeoSeries(pairs["segmentid"].map(ln).values, crs=segs.crs))
    pairs = pairs.groupby(["collision_id", "segmentid"], as_index=False)["d_ft"].min()

    seg_attr = segs.drop_duplicates("segmentid").set_index("segmentid")
    pairs["seg_street_norm"] = normalize_series(pairs["segmentid"].map(seg_attr["street"]))
    pairs["seg_treated"] = pairs["segmentid"].map(seg_attr["is_treated_facility"])

    # --- the tie set: everything within TIE_TOLERANCE_FT of the winner -----
    pairs["d_min"] = pairs.groupby("collision_id")["d_ft"].transform("min")
    tied = pairs[pairs["d_ft"] <= pairs["d_min"] + TIE_TOLERANCE_FT].copy()

    n_matched = tied["collision_id"].nunique()
    k = tied.groupby("collision_id")["segmentid"].nunique()
    n_tied = int((k > 1).sum())
    log.info("crashes matching >=1 segment within %d ft: %s", buf, f"{n_matched:,}")
    log.info("  of those, tied within %.1f ft of the winner: %s (%.1f%%)",
             TIE_TOLERANCE_FT, f"{n_tied:,}", 100 * n_tied / max(n_matched, 1))
    log.info("  (LION segments meet end-to-end at intersections, so a crash "
             "geocoded to an intersection node is equidistant from every leg)")

    # --- tie-break 1: the street NYPD says the crash was on ----------------
    crash_street = normalize_series(
        crashes.set_index("collision_id")["on_street_name"]
    )
    tied["crash_street_norm"] = tied["collision_id"].map(crash_street)
    tied["name_match"] = (
        tied["crash_street_norm"].notna()
        & (tied["seg_street_norm"] == tied["crash_street_norm"])
    )
    has_name_match = tied.groupby("collision_id")["name_match"].transform("any")
    # Where the reported street identifies one of the tied segments, keep only
    # those. Where it identifies none, geometry is all we have.
    resolved = tied[(~has_name_match) | tied["name_match"]].copy()

    k2 = resolved.groupby("collision_id")["segmentid"].nunique()
    n_by_name = int((k[k > 1].index.isin(k2[k2 == 1].index)).sum())
    log.info("  resolved by reported street name: %s", f"{n_by_name:,}")

    # --- what remains: does the residual ambiguity change treatment? -------
    still = resolved[resolved["collision_id"].isin(k2[k2 > 1].index)]
    disagree = still.groupby("collision_id")["seg_treated"].nunique()
    contested = set(disagree[disagree > 1].index)
    log.info("  still tied but all tied segments AGREE on treatment (harmless): %s",
             f"{int((disagree == 1).sum()):,}")
    log.info("  still tied and tied segments DISAGREE on treatment (contested): %s (%.1f%% of matched)",
             f"{len(contested):,}", 100 * len(contested) / max(n_matched, 1))

    # --- final assignment --------------------------------------------------
    assigned = (
        resolved.sort_values(["collision_id", "d_ft", "segmentid"])
        .groupby("collision_id", as_index=False)
        .first()
    )
    assigned["assignment_contested"] = assigned["collision_id"].isin(contested)
    assigned["assignment_method"] = np.where(
        assigned["collision_id"].map(k) == 1, "unique",
        np.where(assigned["collision_id"].map(k2) == 1, "street_name", "nearest_arbitrary"),
    )
    log.info("assignment method: %s",
             assigned["assignment_method"].value_counts().to_dict())

    out = (
        crashes.drop(columns="geometry")
        .merge(
            assigned[["collision_id", "segmentid", "d_ft",
                      "assignment_contested", "assignment_method"]],
            on="collision_id", how="left",
        )
        .merge(
            seg_attr[["street", "ft_facilit", "tf_facilit", "facilitycl", "onoffst",
                      "status", "instdate", "bikeid", "prevbikeid", "is_protected",
                      "is_onstreet", "is_treated_facility"]],
            left_on="segmentid", right_index=True, how="left",
        )
    )
    n_off = int(out["segmentid"].isna().sum())
    log.info("off-panel (no bike facility on that street): %s", f"{n_off:,}")
    log.info("median distance to assigned centerline: %.2f ft", out["d_ft"].median())

    path = config.DATA_INTERIM / "crashes_segments.parquet"
    pd.DataFrame(out).to_parquet(path, index=False)

    qa = pd.DataFrame([{
        **stats,
        "buffer_ft": buf,
        "tie_tolerance_ft": TIE_TOLERANCE_FT,
        "crashes_matched": n_matched,
        "crashes_tied": n_tied,
        "resolved_by_street_name": n_by_name,
        "contested_treatment": len(contested),
        "off_panel": n_off,
    }])
    qa.to_parquet(config.DATA_INTERIM / "spatial_join_qa.parquet", index=False)
    log.info("wrote %s", path.name)


if __name__ == "__main__":
    main()
