# -*- coding: utf-8 -*-
"""Sprint 5 — GeoPackage writer tests."""
import os
import sys
import sqlite3
import pytest
import numpy as np

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)


@pytest.fixture
def synthetic_gpkg(tmp_path, kayad_config):
    """Write a minimal GPKG for 5×5 cells at mRL 185."""
    from modules.m05_gpkg_writer import write_level_gpkg
    n = 25  # 5×5 test grid
    cell_E = np.array([469500.0 + (i % 5) * 5 for i in range(n)], dtype=np.float32)
    cell_N = np.array([2934900.0 + (i // 5) * 5 for i in range(n)], dtype=np.float32)
    geo = {
        'lv': np.ones(n, dtype=np.uint8),
        'pg': np.full(n, 6.0, dtype=np.float32),
        'csr': np.full(n, 20.0, dtype=np.float32),
        'grav': np.full(n, -0.05, dtype=np.float32),
        'grav_raw': np.full(n, -0.05, dtype=np.float32),
        'grav_gradient': np.full(n, 0.0005, dtype=np.float32),
        'grav_laplacian': np.full(n, -0.0001, dtype=np.float32),
        'mag': np.full(n, -5.0, dtype=np.float32),
        'mag_gradient': np.full(n, 0.05, dtype=np.float32),
        'dist_ore': np.linspace(10, 1000, n).astype(np.float32),
        'regime_id': 2,
        'grav_mean': 0.0, 'grav_std': 0.05,
        'mag_mean': 5.0, 'mag_std': 15.0,
        'gg_mean': 0.0003, 'gg_std': 0.0002,
        'lap_std': 0.00005, 'mg_p50': 0.04,
    }
    prox = {
        'c1': np.ones(n, dtype=np.float32),
        'c2': np.full(n, 0.8, dtype=np.float32),
        'c3': np.full(n, 0.9, dtype=np.float32),
        'c4': np.full(n, 0.75, dtype=np.float32),
        'c5': np.full(n, 0.7, dtype=np.float32),
        'c6': np.full(n, 0.95, dtype=np.float32),
        'c7': np.full(n, 0.85, dtype=np.float32),
        'c9': np.full(n, 0.75, dtype=np.float32),
        'c10': np.full(n, 0.8, dtype=np.float32),
        'score': np.full(n, 82.5, dtype=np.float32),
        'class': np.full(n, 4, dtype=np.uint8),
    }
    blind = {
        'c1': np.ones(n, dtype=np.float32),
        'c2': np.full(n, 0.8, dtype=np.float32),
        'c3': np.full(n, 0.9, dtype=np.float32),
        'c4': np.full(n, 0.7, dtype=np.float32),
        'c5': np.full(n, 0.65, dtype=np.float32),
        'c6': np.full(n, 0.95, dtype=np.float32),
        'c7b': np.full(n, 0.75, dtype=np.float32),
        'c8': np.full(n, 0.7, dtype=np.float32),
        'c9_lap': np.full(n, 0.8, dtype=np.float32),
        'c10': np.full(n, 0.6, dtype=np.float32),
        'score': np.full(n, 79.0, dtype=np.float32),
        'class': np.full(n, 3, dtype=np.uint8),
    }
    path = str(tmp_path / 'test_mRL+185.gpkg')
    write_level_gpkg(path, 185.0, prox, blind, geo, cell_E, cell_N, kayad_config)
    return path


def test_gpkg_file_created(synthetic_gpkg):
    assert os.path.exists(synthetic_gpkg), "GPKG file was not created"
    assert os.path.getsize(synthetic_gpkg) > 1000, "GPKG file is suspiciously small"


def test_gpkg_is_valid_sqlite(synthetic_gpkg):
    con = sqlite3.connect(synthetic_gpkg)
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM gpkg_contents").fetchall()]
    assert len(tables) > 0, "GPKG has no layers in gpkg_contents"
    con.close()


def test_gpkg_has_geometry_column(synthetic_gpkg):
    con = sqlite3.connect(synthetic_gpkg)
    rows = con.execute("SELECT * FROM gpkg_geometry_columns").fetchall()
    assert len(rows) > 0, "No geometry columns registered"
    con.close()


def test_gpkg_row_count(synthetic_gpkg):
    con = sqlite3.connect(synthetic_gpkg)
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM gpkg_contents").fetchall()]
    count = con.execute(f"SELECT COUNT(*) FROM [{tables[0]}]").fetchone()[0]
    assert count == 25, f"Expected 25 cells, got {count}"
    con.close()


def test_gpkg_required_fields_present(synthetic_gpkg):
    con = sqlite3.connect(synthetic_gpkg)
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM gpkg_contents").fetchall()]
    cols = [r[1] for r in con.execute(
        f"PRAGMA table_info([{tables[0]}])").fetchall()]
    for field in ['prox_score', 'blind_score', 'prox_class_id', 'blind_class_id',
                  'litho_code', 'litho_name', 'regime_name', 'dist_ore_m']:
        assert field in cols, f"Required field missing: {field}"
    con.close()


def test_gpkg_score_range_valid(synthetic_gpkg):
    con = sqlite3.connect(synthetic_gpkg)
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM gpkg_contents").fetchall()]
    rows = con.execute(
        f"SELECT prox_score, blind_score FROM [{tables[0]}]").fetchall()
    for ps, bs in rows:
        assert 0 <= ps <= 100, f"prox_score out of range: {ps}"
        assert 0 <= bs <= 100, f"blind_score out of range: {bs}"
    con.close()


def test_gpkg_novel_target_column(synthetic_gpkg):
    """novel_target should be 1 where dist_ore_m > novelty threshold."""
    con = sqlite3.connect(synthetic_gpkg)
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM gpkg_contents").fetchall()]
    rows = con.execute(
        f"SELECT dist_ore_m, novel_target FROM [{tables[0]}]").fetchall()
    for dist, novel in rows:
        if dist > 500:
            assert novel == 1, f"dist={dist}m should be novel=1, got {novel}"
        else:
            assert novel == 0, f"dist={dist}m should be novel=0, got {novel}"
    con.close()


def test_gpkg_srs_registered(synthetic_gpkg):
    con = sqlite3.connect(synthetic_gpkg)
    srids = [r[0] for r in con.execute(
        "SELECT srs_id FROM gpkg_spatial_ref_sys").fetchall()]
    assert 32643 in srids, "EPSG:32643 not registered in gpkg_spatial_ref_sys"
    con.close()
