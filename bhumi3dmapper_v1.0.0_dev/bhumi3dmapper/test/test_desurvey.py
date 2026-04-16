# -*- coding: utf-8 -*-
"""Tests for drill hole desurvey module."""
import numpy as np
import pandas as pd
import pytest
import sys
import os

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)

from modules.m07_desurvey import minimum_curvature_desurvey, interpolate_at_depth


def _make_collar(bhids, xs, ys, zs):
    return pd.DataFrame({
        'BHID': bhids, 'XCOLLAR': xs, 'YCOLLAR': ys, 'ZCOLLAR': zs
    })


def _make_survey(bhid, depths, azis, dips):
    return pd.DataFrame({
        'BHID': [bhid] * len(depths),
        'DEPTH': depths, 'BRG': azis, 'DIP': dips
    })


def test_vertical_hole_identity():
    """Vertical hole: XY should stay at collar, Z decreases linearly."""
    collar = _make_collar(['V1'], [1000.0], [2000.0], [500.0])
    survey = _make_survey('V1', [0, 50, 100, 200], [0, 0, 0, 0], [-90, -90, -90, -90])
    result = minimum_curvature_desurvey(survey, collar)

    v1 = result[result['BHID'] == 'V1'].sort_values('DEPTH')
    # X and Y should be constant at collar position
    assert np.allclose(v1['X'].values, 1000.0, atol=0.01)
    assert np.allclose(v1['Y'].values, 2000.0, atol=0.01)
    # Z should decrease by depth amount
    expected_z = [500.0, 500.0, 450.0, 400.0, 300.0]  # collar + 4 stations
    assert np.allclose(v1['Z'].values, expected_z, atol=0.1)


def test_inclined_hole_45deg():
    """Hole inclined 45 degrees due north: should drift north and down equally."""
    collar = _make_collar(['I1'], [0.0], [0.0], [100.0])
    survey = _make_survey('I1', [0, 100], [0, 0], [-45, -45])
    result = minimum_curvature_desurvey(survey, collar)

    i1 = result[result['BHID'] == 'I1'].sort_values('DEPTH')
    last = i1.iloc[-1]
    # At 45 deg, 100m downhole: horizontal offset ~70.7m, vertical ~70.7m
    assert abs(last['X'] - 0.0) < 1.0, "No east drift expected for azimuth=0"
    assert abs(last['Y'] - 70.7) < 2.0, f"Expected ~70.7m north drift, got {last['Y']}"
    assert abs(last['Z'] - (100.0 - 70.7)) < 2.0, f"Expected Z~29.3, got {last['Z']}"


def test_horizontal_hole():
    """Hole at 0 degrees dip (horizontal): should drift horizontally only."""
    collar = _make_collar(['H1'], [0.0], [0.0], [100.0])
    survey = _make_survey('H1', [0, 50], [90, 90], [0, 0])
    result = minimum_curvature_desurvey(survey, collar)

    h1 = result[result['BHID'] == 'H1'].sort_values('DEPTH')
    last = h1.iloc[-1]
    assert abs(last['X'] - 50.0) < 1.0, "Should drift 50m east"
    assert abs(last['Y'] - 0.0) < 1.0, "No north drift"
    assert abs(last['Z'] - 100.0) < 1.0, "No vertical change"


def test_interpolate_at_depth():
    """Interpolation between survey stations."""
    collar = _make_collar(['T1'], [0.0], [0.0], [100.0])
    survey = _make_survey('T1', [0, 100], [0, 0], [-90, -90])
    desurvey = minimum_curvature_desurvey(survey, collar)

    # Midpoint
    xyz = interpolate_at_depth(desurvey, 'T1', 50.0)
    assert xyz is not None
    assert abs(xyz[2] - 50.0) < 1.0, f"Expected Z~50 at depth 50, got {xyz[2]}"


def test_multiple_holes():
    """Desurvey with multiple holes."""
    collar = _make_collar(['A', 'B'], [0.0, 100.0], [0.0, 0.0], [500.0, 500.0])
    survey_a = _make_survey('A', [0, 100], [0, 0], [-90, -90])
    survey_b = _make_survey('B', [0, 100], [90, 90], [-45, -45])
    survey = pd.concat([survey_a, survey_b], ignore_index=True)

    result = minimum_curvature_desurvey(survey, collar)
    assert set(result['BHID'].unique()) == {'A', 'B'}
    assert len(result[result['BHID'] == 'A']) >= 2
    assert len(result[result['BHID'] == 'B']) >= 2


def test_missing_collar_skipped():
    """Holes without collar data should be skipped gracefully."""
    collar = _make_collar(['A'], [0.0], [0.0], [500.0])
    survey = _make_survey('B', [0, 100], [0, 0], [-90, -90])
    result = minimum_curvature_desurvey(survey, collar)
    assert len(result) == 0 or 'B' not in result['BHID'].values
