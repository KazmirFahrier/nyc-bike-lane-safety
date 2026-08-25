"""Project-wide paths, constants, and the analysis window.

Every number that shapes the study lives here, not scattered through scripts.
If a reviewer asks "why 2013?", the answer should be one grep away.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

# --- Paths ---------------------------------------------------------------
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_INTERIM = PROJECT_ROOT / "data" / "interim"
DATA_EXTERNAL = PROJECT_ROOT / "data" / "external"
LOGS = PROJECT_ROOT / "logs"
DUCKDB_PATH = PROJECT_ROOT / "data" / "nycbike.duckdb"

for _d in (DATA_RAW, DATA_INTERIM, DATA_EXTERNAL, LOGS):
    _d.mkdir(parents=True, exist_ok=True)

# --- Credentials ---------------------------------------------------------
SOCRATA_APP_TOKEN = os.getenv("SOCRATA_APP_TOKEN") or None
CENSUS_API_KEY = os.getenv("CENSUS_API_KEY") or None

# --- Analysis window -----------------------------------------------------
# The crash table starts in July 2012. We take whole years only, so the panel
# is balanced and no year is a partial count. 2013 is the first complete year.
STUDY_START = "2013-01-01"
# Socrata crash data lags ~1-2 months and the most recent months are revised
# upward as reports are filed. We stop at the last complete calendar year to
# avoid a spurious downward trend at the right edge of every time series.
STUDY_END = "2024-12-31"

# --- Socrata dataset identifiers ----------------------------------------
# Verified live 2026-08-24. Row counts are as-of that date and are asserted
# loosely (>=) in the ingest reconciliation, since these are append-only.
DATASETS = {
    "crashes": "h9gi-nx95",           # Motor Vehicle Collisions - Crashes
    "persons": "f55k-p6yu",           # Motor Vehicle Collisions - Person
    "bike_routes": "mzxg-pwib",       # NYC Bike Routes (lane geometry + install year)
    "bike_counts": "uczf-rk3c",       # Bicycle Counts (automated counters, 15-min)
    "bike_counters": "smn3-rzf9",     # Bicycle Counters (counter locations, 41 sites)
    "bike_ped_counts": "ct66-47at",   # Bicycle and Pedestrian Counts
}
SOCRATA_DOMAIN = "data.cityofnewyork.us"

# --- Spatial -------------------------------------------------------------
# NAD83 / New York Long Island (ftUS). The city's own projection; distances
# come out in feet, which is what DOT uses for corridor buffers.
CRS_NYC = "EPSG:2263"
CRS_WGS84 = "EPSG:4326"
# Half-width of the corridor buffer used to attribute a crash to a street
# segment. 100 ft covers the roadbed plus both sidewalks on a typical NYC
# street; sensitivity to this choice is tested in the robustness grid (D9).
CORRIDOR_BUFFER_FT = 100
