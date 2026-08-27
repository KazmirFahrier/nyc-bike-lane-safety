"""Shared fixtures.

Tests here are deliberately hermetic: no network, no DuckDB file, no parquet.
Everything either builds a small synthetic frame or stubs the HTTP layer. The
expensive end-to-end check is scripts/clean_room.sh, which is a different kind
of test and does not belong in CI.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "analysis"))


@pytest.fixture
def two_cohort_panel() -> pd.DataFrame:
    """A tiny corridor panel with a known, hand-computable answer.

    Two treated corridors (cohort 2018) and two never-treated, 2015-2020.
    Controls sit flat at 1.0 injury per segment. Treated sit flat at 2.0
    before 2018 and 1.0 from 2018 on -- so the true ATT is exactly -1.0 in
    every post period, whichever base year is used.
    """
    rows = []
    for cid, treated in (("T1", True), ("T2", True), ("C1", False), ("C2", False)):
        for yr in range(2015, 2021):
            if treated:
                y = 2.0 if yr < 2018 else 1.0
            else:
                y = 1.0
            rows.append({
                "corridor_id": cid, "panel_year": yr, "boro_code": "1",
                "n_segments": 1, "cyclist_injured": y,
                "injuries_per_segment": y,
                "treatment_cohort": "switcher" if treated else "never_treated",
                "first_protected_year": 2018.0 if treated else None,
            })
    return pd.DataFrame(rows)


@pytest.fixture
def two_cohort_matched() -> pd.DataFrame:
    rows = []
    for cid, t in (("T1", True), ("T2", True), ("C1", False), ("C2", False)):
        rows.append({
            "cohort_year": 2018, "corridor_id": cid, "is_treated_here": t,
            "is_eligible_control": not t, "in_common_support": True,
            "cem_weight": 1.0, "boro_code": "1", "injury_bin": "1-2",
        })
    return pd.DataFrame(rows)
