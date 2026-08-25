"""A small, honest Socrata (SoDA 2.1) client.

Two things here are not optional and are the reason this file exists rather
than a one-line `pd.read_json`:

1. **Stable paging.** Socrata's default row order is undefined. Paging with
   `$limit`/`$offset` against an undefined order will silently skip and
   duplicate rows on a multi-hundred-thousand-row pull. Every request here
   pins `$order=:id`, the internal row identifier, which is stable and unique.

2. **Row-count reconciliation.** Before pulling, we ask the API how many rows
   match the filter. After pulling, we compare. A pull that lands a different
   number of rows than the server promised is a failed pull, not a warning --
   it raises. Silent under-collection is the single most common way an
   analysis ends up quietly wrong.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from . import config

log = logging.getLogger(__name__)

PAGE_SIZE = 50_000
TIMEOUT = 120


class SocrataError(RuntimeError):
    """Raised when the API misbehaves or a pull fails reconciliation."""


@dataclass
class PullReceipt:
    """The audit record for one dataset pull.

    Written next to the data as JSON. This is what makes the clean-room
    reproduction on D15 checkable: same filter, same expected count, or the
    upstream data changed and we can say exactly how much.
    """

    dataset_id: str
    dataset_name: str
    where: str | None
    select: str | None
    server_count: int
    rows_landed: int
    pages: int
    started_utc: str
    finished_utc: str
    elapsed_sec: float
    output_path: str

    def write(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2) + "\n")


def _headers() -> dict[str, str]:
    h = {"Accept": "application/json", "User-Agent": "nyc-bike-lane-safety/0.1"}
    if config.SOCRATA_APP_TOKEN:
        h["X-App-Token"] = config.SOCRATA_APP_TOKEN
    return h


@retry(
    retry=retry_if_exception_type((requests.RequestException, SocrataError)),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
def _get(url: str, params: dict) -> list[dict]:
    resp = requests.get(url, params=params, headers=_headers(), timeout=TIMEOUT)
    if resp.status_code == 429:
        # Throttled. Without an app token this happens constantly; with one it
        # is rare. Back off and let tenacity retry.
        raise SocrataError("429 rate limited")
    if resp.status_code >= 500:
        raise SocrataError(f"{resp.status_code} server error: {resp.text[:200]}")
    if not resp.ok:
        # 4xx other than 429 means our query is wrong. Retrying will not help.
        raise SocrataError(f"{resp.status_code}: {resp.text[:500]}") from None
    return resp.json()


def _resource_url(dataset_id: str) -> str:
    return f"https://{config.SOCRATA_DOMAIN}/resource/{dataset_id}.json"


def count_rows(dataset_id: str, where: str | None = None) -> int:
    """Ask the server how many rows match `where`. This is the reconciliation target."""
    params: dict[str, str] = {"$select": "count(*) AS n"}
    if where:
        params["$where"] = where
    payload = _get(_resource_url(dataset_id), params)
    if not payload:
        return 0
    # Socrata returns the alias, but has historically also returned "count".
    row = payload[0]
    for key in ("n", "count", "count_1"):
        if key in row:
            return int(row[key])
    raise SocrataError(f"unexpected count payload: {row!r}")


def fetch(
    dataset_name: str,
    where: str | None = None,
    select: str | None = None,
    page_size: int = PAGE_SIZE,
) -> tuple[pd.DataFrame, PullReceipt]:
    """Pull a full filtered dataset, reconciled against the server's own count.

    Returns the frame and a receipt. Raises SocrataError if the row count
    landed does not match what the server said to expect.
    """
    dataset_id = config.DATASETS[dataset_name]
    url = _resource_url(dataset_id)
    started = datetime.now(timezone.utc)
    t0 = time.monotonic()

    expected = count_rows(dataset_id, where)
    log.info("%s (%s): server reports %s matching rows", dataset_name, dataset_id, f"{expected:,}")

    frames: list[pd.DataFrame] = []
    offset = 0
    pages = 0
    while offset < expected:
        params: dict[str, str | int] = {
            "$limit": page_size,
            "$offset": offset,
            "$order": ":id",  # stable paging -- see module docstring
        }
        if where:
            params["$where"] = where
        if select:
            params["$select"] = select
        batch = _get(url, params)
        if not batch:
            break
        frames.append(pd.DataFrame(batch))
        pages += 1
        offset += len(batch)
        log.info("  %s: %s / %s rows", dataset_name, f"{offset:,}", f"{expected:,}")

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    finished = datetime.now(timezone.utc)

    if len(df) != expected:
        raise SocrataError(
            f"{dataset_name}: reconciliation failed -- server promised {expected:,} rows, "
            f"landed {len(df):,}. Refusing to write a short pull."
        )

    receipt = PullReceipt(
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        where=where,
        select=select,
        server_count=expected,
        rows_landed=len(df),
        pages=pages,
        started_utc=started.isoformat(),
        finished_utc=finished.isoformat(),
        elapsed_sec=round(time.monotonic() - t0, 1),
        output_path="",
    )
    return df, receipt


def fetch_to_parquet(
    dataset_name: str,
    where: str | None = None,
    select: str | None = None,
    out_dir: Path | None = None,
) -> PullReceipt:
    """Pull, reconcile, and land as parquet with a receipt beside it."""
    out_dir = out_dir or config.DATA_RAW
    df, receipt = fetch(dataset_name, where=where, select=select)
    out_path = out_dir / f"{dataset_name}.parquet"
    # Socrata returns everything as strings; keep it that way on disk and cast
    # in dbt, so the raw layer is a faithful copy of what the API served.
    df.to_parquet(out_path, index=False)
    receipt.output_path = str(out_path.relative_to(config.PROJECT_ROOT))
    receipt.write(out_dir / f"{dataset_name}.receipt.json")
    log.info("wrote %s (%s rows)", out_path.name, f"{len(df):,}")
    return receipt


def fetch_aggregate(
    dataset_name: str,
    select: str,
    group: str,
    order: str,
    where: str | None = None,
    control_totals: dict[str, str] | None = None,
    page_size: int = PAGE_SIZE,
) -> tuple[pd.DataFrame, PullReceipt]:
    """Pull a server-side aggregation, reconciled by control totals.

    Aggregates cannot use the `$order=:id` trick (there is no row id) and there
    is no cheap way to ask how many groups a GROUP BY will produce. So the
    reconciliation is different, and stronger: the caller supplies control
    totals computed over the *ungrouped* data, and we assert the aggregated
    result reproduces them.

    Pulling 6.2M 15-minute counter readings to sum them locally would be the
    obvious alternative. This is the same answer for 3% of the bytes, and the
    control totals prove it is the same answer.

    Args:
        select: SoQL $select for the aggregate, e.g.
            "id, date_trunc_ymd(date) AS day, sum(counts) AS daily_counts"
        group: SoQL $group, e.g. "id, day"
        order: a deterministic ordering over the group keys. Must be unique
            per group or offset paging will skip rows.
        control_totals: maps a column in the aggregated frame to a SoQL
            aggregate over the ungrouped data, e.g.
            {"daily_counts": "sum(counts)"}. Each is checked exactly.
    """
    dataset_id = config.DATASETS[dataset_name]
    url = _resource_url(dataset_id)
    started = datetime.now(timezone.utc)
    t0 = time.monotonic()

    expected: dict[str, int] = {}
    for col, expr in (control_totals or {}).items():
        params: dict[str, str] = {"$select": f"{expr} AS v"}
        if where:
            params["$where"] = where
        payload = _get(url, params)
        expected[col] = int(float(payload[0]["v"])) if payload and payload[0].get("v") else 0
        log.info("%s: control total %s = %s", dataset_name, expr, f"{expected[col]:,}")

    frames: list[pd.DataFrame] = []
    offset = 0
    pages = 0
    while True:
        params = {
            "$select": select,
            "$group": group,
            "$order": order,
            "$limit": page_size,
            "$offset": offset,
        }
        if where:
            params["$where"] = where
        batch = _get(url, params)
        if not batch:
            break
        frames.append(pd.DataFrame(batch))
        pages += 1
        offset += len(batch)
        log.info("  %s: %s aggregated rows", dataset_name, f"{offset:,}")
        if len(batch) < page_size:
            break

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    for col, want in expected.items():
        if col not in df.columns:
            raise SocrataError(f"control total column {col!r} not in aggregated result")
        got = int(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())
        if got != want:
            raise SocrataError(
                f"{dataset_name}: control total mismatch on {col} -- "
                f"ungrouped data totals {want:,}, aggregation totals {got:,} "
                f"(difference {got - want:+,}). The aggregation lost or duplicated rows."
            )
        log.info("%s: control total %s reconciled (%s)", dataset_name, col, f"{got:,}")

    receipt = PullReceipt(
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        where=where,
        select=f"{select} GROUP BY {group}",
        server_count=max(expected.values()) if expected else len(df),
        rows_landed=len(df),
        pages=pages,
        started_utc=started.isoformat(),
        finished_utc=datetime.now(timezone.utc).isoformat(),
        elapsed_sec=round(time.monotonic() - t0, 1),
        output_path="",
    )
    return df, receipt
