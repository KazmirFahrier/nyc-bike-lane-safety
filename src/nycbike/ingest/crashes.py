"""Pull NYPD Motor Vehicle Collisions.

Two pulls, both reconciled:

  crashes_cyclist -- every crash in the study window in which at least one
      cyclist was injured or killed. This is the outcome variable.

  crashes_all -- every crash in the window, pulled only when --all-crashes is
      passed. Used for the placebo/control outcome in D9: if protected lanes
      really cut cyclist injuries, motorist injuries on the same corridors
      should NOT move in lockstep. If they do, we are measuring general
      traffic calming (or a reporting change), not the lane.

Deliberately NOT filtered on latitude/longitude here. A meaningful share of
NYPD crash records are ungeocoded, and that share changes over time. Dropping
them silently at ingest would hide a data-quality problem that belongs in the
brief; we land everything and quantify the loss in dbt instead.

Usage:
    python -m nycbike.ingest.crashes
    python -m nycbike.ingest.crashes --all-crashes
"""

from __future__ import annotations

import argparse

from .. import config, socrata
from ..logging_setup import setup

WINDOW = (
    f"crash_date >= '{config.STUDY_START}T00:00:00' "
    f"AND crash_date < '2025-01-01T00:00:00'"
)
CYCLIST = "(number_of_cyclist_injured > 0 OR number_of_cyclist_killed > 0)"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--all-crashes",
        action="store_true",
        help="also pull all ~2.0M crashes in the window (slow; needed for the placebo test)",
    )
    args = ap.parse_args()
    log = setup("ingest_crashes")

    log.info("study window: %s to %s", config.STUDY_START, config.STUDY_END)
    if not config.SOCRATA_APP_TOKEN:
        log.warning("no SOCRATA_APP_TOKEN set -- requests will be throttled. See .env.example")

    r = socrata.fetch_to_parquet("crashes", where=f"{WINDOW} AND {CYCLIST}")
    # Land under a clearer name than the dataset key.
    (config.DATA_RAW / "crashes.parquet").rename(config.DATA_RAW / "crashes_cyclist.parquet")
    (config.DATA_RAW / "crashes.receipt.json").rename(
        config.DATA_RAW / "crashes_cyclist.receipt.json"
    )
    log.info("crashes_cyclist: %s rows in %.1fs", f"{r.rows_landed:,}", r.elapsed_sec)

    if args.all_crashes:
        log.info("pulling all crashes in window -- this takes a few minutes")
        r2 = socrata.fetch_to_parquet("crashes", where=WINDOW)
        (config.DATA_RAW / "crashes.parquet").rename(config.DATA_RAW / "crashes_all.parquet")
        (config.DATA_RAW / "crashes.receipt.json").rename(
            config.DATA_RAW / "crashes_all.receipt.json"
        )
        log.info("crashes_all: %s rows in %.1fs", f"{r2.rows_landed:,}", r2.elapsed_sec)


if __name__ == "__main__":
    main()
