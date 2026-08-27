"""The reconciliation contract: a short pull must fail loudly, never silently."""

from __future__ import annotations

import json

import pytest

from nycbike import socrata


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.ok = 200 <= status < 300
        self.text = json.dumps(payload) if isinstance(payload, (list, dict)) else str(payload)

    def json(self):
        return self._payload


def test_count_rows_reads_the_aliased_count(monkeypatch):
    monkeypatch.setattr(socrata, "_get", lambda url, params: [{"n": "1234"}])
    assert socrata.count_rows("abcd-efgh") == 1234


def test_count_rows_tolerates_the_unaliased_column(monkeypatch):
    # Socrata has historically returned "count" rather than the requested alias.
    monkeypatch.setattr(socrata, "_get", lambda url, params: [{"count": "77"}])
    assert socrata.count_rows("abcd-efgh") == 77


def test_count_rows_rejects_an_unexpected_payload(monkeypatch):
    monkeypatch.setattr(socrata, "_get", lambda url, params: [{"surprise": "1"}])
    with pytest.raises(socrata.SocrataError, match="unexpected count payload"):
        socrata.count_rows("abcd-efgh")


def test_fetch_raises_when_fewer_rows_land_than_promised(monkeypatch):
    """The single most important behaviour in the ingest layer.

    Silent under-collection is how an analysis ends up quietly wrong, so a pull
    that does not reconcile must raise rather than write a short file.
    """
    monkeypatch.setattr(socrata, "count_rows", lambda ds, where=None: 100)
    # Server promises 100 but hands back 10 and then stops.
    monkeypatch.setattr(socrata, "_get",
                        lambda url, params: [{"id": str(i)} for i in range(10)] if not params.get("$offset") else [])
    with pytest.raises(socrata.SocrataError, match="reconciliation failed"):
        socrata.fetch("crashes")


def test_fetch_succeeds_when_counts_agree(monkeypatch):
    monkeypatch.setattr(socrata, "count_rows", lambda ds, where=None: 3)
    monkeypatch.setattr(socrata, "_get",
                        lambda url, params: [] if params.get("$offset") else [{"id": "1"}, {"id": "2"}, {"id": "3"}])
    df, receipt = socrata.fetch("crashes")
    assert len(df) == 3
    assert receipt.server_count == receipt.rows_landed == 3


def test_paging_pins_a_stable_order(monkeypatch):
    """Offset paging against Socrata's undefined default order skips and
    duplicates rows. Every request must pin $order=:id."""
    seen = []
    monkeypatch.setattr(socrata, "count_rows", lambda ds, where=None: 1)

    def _spy(url, params):
        seen.append(params)
        return [{"id": "1"}] if not params.get("$offset") else []

    monkeypatch.setattr(socrata, "_get", _spy)
    socrata.fetch("crashes")
    assert seen, "no request was made"
    assert all(p.get("$order") == ":id" for p in seen)


def test_receipt_round_trips_through_json(tmp_path):
    r = socrata.PullReceipt(
        dataset_id="h9gi-nx95", dataset_name="crashes", where="x > 1", select=None,
        server_count=5, rows_landed=5, pages=1, started_utc="a", finished_utc="b",
        elapsed_sec=1.0, output_path="p.parquet",
    )
    p = tmp_path / "r.json"
    r.write(p)
    back = json.loads(p.read_text())
    assert back["server_count"] == back["rows_landed"] == 5
    assert back["dataset_id"] == "h9gi-nx95"


def test_aggregate_receipt_records_control_totals_not_a_row_count():
    """Aggregate pulls have no cheap group count. Conflating the two made a
    receipt read as though 159M rows had gone missing."""
    r = socrata.PullReceipt(
        dataset_id="uczf-rk3c", dataset_name="bike_counts", where=None, select="sum(counts)",
        server_count=None, rows_landed=65_162, pages=1, started_utc="a", finished_utc="b",
        elapsed_sec=1.0, output_path="p.parquet",
        control_totals={"daily_counts": 159_183_214},
    )
    assert r.server_count is None
    assert r.control_totals["daily_counts"] == 159_183_214
