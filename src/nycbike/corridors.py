"""Aggregate street segments into corridors.

Three separate problems all point at the same fix.

**Power.** 92.5% of segment-years carry zero cyclist injuries. Matching on
injury history at segment level is mostly matching zeros to zeros, and a
negative binomial fit on a 92.5%-zero outcome has very little to work with.

**The policy unit is wrong.** DOT does not install a protected lane on one
block. It installs on a corridor -- 1st Avenue from Houston to 34th. Estimating
a per-block effect answers a question nobody asked and that no agency can act on.

**Intersection assignment.** 92% of matched crashes sit within a foot of two
or more centerlines, and 13.4% of those ties disagree about treatment. Most of
that ambiguity is *within* a corridor: adjacent blocks of the same street with
the same lane. Aggregating makes it disappear rather than requiring it to be
adjudicated.

**Definition.** A corridor is a maximal run of segments that are contiguous,
on the same street, in the same borough, and share the same treatment history.
The treatment split is deliberate: where 1st Avenue got a lane on blocks 1-20
in 2019 and blocks 21-30 never did, those are two corridors, not one, because
they are two different interventions.

Contiguity is computed as connected components over an endpoint-adjacency
graph. Two segments are adjacent when an endpoint of one lies within
ENDPOINT_TOLERANCE_FT of an endpoint of the other -- LION centerlines are meant
to share endpoints exactly, but coordinate rounding leaves sub-foot gaps.

Usage:
    python -m nycbike.corridors
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from shapely import wkt

from . import config
from .logging_setup import setup

# LION centerlines nominally share endpoints exactly; coordinate rounding
# leaves gaps well under a foot. 10 ft is loose enough to close those without
# bridging genuinely separate stretches of a street.
ENDPOINT_TOLERANCE_FT = 10.0


def _endpoints(geom):
    """First and last coordinate of a (multi)linestring."""
    if geom is None or geom.is_empty:
        return None
    if geom.geom_type == "MultiLineString":
        parts = list(geom.geoms)
        coords = list(parts[0].coords) + list(parts[-1].coords)
    else:
        coords = list(geom.coords)
    return coords[0], coords[-1]


def build_corridors() -> gpd.GeoDataFrame:
    log = setup("corridors")

    routes = pd.read_parquet(config.DATA_RAW / "bike_routes.parquet")
    routes = routes[routes["geometry_wkt"].notna()].copy()

    # One geometry and one treatment history per segmentid.
    import duckdb

    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    treat = con.execute("""
        select distinct segmentid, street, boro_code, treatment_cohort,
               first_protected_year, is_offstreet_path
        from main.int_segment_treatment
    """).df()
    con.close()

    geom = (
        routes.sort_values("instdate")
        .drop_duplicates("segmentid", keep="last")[["segmentid", "geometry_wkt"]]
    )
    df = treat.merge(geom, on="segmentid", how="inner")
    df = df[~df["is_offstreet_path"]].copy()
    log.info("on-street segments to group: %s", f"{len(df):,}")

    gdf = gpd.GeoDataFrame(
        df, geometry=df["geometry_wkt"].map(wkt.loads), crs=config.CRS_WGS84
    ).to_crs(config.CRS_NYC)

    # Treatment history is part of the grouping key: two stretches of the same
    # street treated in different years are different interventions.
    gdf["group_key"] = (
        gdf["street"].fillna("(unnamed)")
        + "|" + gdf["boro_code"].fillna("?")
        + "|" + gdf["first_protected_year"].fillna(-1).astype(int).astype(str)
    )

    corridor_ids = np.empty(len(gdf), dtype=object)
    n_groups = 0
    for key, idx in gdf.groupby("group_key").groups.items():
        sub = gdf.loc[idx]
        n = len(sub)
        if n == 1:
            corridor_ids[gdf.index.get_indexer(idx)] = [f"{key}|0"]
            n_groups += 1
            continue

        ends = sub.geometry.map(_endpoints)
        pts = np.array([p for e in ends for p in (e if e else ((np.nan, np.nan),) * 2)])
        owner = np.repeat(np.arange(n), 2)

        # Endpoint pairs closer than the tolerance make their segments adjacent.
        tree = gpd.GeoSeries(gpd.points_from_xy(pts[:, 0], pts[:, 1]), crs=sub.crs)
        near = tree.sindex.query(
            tree.buffer(ENDPOINT_TOLERANCE_FT), predicate="intersects"
        )
        a, b = owner[near[0]], owner[near[1]]
        keep = a != b
        adj = coo_matrix(
            (np.ones(keep.sum()), (a[keep], b[keep])), shape=(n, n)
        )
        _, labels = connected_components(adj, directed=False)
        corridor_ids[gdf.index.get_indexer(idx)] = [f"{key}|{lb}" for lb in labels]
        n_groups += 1

    gdf["corridor_id"] = corridor_ids
    log.info("street x borough x treatment groups: %s", f"{n_groups:,}")
    log.info("corridors formed: %s", f"{gdf['corridor_id'].nunique():,}")

    sizes = gdf.groupby("corridor_id").size()
    log.info("segments per corridor: median %.0f, mean %.1f, max %d",
             sizes.median(), sizes.mean(), sizes.max())
    log.info("single-segment corridors: %s (%.1f%%)",
             f"{int((sizes == 1).sum()):,}", 100 * (sizes == 1).mean())

    out = gdf[["segmentid", "corridor_id", "street", "boro_code",
               "treatment_cohort", "first_protected_year"]].copy()
    path = config.DATA_INTERIM / "segment_corridors.parquet"
    out.to_parquet(path, index=False)
    log.info("wrote %s", path.name)
    return gdf


if __name__ == "__main__":
    build_corridors()
