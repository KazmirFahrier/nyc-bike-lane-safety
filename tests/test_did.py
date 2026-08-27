"""The estimator, on data whose answer is known by construction.

A hand-rolled Callaway-Sant'Anna goes wrong quietly: an off-by-one in the base
period or a control group that keeps already-treated units produces a plausible
number rather than an error. These tests pin the arithmetic to a panel where
the true effect is exactly -1.0.
"""

from __future__ import annotations

import did
import numpy as np
import pandas as pd
import pytest


def test_att_recovers_a_known_effect(two_cohort_panel, two_cohort_matched):
    gt = did.att_gt(two_cohort_panel, two_cohort_matched)
    post = gt[gt["event_time"] >= 0]
    assert len(post) > 0
    assert np.allclose(post["att"], -1.0), post[["year", "att"]].to_dict("records")


def test_pre_period_atts_are_zero_when_trends_are_parallel(two_cohort_panel, two_cohort_matched):
    gt = did.att_gt(two_cohort_panel, two_cohort_matched)
    pre = gt[gt["event_time"] < 0]
    assert len(pre) > 0
    assert np.allclose(pre["att"], 0.0, atol=1e-12)


def test_base_period_is_excluded_from_the_output(two_cohort_panel, two_cohort_matched):
    gt = did.att_gt(two_cohort_panel, two_cohort_matched)
    assert (gt["event_time"] == -1).sum() == 0, "the base year must not appear as an estimate"


def test_alternative_base_window_averages_several_years(two_cohort_panel, two_cohort_matched):
    """With flat pre-trends both base choices agree. The point of the test is
    that the multi-year window runs at all and excludes every year it averages."""
    gt = did.att_gt(two_cohort_panel, two_cohort_matched, base_window=(-3, -2))
    assert not gt.empty
    assert set(gt["event_time"]) & {-3, -2} == set()
    post = gt[gt["event_time"] >= 0]
    assert np.allclose(post["att"], -1.0)


def test_already_treated_units_are_dropped_from_controls():
    """A corridor treated in 2016 must not serve as a control for the 2018
    cohort in 2018 onward. If it does, the estimate is contaminated -- which is
    precisely the failure two-way fixed effects has."""
    rows = []
    for cid, first in (("T", 2018.0), ("EARLY", 2016.0), ("NEVER", None)):
        for yr in range(2015, 2021):
            treated_now = first is not None and yr >= first
            rows.append({
                "corridor_id": cid, "panel_year": yr, "boro_code": "1", "n_segments": 1,
                "cyclist_injured": 1.0, "injuries_per_segment": 5.0 if treated_now else 1.0,
                "treatment_cohort": "switcher" if first else "never_treated",
                "first_protected_year": first,
            })
    panel = pd.DataFrame(rows)
    matched = pd.DataFrame([
        {"cohort_year": 2018, "corridor_id": "T", "is_treated_here": True,
         "is_eligible_control": False, "in_common_support": True, "cem_weight": 1.0},
        {"cohort_year": 2018, "corridor_id": "EARLY", "is_treated_here": False,
         "is_eligible_control": True, "in_common_support": True, "cem_weight": 1.0},
        {"cohort_year": 2018, "corridor_id": "NEVER", "is_treated_here": False,
         "is_eligible_control": True, "in_common_support": True, "cem_weight": 1.0},
    ])
    gt = did.att_gt(panel, matched)
    post = gt[gt["event_time"] >= 0]
    # NEVER stays flat at 1.0; EARLY is already at 5.0 and must be excluded.
    # Treated goes 1.0 -> 5.0, so the ATT is +4.0 against the clean control.
    assert np.allclose(post["att"], 4.0), post[["year", "att"]].to_dict("records")


def test_event_study_weights_cohorts_by_size():
    gt = pd.DataFrame([
        {"cohort": 2018, "year": 2018, "event_time": 0, "att": 1.0, "n_treated": 90},
        {"cohort": 2019, "year": 2019, "event_time": 0, "att": 11.0, "n_treated": 10},
    ])
    ev = did.aggregate_event_study(gt)
    # (1*90 + 11*10) / 100 = 2.0, not the unweighted 6.0
    assert ev.loc[ev["event_time"] == 0, "att"].iloc[0] == pytest.approx(2.0)


def test_overall_att_uses_post_periods_only():
    gt = pd.DataFrame([
        {"cohort": 2018, "year": 2016, "event_time": -2, "att": 99.0, "n_treated": 1},
        {"cohort": 2018, "year": 2018, "event_time": 0, "att": -1.0, "n_treated": 1},
        {"cohort": 2018, "year": 2019, "event_time": 1, "att": -3.0, "n_treated": 1},
    ])
    assert did.aggregate_overall(gt) == pytest.approx(-2.0)


class TestBootstrapPvalue:
    """The bug this function exists to prevent."""

    def test_recentres_rather_than_comparing_to_its_own_centre(self):
        # Draws centred far from zero: naively comparing |draw| >= |observed|
        # returns ~0.5 by construction. Recentred, this is a decisive rejection.
        rng = np.random.default_rng(0)
        draws = rng.normal(loc=10.0, scale=1.0, size=20_000)
        p = did.bootstrap_pvalue(draws, observed=10.0)
        assert p < 0.001, f"expected a decisive rejection, got {p}"

    def test_a_statistic_indistinguishable_from_zero_gives_a_large_p(self):
        rng = np.random.default_rng(1)
        draws = rng.normal(loc=0.05, scale=1.0, size=20_000)
        assert did.bootstrap_pvalue(draws, observed=0.05) > 0.5

    def test_handles_all_nan_draws(self):
        assert np.isnan(did.bootstrap_pvalue(np.array([np.nan, np.nan]), 1.0))
