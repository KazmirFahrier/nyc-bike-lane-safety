"""Pull ACS 5-Year tract demographics for the equity stratification.

**Requires a free Census API key.** The Census API began rejecting
unauthenticated requests; without a key every call returns a "Missing Key"
HTML page rather than JSON. Sign up (free, instant, no cost or approval):

    https://api.census.gov/data/key_signup.html

then put it in .env as CENSUS_API_KEY=...

**Vintage, and why one vintage.** Census tract boundaries were redrawn between
the 2010 and 2020 censuses, so a tract id does not mean the same polygon across
the study window. The equity analysis is deliberately cross-sectional -- it asks
"which neighborhoods got lanes", not "how did neighborhoods change" -- so it uses
a single ACS vintage on 2020-based tracts and does not attempt a tract-level
panel. Trying to chain 2010 and 2020 tracts through a crosswalk would add
apportionment error to answer a question this study is not asking.

**Variables** are chosen to support the DOHMH-style equity framing: who lives on
the corridors that got lanes, and does that differ from who lives on the ones
that did not.

Usage:
    python -m nycbike.ingest.acs [--year 2023]
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd
import requests

from .. import config
from ..logging_setup import setup

# NYC's five boroughs are five NY State counties.
NYC_COUNTIES = {
    "005": "Bronx",
    "047": "Brooklyn",
    "061": "Manhattan",
    "081": "Queens",
    "085": "Staten Island",
}
STATE_FIPS = "36"

VARIABLES = {
    "B01003_001E": "total_population",
    "B19013_001E": "median_household_income",
    "B17001_001E": "poverty_universe",
    "B17001_002E": "poverty_below",
    "B03002_001E": "race_universe",
    "B03002_003E": "white_nh",
    "B03002_004E": "black_nh",
    "B03002_006E": "asian_nh",
    "B03002_012E": "hispanic",
    "B08301_001E": "commute_total",
    "B08301_018E": "commute_bicycle",
    "B25044_001E": "vehicle_universe",
    "B25044_003E": "owner_no_vehicle",
    "B25044_010E": "renter_no_vehicle",
}


def _fetch_county(year: int, county: str, key: str) -> pd.DataFrame:
    url = f"https://api.census.gov/data/{year}/acs/acs5"
    params = {
        "get": "NAME," + ",".join(VARIABLES),
        "for": "tract:*",
        "in": f"state:{STATE_FIPS} county:{county}",
        "key": key,
    }
    resp = requests.get(url, params=params, timeout=120)
    resp.raise_for_status()
    if not resp.text.lstrip().startswith("["):
        raise RuntimeError(
            f"Census API did not return JSON for county {county}. "
            f"This almost always means a missing or invalid CENSUS_API_KEY. "
            f"First 200 chars: {resp.text[:200]!r}"
        )
    payload = resp.json()
    return pd.DataFrame(payload[1:], columns=payload[0])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, default=2023, help="ACS 5-year end year")
    args = ap.parse_args()
    log = setup("ingest_acs")

    if not config.CENSUS_API_KEY:
        log.error(
            "CENSUS_API_KEY is not set. Get a free key at "
            "https://api.census.gov/data/key_signup.html and add it to .env"
        )
        sys.exit(2)

    frames = []
    for fips, name in NYC_COUNTIES.items():
        df = _fetch_county(args.year, fips, config.CENSUS_API_KEY)
        df["borough"] = name
        log.info("%-14s %s tracts", name, len(df))
        frames.append(df)

    acs = pd.concat(frames, ignore_index=True).rename(columns=VARIABLES)

    # GEOID is the join key to TIGER tract geometry.
    acs["geoid"] = acs["state"] + acs["county"] + acs["tract"]

    numeric = list(VARIABLES.values())
    for c in numeric:
        acs[c] = pd.to_numeric(acs[c], errors="coerce")
        # Census uses large negative sentinels (-666666666) for suppressed or
        # non-applicable estimates. Left as NaN, never as a value.
        acs.loc[acs[c] < -1e8, c] = pd.NA

    acs["pct_below_poverty"] = 100 * acs["poverty_below"] / acs["poverty_universe"]
    acs["pct_bike_commute"] = 100 * acs["commute_bicycle"] / acs["commute_total"]
    acs["pct_white_nh"] = 100 * acs["white_nh"] / acs["race_universe"]
    acs["pct_no_vehicle"] = (
        100 * (acs["owner_no_vehicle"] + acs["renter_no_vehicle"]) / acs["vehicle_universe"]
    )
    acs["acs_vintage"] = f"{args.year - 4}-{args.year}"

    out = config.DATA_EXTERNAL / f"acs5_{args.year}_nyc_tracts.parquet"
    acs.to_parquet(out, index=False)
    log.info("wrote %s (%s tracts)", out.name, f"{len(acs):,}")
    log.info(
        "median household income suppressed in %s tracts",
        int(acs["median_household_income"].isna().sum()),
    )


if __name__ == "__main__":
    main()
