"""Length-weighted attribution of tract characteristics to corridors."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from equity import wavg


def test_weights_by_length_not_by_tract_count():
    """The methodological choice the function exists to make. A corridor with
    900 ft in a $50k tract and 100 ft in a $150k tract is a $60k corridor, not
    a $100k one."""
    g = pd.DataFrame({"income": [50_000.0, 150_000.0], "len_ft": [900.0, 100.0]})
    assert wavg(g, "income") == pytest.approx(60_000.0)


def test_a_single_tract_returns_that_tracts_value():
    g = pd.DataFrame({"income": [75_000.0], "len_ft": [1234.0]})
    assert wavg(g, "income") == pytest.approx(75_000.0)


def test_suppressed_tracts_are_dropped_not_treated_as_zero():
    """126 NYC tracts have a suppressed median income. Counting those as zero
    would drag every corridor crossing one toward the bottom quintile."""
    g = pd.DataFrame({"income": [80_000.0, np.nan], "len_ft": [500.0, 500.0]})
    assert wavg(g, "income") == pytest.approx(80_000.0)


def test_zero_length_pieces_are_ignored():
    """gpd.overlay emits slivers where a corridor merely touches a tract
    boundary. They carry no information and must not vote."""
    g = pd.DataFrame({"income": [80_000.0, 10_000.0], "len_ft": [500.0, 0.0]})
    assert wavg(g, "income") == pytest.approx(80_000.0)


def test_all_missing_returns_nan_rather_than_raising():
    g = pd.DataFrame({"income": [np.nan, np.nan], "len_ft": [100.0, 200.0]})
    assert np.isnan(wavg(g, "income"))


def test_all_zero_weight_returns_nan():
    g = pd.DataFrame({"income": [1.0, 2.0], "len_ft": [0.0, 0.0]})
    assert np.isnan(wavg(g, "income"))
