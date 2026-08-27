"""Corridor construction: contiguity, tolerance, and geometry parsing."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import LineString, MultiLineString

from nycbike.corridors import ENDPOINT_TOLERANCE_FT, _endpoints, components_within_tolerance
from nycbike.ingest.bike_routes import _to_geometry

CRS = "EPSG:2263"  # feet


def _gs(lines):
    return gpd.GeoSeries(lines, crs=CRS)


def test_endpoints_of_a_linestring():
    first, last = _endpoints(LineString([(0, 0), (5, 0), (10, 0)]))
    assert first == (0.0, 0.0)
    assert last == (10.0, 0.0)


def test_endpoints_of_a_multilinestring_span_all_parts():
    g = MultiLineString([[(0, 0), (5, 0)], [(5, 0), (12, 0)]])
    first, last = _endpoints(g)
    assert first == (0.0, 0.0)
    assert last == (12.0, 0.0)


def test_touching_segments_form_one_corridor():
    lines = [LineString([(0, 0), (10, 0)]),
             LineString([(10, 0), (20, 0)]),
             LineString([(20, 0), (30, 0)])]
    assert len(set(components_within_tolerance(_gs(lines)))) == 1


def test_a_gap_wider_than_tolerance_splits_the_corridor():
    lines = [LineString([(0, 0), (10, 0)]),
             LineString([(10 + ENDPOINT_TOLERANCE_FT * 5, 0), (30, 0)])]
    assert len(set(components_within_tolerance(_gs(lines)))) == 2


def test_a_sub_tolerance_gap_is_bridged():
    """LION centerlines are meant to share endpoints exactly, but coordinate
    rounding leaves sub-foot gaps. Every one of those would otherwise become a
    spurious corridor break -- the exact failure that made ST_LineMerge
    unusable in the PostGIS build."""
    lines = [LineString([(0, 0), (10, 0)]),
             LineString([(10.4, 0), (20, 0)])]
    assert len(set(components_within_tolerance(_gs(lines)))) == 1


def test_a_three_way_junction_stays_one_component():
    """ST_LineMerge refuses to merge through a node where 3+ lines meet. The
    graph build must not inherit that behaviour: a street that forks and
    rejoins is still one corridor."""
    lines = [LineString([(0, 0), (10, 0)]),
             LineString([(10, 0), (20, 5)]),
             LineString([(10, 0), (20, -5)])]
    assert len(set(components_within_tolerance(_gs(lines)))) == 1


def test_an_isolated_segment_is_its_own_component_not_noise():
    lines = [LineString([(0, 0), (10, 0)]),
             LineString([(10, 0), (20, 0)]),
             LineString([(500, 500), (510, 500)])]
    labels = components_within_tolerance(_gs(lines))
    assert len(set(labels)) == 2
    assert labels[0] == labels[1] != labels[2]


@pytest.mark.parametrize("n", [0, 1])
def test_degenerate_inputs(n):
    lines = [LineString([(0, 0), (1, 0)])][:n]
    assert len(components_within_tolerance(_gs(lines))) == n


def test_geometry_parses_from_a_geojson_dict():
    g = _to_geometry({"type": "LineString", "coordinates": [[0, 0], [1, 1]]})
    assert g is not None and g.geom_type == "LineString"


def test_geometry_parses_from_a_json_string():
    g = _to_geometry('{"type": "LineString", "coordinates": [[0, 0], [1, 1]]}')
    assert g is not None and g.geom_type == "LineString"


@pytest.mark.parametrize("bad", [None, np.nan, "not json", "{}", '{"type":"Nope"}'])
def test_unparseable_geometry_returns_none_rather_than_raising(bad):
    """A handful of bad geometries must not abort a 29,695-row ingest; they are
    counted and logged instead."""
    assert _to_geometry(bad) is None
