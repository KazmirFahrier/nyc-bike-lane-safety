"""Pull tract-level ACS demographics for New York City -- without an API key.

The obvious route, api.census.gov, now redirects every keyless request to
`missing_key.html`; the old allowance for a few hundred unauthenticated queries
a day is gone. That is a reason to use a different public route, not a reason to
stop: the ACS Summary Files sit on the Census FTP server, need no key, no
account and no registration, and carry exactly the same estimates.

Each table is one pipe-delimited file covering every geography in the country,
so they are large (b17001 is 114 MB). They are streamed and filtered to New
York City's five counties on the way in rather than landed whole.

GEO_IDs are summary-level prefixed. Census tracts are level 140, so a NYC tract
looks like `1400000US36061000100` -- state 36, county 061, tract 000100.

Tables:
    B19013  median household income
    B03002  race and Hispanic origin (the table that separates Hispanic origin
            from race properly, rather than B02001 which does not)
    B17001  poverty status

Usage:
    python -m nycbike.ingest.acs
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

from .. import config
from ..logging_setup import setup

ACS_YEAR = 2022  # 2018-2022 5-year estimates: the vintage centered on the study window
SF_BASE = (
    f"https://www2.census.gov/programs-surveys/acs/summary_file/{ACS_YEAR}"
    f"/table-based-SF/data/5YRData"
)
TIGER = f"https://www2.census.gov/geo/tiger/TIGER{ACS_YEAR}/TRACT/tl_{ACS_YEAR}_36_tract.zip"

# State 36, the five counties that make up New York City.
NYC_COUNTIES = {"005": "Bronx", "047": "Brooklyn", "061": "Manhattan",
                "081": "Queens", "085": "Staten Island"}
TRACT_PREFIX = "1400000US36"

# Columns wanted from each table, and what they mean.
WANTED = {
    "b19013": {"B19013_E001": "median_household_income"},
    "b03002": {
        "B03002_E001": "pop_total",
        "B03002_E003": "pop_white_nh",
        "B03002_E004": "pop_black_nh",
        "B03002_E006": "pop_asian_nh",
        "B03002_E012": "pop_hispanic",
    },
    "b17001": {
        "B17001_E001": "poverty_universe",
        "B17001_E002": "pop_below_poverty",
    },
}


def _download(url: str, dest: Path, log) -> Path:
    """Fetch to disk once and reuse. These files total ~210 MB."""
    if dest.exists() and dest.stat().st_size > 0:
        log.info("  cached: %s (%.1f MB)", dest.name, dest.stat().st_size / 1048576)
        return dest
    log.info("  downloading %s", url.rsplit("/", 1)[-1])
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for block in r.iter_content(chunk_size=1 << 20):
                fh.write(block)
    log.info("  wrote %s (%.1f MB)", dest.name, dest.stat().st_size / 1048576)
    return dest


def _read_table(table: str, log) -> pd.DataFrame:
    """Load one ACS table, keeping only NYC tracts and the wanted columns.

    Read from a cached local copy rather than straight off the socket: pandas'
    chunked reader outlives the requests context manager, and reading through
    `r.raw` fails with "I/O operation on closed file" once the connection is
    released. Caching also means a re-run does not re-fetch 210 MB.
    """
    url = f"{SF_BASE}/acsdt5y{ACS_YEAR}-{table}.dat"
    path = _download(url, config.DATA_EXTERNAL / f"acsdt5y{ACS_YEAR}-{table}.dat", log)

    keep_cols = WANTED[table]
    chunks: list[pd.DataFrame] = []
    total_rows = 0
    for chunk in pd.read_csv(
        path, sep="|", dtype=str, chunksize=200_000,
        usecols=lambda c: c == "GEO_ID" or c in keep_cols,
    ):
        total_rows += len(chunk)
        hit = chunk[
            chunk["GEO_ID"].str.startswith(TRACT_PREFIX, na=False)
            & chunk["GEO_ID"].str[len(TRACT_PREFIX):len(TRACT_PREFIX) + 3].isin(NYC_COUNTIES)
        ]
        if len(hit):
            chunks.append(hit)

    df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
    log.info("  %s: scanned %s rows, kept %s NYC tracts",
             table, f"{total_rows:,}", f"{len(df):,}")
    return df.rename(columns=keep_cols)


def main() -> None:
    log = setup("ingest_acs")
    log.info("ACS %s 5-year estimates, via the Census FTP summary files (no API key)", ACS_YEAR)

    frames = [_read_table(t, log) for t in WANTED]
    acs = frames[0]
    for f in frames[1:]:
        acs = acs.merge(f, on="GEO_ID", how="outer")

    # ACS uses large negative sentinels for suppressed / not-applicable values.
    num_cols = [c for c in acs.columns if c != "GEO_ID"]
    for c in num_cols:
        acs[c] = pd.to_numeric(acs[c], errors="coerce")
        acs.loc[acs[c] < -100000, c] = pd.NA

    acs["geoid"] = acs["GEO_ID"].str.removeprefix("1400000US")
    acs["county_fips"] = acs["geoid"].str[2:5]
    acs["borough"] = acs["county_fips"].map(NYC_COUNTIES)

    # Derived shares. Guarded against zero-population tracts (parks, cemeteries,
    # the airports) which would otherwise divide by zero and produce inf.
    tot = acs["pop_total"].where(acs["pop_total"] > 0)
    acs["share_white_nh"] = acs["pop_white_nh"] / tot
    acs["share_black_nh"] = acs["pop_black_nh"] / tot
    acs["share_hispanic"] = acs["pop_hispanic"] / tot
    acs["share_asian_nh"] = acs["pop_asian_nh"] / tot
    acs["share_poc"] = 1 - acs["share_white_nh"]
    pu = acs["poverty_universe"].where(acs["poverty_universe"] > 0)
    acs["poverty_rate"] = acs["pop_below_poverty"] / pu

    log.info("")
    log.info("tracts by borough:")
    for b, n in acs["borough"].value_counts().items():
        log.info("  %-14s %s", b, n)
    log.info("")
    log.info("median household income: median %s, %s tracts suppressed",
             f"${acs['median_household_income'].median():,.0f}",
             int(acs["median_household_income"].isna().sum()))
    log.info("zero-population tracts (parks, airports, cemeteries): %s",
             int((acs["pop_total"] == 0).sum()))

    # --- geometry -------------------------------------------------------
    log.info("")
    log.info("TIGER tract geometry")
    zpath = _download(TIGER, config.DATA_EXTERNAL / f"tl_{ACS_YEAR}_36_tract.zip", log)
    gdf = gpd.read_file(zpath)  # pyogrio reads the zipped shapefile directly
    gdf = gdf[gdf["COUNTYFP"].isin(NYC_COUNTIES)].copy()
    gdf["geoid"] = gdf["GEOID"]
    log.info("  tract polygons for NYC: %s", f"{len(gdf):,}")

    merged = gdf[["geoid", "ALAND", "geometry"]].merge(acs, on="geoid", how="left")
    unmatched = int(merged["pop_total"].isna().sum())
    if unmatched:
        log.warning("  %s tract polygons have no ACS row", unmatched)

    out_gpkg = config.DATA_EXTERNAL / "acs_tracts.gpkg"
    merged.to_file(out_gpkg, layer="tracts", driver="GPKG")

    flat = merged.drop(columns=["geometry"])
    flat.to_parquet(config.DATA_EXTERNAL / "acs_tracts.parquet", index=False)
    log.info("wrote acs_tracts.gpkg and acs_tracts.parquet (%s tracts)", f"{len(merged):,}")


if __name__ == "__main__":
    main()
