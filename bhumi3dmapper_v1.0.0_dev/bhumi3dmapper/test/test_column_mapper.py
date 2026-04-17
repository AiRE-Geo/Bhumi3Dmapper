# -*- coding: utf-8 -*-
"""Tests for JC-24 column mapper."""
import pandas as pd
import pytest
import sys, os

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)

from modules.m09_column_mapper import (
    fuzzy_match, auto_map, preview_data, validate_mapping, sanity_check_column,
    FIELD_ALIASES, REQUIRED_FIELDS, OPTIONAL_FIELDS
)


def test_exact_match_scores_one():
    r = fuzzy_match('col_bhid', ['BHID', 'XCOLLAR'])
    assert r[0][0] == 'BHID' and r[0][1] >= 0.99


def test_fuzzy_match_hole_id():
    r = fuzzy_match('col_bhid', ['HOLE_ID', 'EAST', 'NORTH'])
    assert r[0][0] == 'HOLE_ID' and r[0][1] >= 0.70


def test_fuzzy_match_east_is_xcollar():
    r = fuzzy_match('col_xcollar', ['HOLE_ID', 'EAST', 'NORTH', 'RL'])
    assert r[0][0] == 'EAST'


def test_fuzzy_match_rl_is_zcollar():
    r = fuzzy_match('col_zcollar', ['HOLE_ID', 'EAST', 'NORTH', 'RL'])
    assert r[0][0] == 'RL'


def test_no_match_below_threshold():
    r = fuzzy_match('col_zn', ['FOO', 'BAR', 'BAZ'], threshold=0.80)
    assert len(r) == 0


def test_auto_map_collar_full():
    cols = ['HOLE_ID', 'EAST', 'NORTH', 'RL', 'MAX_DEPTH']
    mapping = auto_map('collar', cols)
    assert mapping['col_bhid'] == 'HOLE_ID'
    assert mapping['col_xcollar'] == 'EAST'
    assert mapping['col_ycollar'] == 'NORTH'
    assert mapping['col_zcollar'] == 'RL'


def test_auto_map_no_double_use():
    """Two fields should not map to the same column."""
    cols = ['HOLE', 'EAST', 'NORTH', 'RL']  # no clear depth column
    mapping = auto_map('collar', cols)
    used = [v for v in mapping.values() if v is not None]
    assert len(used) == len(set(used))


def test_auto_map_optional_unmapped():
    """Optional fields can be None when no match exists."""
    cols = ['BHID', 'XCOLLAR', 'YCOLLAR', 'ZCOLLAR']  # no ZN/PB
    mapping = auto_map('assay', cols)
    assert mapping['col_zn'] is None
    assert mapping['col_pb'] is None


def test_validate_required_present():
    mapping = {'col_bhid': 'HOLE_ID', 'col_xcollar': 'EAST',
               'col_ycollar': 'NORTH', 'col_zcollar': 'RL'}
    ok, missing = validate_mapping(mapping, 'collar')
    assert ok and missing == []


def test_validate_missing_required():
    mapping = {'col_bhid': None, 'col_xcollar': 'EAST',
               'col_ycollar': 'NORTH', 'col_zcollar': 'RL'}
    ok, missing = validate_mapping(mapping, 'collar')
    assert not ok
    assert 'col_bhid' in missing


def test_preview_data_numeric():
    df = pd.DataFrame({'EAST': [468655, 468712, 469100, 469550]})
    p = preview_data(df, 'EAST')
    assert p['is_numeric']
    assert p['min'] == 468655
    assert p['max'] == 469550
    assert p['n_null'] == 0


def test_sanity_check_utm_looks_like_latlon():
    df = pd.DataFrame({'EAST': [75.3, 75.4, 75.5]})  # looks like longitude
    w = sanity_check_column(df, 'EAST', 'col_xcollar')
    assert len(w) >= 1
    assert 'longitude' in w[0].lower()


def test_sanity_check_utm_ok():
    df = pd.DataFrame({'EAST': [468655, 468712, 469100]})
    w = sanity_check_column(df, 'EAST', 'col_xcollar')
    assert len(w) == 0  # no warnings for proper UTM


def test_sanity_check_dip_out_of_range():
    df = pd.DataFrame({'DIP': [-45, -60, 120]})  # 120 is invalid
    w = sanity_check_column(df, 'DIP', 'col_dip')
    assert len(w) >= 1


def test_fuzzy_match_case_insensitive():
    """Column matching should ignore case."""
    r = fuzzy_match('col_bhid', ['bhid', 'BHID', 'Bhid'])
    for col, score in r:
        assert score >= 0.99
