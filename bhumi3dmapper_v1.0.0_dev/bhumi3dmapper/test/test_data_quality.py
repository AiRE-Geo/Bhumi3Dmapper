# -*- coding: utf-8 -*-
"""Tests for JC-28 data quality checks."""
import numpy as np
import pandas as pd
import pytest
import sys, os

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)

from modules.m12_data_quality import (
    DQIssue, DQReport, check_drill_quality, check_geophysics_quality,
    check_grid_quality, run_all_checks
)
from core.config import ProjectConfig


def _collar(n=10, z_present=True, dupes=False):
    data = {
        'BHID': [f'H{i:03d}' for i in range(n)],
        'XCOLLAR': [469500 + i*10 for i in range(n)],
        'YCOLLAR': [2934900 + i*10 for i in range(n)],
    }
    if z_present:
        data['ZCOLLAR'] = [460 - i for i in range(n)]
    else:
        data['ZCOLLAR'] = [None] * n
    if dupes:
        data['BHID'][0] = data['BHID'][1]
    return pd.DataFrame(data)


def _litho(n_clean=5, n_unknown=0):
    rows = []
    for _ in range(n_clean):
        rows.append({'BHID': 'H000', 'FROM': 0, 'TO': 10, 'lcode': 1})
    for _ in range(n_unknown):
        rows.append({'BHID': 'H000', 'FROM': 0, 'TO': 10, 'lcode': 0})
    return pd.DataFrame(rows)


def test_empty_collar_critical():
    cfg = ProjectConfig()
    issues = check_drill_quality(pd.DataFrame(), None, None, None, cfg)
    assert len(issues) >= 1
    assert issues[0].severity == 'critical'
    assert issues[0].blocks_advance


def test_duplicate_bhid_critical():
    cfg = ProjectConfig()
    df = _collar(n=5, dupes=True)
    issues = check_drill_quality(df, None, None, None, cfg)
    crit = [i for i in issues if i.severity == 'critical']
    assert len(crit) >= 1
    assert 'duplicate' in crit[0].title.lower()


def test_missing_elevations_warn():
    cfg = ProjectConfig()
    df = _collar(n=10, z_present=False)
    issues = check_drill_quality(df, None, None, None, cfg)
    warns = [i for i in issues if 'elevation' in i.title.lower()]
    assert len(warns) >= 1


def test_decimal_degree_coords_critical():
    cfg = ProjectConfig()
    df = pd.DataFrame({
        'BHID': ['H1', 'H2', 'H3'],
        'XCOLLAR': [75.3, 75.4, 75.5],  # longitude!
        'YCOLLAR': [26.5, 26.6, 26.7],
        'ZCOLLAR': [400, 405, 410],
    })
    issues = check_drill_quality(df, None, None, None, cfg)
    crit = [i for i in issues if i.severity == 'critical' and 'decimal' in i.title.lower()]
    assert len(crit) >= 1


def test_high_unknown_rock_warning():
    cfg = ProjectConfig()
    collar = _collar(n=5)
    litho = _litho(n_clean=2, n_unknown=8)  # 80% unknown
    issues = check_drill_quality(collar, litho, None, None, cfg)
    unknowns = [i for i in issues if 'unknown' in i.title.lower()]
    assert len(unknowns) >= 1


def test_clean_data_no_critical():
    cfg = ProjectConfig()
    collar = _collar(n=10)
    litho = _litho(n_clean=50, n_unknown=1)  # 2% unknown
    issues = check_drill_quality(collar, litho, None, None, cfg)
    crit = [i for i in issues if i.severity == 'critical']
    assert len(crit) == 0


def test_negative_grade_critical():
    cfg = ProjectConfig()
    collar = _collar(n=3)
    assay = pd.DataFrame({
        'BHID': ['H000', 'H001', 'H002'],
        'FROM': [0, 0, 0], 'TO': [10, 10, 10],
        'ZN': [5.0, -1.5, 10.0],  # negative!
    })
    issues = check_drill_quality(collar, None, assay, None, cfg)
    crit = [i for i in issues if i.severity == 'critical' and 'negative' in i.title.lower()]
    assert len(crit) >= 1


def test_no_gravity_warns():
    cfg = ProjectConfig()
    issues = check_geophysics_quality({}, {}, cfg)
    grav_warns = [i for i in issues if 'gravity' in i.title.lower()]
    assert len(grav_warns) >= 1


def test_high_nodata_warns():
    cfg = ProjectConfig()
    bad = np.full((50, 50), np.nan, dtype=np.float32)
    bad[:10, :10] = 0.1  # only 4% valid
    grids = {185: bad}
    issues = check_geophysics_quality(grids, {}, cfg)
    nodata_warns = [i for i in issues if 'nodata' in i.title.lower()]
    assert len(nodata_warns) >= 1


def test_invalid_z_range_critical():
    cfg = ProjectConfig()
    cfg.grid.z_top_mrl = 100
    cfg.grid.z_bot_mrl = 200  # inverted!
    issues = check_grid_quality(cfg)
    crit = [i for i in issues if i.severity == 'critical']
    assert len(crit) >= 1
    assert any(i.blocks_advance for i in crit)


def test_zero_cells_critical():
    cfg = ProjectConfig()
    cfg.grid.nx = 0
    issues = check_grid_quality(cfg)
    crit = [i for i in issues if i.severity == 'critical']
    assert len(crit) >= 1


def test_dqreport_summary():
    cfg = ProjectConfig()
    collar = _collar(n=5, dupes=True)
    report = run_all_checks(cfg, collar_df=collar)
    assert report.critical_count >= 1
    assert report.blocks_advance
    assert 'critical' in report.summary().lower()


def test_dqreport_by_category():
    cfg = ProjectConfig()
    collar = _collar(n=5, z_present=False)
    report = run_all_checks(cfg, collar_df=collar)
    by_cat = report.by_category()
    assert 'drill' in by_cat


def test_clean_dqreport():
    cfg = ProjectConfig()
    collar = _collar(n=10)  # clean data
    litho = _litho(n_clean=20)
    # Add valid geophysics
    arr = np.full((50, 50), 0.0, dtype=np.float32)
    grav = {185: arr, 210: arr, 235: arr}
    mag = {185: arr, 210: arr, 235: arr}
    report = run_all_checks(cfg, collar_df=collar, litho_df=litho,
                              grav_grids=grav, mag_grids=mag)
    assert report.critical_count == 0
    assert not report.blocks_advance


def test_issue_to_dict():
    i = DQIssue(category='drill', severity='warning', title='Test',
                details='d', action='a', affected=5)
    d = i.to_dict()
    assert d['category'] == 'drill'
    assert d['severity'] == 'warning'
