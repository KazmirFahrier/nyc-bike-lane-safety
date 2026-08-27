"""Build corridors in PostGIS and verify they match the DuckDB implementation.

The verification is the point. A second implementation nobody checks is
decoration; a second implementation that is compared segment for segment
against the first is evidence that the corridor definition is well specified
rather than an artefact of one library's tolerances.

Requires the container from `make postgis-up`.

Usage:
    python scripts/run_postgis_corridors.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nycbike import config
from nycbike.logging_setup import setup

CONTAINER = "nycbike-postgis"
PSQL = ["docker", "exec", "-i", CONTAINER, "psql", "-U", "nycbike", "-d", "nycbike"]


def psql(args: list[str], stdin: str | None = None) -> str:
    r = subprocess.run(PSQL + args, input=stdin, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"psql failed: {r.stderr[:1000]}")
    return r.stdout


def main() -> None:
    log = setup("postgis_corridors")

    # --- export the same input the Python implementation used --------------
    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    segs = con.execute("""
        select t.segmentid, t.street, t.boro_code, t.first_protected_year,
               r.geometry_wkt
        from (select distinct segmentid, street, boro_code, first_protected_year,
                     is_offstreet_path
              from main.int_segment_treatment) t
        join (select segmentid, geometry_wkt,
                     row_number() over (partition by segmentid order by install_date desc) rn
              from main_staging.stg_bike_routes) r
          on r.segmentid = t.segmentid and r.rn = 1
        where not t.is_offstreet_path and r.geometry_wkt is not null
    """).df()
    con.close()
    log.info("segments to load: %s", f"{len(segs):,}")

    csv = config.DATA_INTERIM / "postgis_segments.csv"
    segs.to_csv(csv, index=False, header=False)

    log.info("creating schema")
    psql(["-v", "ON_ERROR_STOP=1", "-f", "-"], (ROOT / "sql/postgis/01_load.sql").read_text())

    log.info("loading segments")
    psql(["-v", "ON_ERROR_STOP=1", "-c",
          r"\copy bike_segments (segmentid, street, boro_code, first_protected_year, geom_wkt) "
          r"FROM STDIN WITH (FORMAT csv)"], csv.read_text())

    log.info("building corridors with ST_ClusterDBSCAN")
    psql(["-v", "ON_ERROR_STOP=1", "-f", "-"], (ROOT / "sql/postgis/02_corridors.sql").read_text())

    n_cor = int(psql(["-tAc", "select count(*) from corridors"]).strip())
    n_map = int(psql(["-tAc", "select count(*) from segment_corridor"]).strip())
    log.info("PostGIS: %s corridors, %s segment assignments", f"{n_cor:,}", f"{n_map:,}")

    # --- compare against the DuckDB/Python implementation ------------------
    pg = pd.read_csv(
        pd.io.common.StringIO(
            psql(["-tAc", "copy (select segmentid, corridor_pk from segment_corridor) to stdout with csv"])
        ),
        names=["segmentid", "pg_corridor"],
        dtype={"segmentid": str},
    )
    py = pd.read_parquet(config.DATA_INTERIM / "segment_corridors.parquet")[
        ["segmentid", "corridor_id"]
    ]
    py["segmentid"] = py["segmentid"].astype(str)

    both = py.merge(pg, on="segmentid", how="outer", indicator=True)
    only_py = int((both["_merge"] == "left_only").sum())
    only_pg = int((both["_merge"] == "right_only").sum())
    log.info("segments only in DuckDB build: %s", only_py)
    log.info("segments only in PostGIS build: %s", only_pg)

    # Corridor ids differ by construction; what must match is the *partition*:
    # any two segments grouped together by one implementation must be grouped
    # together by the other.
    m = both[both["_merge"] == "both"]
    ct = pd.crosstab(m["corridor_id"], m["pg_corridor"])
    py_split = int((ct.gt(0).sum(axis=1) > 1).sum())
    pg_split = int((ct.gt(0).sum(axis=0) > 1).sum())

    log.info("")
    log.info("=== PARTITION AGREEMENT ===")
    log.info("  segments compared:                       %s", f"{len(m):,}")
    log.info("  DuckDB corridors split across PostGIS:   %s", py_split)
    log.info("  PostGIS corridors split across DuckDB:   %s", pg_split)
    if py_split == 0 and pg_split == 0 and only_py == 0 and only_pg == 0:
        log.info("  IDENTICAL partition -- the two implementations agree exactly")
    else:
        log.info("  PARTITIONS DIFFER -- investigate before trusting either")
        d = ct.gt(0).sum(axis=1)
        log.info("  worst DuckDB corridor spans %s PostGIS runs", int(d.max()))


if __name__ == "__main__":
    main()
