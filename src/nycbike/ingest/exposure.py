"""Pull ridership exposure from DOT's automated bicycle counters.

Exposure is the whole reason this study exists. Cyclist injuries on a corridor
can rise because the corridor got more dangerous or because more people are
riding on it. Only the first is a policy failure. Without a ridership
denominator the headline number is uninterpretable.

**Pulled as daily aggregates, not raw readings.** The counter feed is 6.2M
15-minute readings in the study window. We aggregate server-side to
site x day x status and reconcile against control totals computed over the
ungrouped data: the summed daily counts must equal `sum(counts)` over the raw
feed exactly, and the interval tally must equal `count(*)`. Same answer, 3% of
the bytes, and the control totals prove it is the same answer.

**Two data-quality traps, both preserved rather than cleaned away:**

  status=4 covers 1.30M of 7.38M readings (17.6%). It is not documented in the
  data dictionary as of this writing. We keep status as a grouping key so the
  downstream model can include or exclude it and the robustness grid can test
  whether the choice matters, rather than baking one guess into the raw layer.

  A dead counter reports 0, and 0 is also a legitimate count at 4am in
  February. A site reporting exactly zero across all 96 intervals of a day is
  almost certainly offline, not deserted. We land `intervals` and
  `nonzero_intervals` per site-day so the staging layer can tell the two apart.
  Treating counter outages as zero ridership would inflate every per-rider
  injury rate computed from them.

**The honest limit:** 41 counter sites. This cannot measure ridership on 4,357
treated segments. It supports a citywide and borough ridership index, which is
what the exposure offset uses. Segment-level exposure is modelled, not
measured, and D9 reports how far the headline estimate moves without any
exposure adjustment at all.

Usage:
    python -m nycbike.ingest.exposure
"""

from __future__ import annotations

import pandas as pd

from .. import config, socrata
from ..logging_setup import setup

WINDOW = (
    f"date >= '{config.STUDY_START}T00:00:00' AND date < '2025-01-01T00:00:00'"
)


def main() -> None:
    log = setup("ingest_exposure")

    # --- counter site locations (41 rows) --------------------------------
    sites, sites_receipt = socrata.fetch("bike_counters")
    sites.to_parquet(config.DATA_RAW / "bike_counters.parquet", index=False)
    sites_receipt.output_path = "data/raw/bike_counters.parquet"
    sites_receipt.write(config.DATA_RAW / "bike_counters.receipt.json")
    log.info("counter sites: %s", len(sites))

    # --- daily counts per site per status --------------------------------
    df, receipt = socrata.fetch_aggregate(
        "bike_counts",
        select=(
            "id, date_trunc_ymd(date) AS day, status, "
            "sum(counts) AS daily_counts, "
            "count(*) AS intervals, "
            "sum(case(counts > 0, 1, true, 0)) AS nonzero_intervals"
        ),
        group="id, day, status",
        order="day, id, status",
        where=WINDOW,
        control_totals={"daily_counts": "sum(counts)", "intervals": "count(*)"},
    )

    df["day"] = pd.to_datetime(df["day"])
    for c in ("daily_counts", "intervals", "nonzero_intervals"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")

    out = config.DATA_RAW / "bike_counts_daily.parquet"
    df.to_parquet(out, index=False)
    receipt.output_path = str(out.relative_to(config.PROJECT_ROOT))
    receipt.write(config.DATA_RAW / "bike_counts_daily.receipt.json")

    # --- profile, for the data dictionary --------------------------------
    log.info("site-day-status rows: %s", f"{len(df):,}")
    log.info("date span: %s to %s", df["day"].min().date(), df["day"].max().date())
    log.info("distinct sites reporting: %s", df["id"].nunique())
    by_status = df.groupby("status")["daily_counts"].sum()
    for st, tot in by_status.items():
        log.info("  status=%s: %s counted bike passages", st, f"{int(tot):,}")

    # How much of the panel is a counter that was almost certainly offline?
    full = df.groupby(["id", "day"], as_index=False).agg(
        counts=("daily_counts", "sum"),
        intervals=("intervals", "sum"),
        nonzero=("nonzero_intervals", "sum"),
    )
    dead = full[(full["nonzero"] == 0) & (full["intervals"] >= 96)]
    log.info(
        "site-days with 96+ intervals and zero non-zero readings (likely offline): "
        "%s of %s (%.1f%%)",
        f"{len(dead):,}", f"{len(full):,}", 100 * len(dead) / max(len(full), 1),
    )
    log.info("wrote %s", out.name)


if __name__ == "__main__":
    main()
