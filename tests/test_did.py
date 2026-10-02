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


def test_removed_and_undated_lanes_are_excluded_from_absorbing_design():
    p = pd.DataFrame({
        "corridor_id": ["removed", "removed", "unknown", "clean"],
        "panel_year": [2018, 2019, 2019, 2019],
        "first_protected_year": [2018, 2018, 2018, 2018],
        "is_treated": [True, False, True, True],
        "has_undated_removal": [False, False, True, False],
    })
    m = pd.DataFrame({"corridor_id": ["removed", "unknown", "clean"]})
    panel, matched = did.absorbing_sample(p, m)
    assert panel.corridor_id.tolist() == ["clean"]
    assert matched.corridor_id.tolist() == ["clean"]


def test_strata_weights_are_rebuilt_when_a_future_control_is_treated():
    # Both strata have one treated corridor. Removing a future treated control
    # must leave equal stratum weights, rather than halve the first stratum.
    rows = []
    definitions = [("T1", "A", 2018, 0), ("T2", "B", 2018, 0),
                   ("C1", "A", None, 10), ("F", "A", 2019, 10),
                   ("C2", "B", None, 0)]
    for cid, _st, first, delta in definitions:
        for yr in [2017, 2019]:
            rows.append({"corridor_id": cid, "panel_year": yr,
                         "injuries_per_segment": delta if yr == 2019 else 0,
                         "first_protected_year": first})
    p = pd.DataFrame(rows)
    m = pd.DataFrame([{"corridor_id": cid, "cohort_year": 2018,
                       "is_treated_here": cid.startswith("T"), "boro_code": st,
                       "injury_bin": "0", "cem_weight": 0.5 if st == "A" and not cid.startswith("T") else 1.0}
                      for cid, st, _, _ in definitions])
    gt = did.att_gt(p, m)
    assert gt.loc[gt.year.eq(2019), "att"].iloc[0] == pytest.approx(-5)
    draws, _, _ = did.bootstrap(p, m, n_boot=300)
    finite = draws[~np.isnan(draws)]
    assert np.isfinite(finite).all()
    assert finite.min() >= -10 and finite.max() <= 0

    # Validate batched bootstrap arithmetic against independent explicit
    # resampling and the estimator on the same first five multinomial draws.
    ids = np.sort(m.corridor_id.unique())
    rng = np.random.default_rng(did.RNG_SEED)
    multiplicities = rng.multinomial(len(ids), np.full(len(ids), 1 / len(ids)), size=5)
    for i, counts in enumerate(multiplicities):
        draw = np.repeat(ids, counts)
        rep = pd.DataFrame({"corridor_id": draw, "boot_id": [f"B{j}" for j in range(len(draw))]})
        bp = p.merge(rep, on="corridor_id").drop(columns="corridor_id").rename(columns={"boot_id": "corridor_id"})
        bm = m.merge(rep, on="corridor_id").drop(columns="corridor_id").rename(columns={"boot_id": "corridor_id"})
        reference = did.att_gt(bp, bm)
        expected = did.aggregate_overall(reference) if not reference.empty else np.nan
        assert np.isclose(draws[i], expected, equal_nan=True)


def test_block_bootstrap_preserves_known_constant_effect(two_cohort_panel, two_cohort_matched):
    overall, events, _ = did.bootstrap(two_cohort_panel, two_cohort_matched, n_boot=200)
    assert np.allclose(overall[np.isfinite(overall)], -1)
    for event in events.columns:
        expect = -1 if event >= 0 else 0
        assert np.allclose(events[event].dropna(), expect)


def test_bootstrap_draws_ignore_input_row_order(two_cohort_panel, two_cohort_matched):
    # Heterogeneous outcomes ensure permuted draw assignments are detectable.
    panel = two_cohort_panel.copy()
    ids = sorted(panel.corridor_id.unique())
    slopes = dict(zip(ids, np.arange(len(ids)) * 0.3, strict=True))
    panel['injuries_per_segment'] += panel.corridor_id.map(slopes) * panel.panel_year
    original = did.bootstrap(panel, two_cohort_matched, n_boot=100)
    shuffled = did.bootstrap(panel.sample(frac=1, random_state=7),
                             two_cohort_matched.sample(frac=1, random_state=8), n_boot=100)
    for expected, actual in zip(original, shuffled, strict=True):
        np.testing.assert_allclose(expected, actual, atol=1e-10, equal_nan=True)
