# -*- coding: utf-8 -*-
"""Sprint 2 — ProjectConfig roundtrip and validation tests."""
import os
import json
import sys
import pytest

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)


def test_config_creates_default():
    from core.config import ProjectConfig
    cfg = ProjectConfig()
    assert cfg.project_name == 'Unnamed Project'
    assert cfg.grid.cell_size_m == 5.0


def test_config_roundtrip_json(tmp_path, kayad_config):
    path = str(tmp_path / 'cfg.json')
    kayad_config.to_json(path)
    assert os.path.exists(path)
    loaded = type(kayad_config).from_json(path)
    assert loaded.project_name == kayad_config.project_name
    assert loaded.crs_epsg == 32643
    assert loaded.grid.nx == 482
    assert loaded.grid.cell_size_m == 5.0


def test_config_json_is_valid(tmp_path, kayad_config):
    path = str(tmp_path / 'cfg.json')
    kayad_config.to_json(path)
    with open(path) as f:
        data = json.load(f)
    assert 'project_name' in data
    assert 'grid' in data
    assert 'scoring' in data


def test_config_z_levels(kayad_config):
    levels = kayad_config.grid.z_levels
    assert levels[0] == -260.0
    assert levels[-1] == 460.0
    assert len(levels) == 145
    assert all(abs(levels[i+1] - levels[i] - 5.0) < 0.01
               for i in range(len(levels) - 1))


def test_config_cells_per_level(kayad_config):
    assert kayad_config.grid.n_cells_per_level == 482 * 722


def test_scoring_weights_sum(kayad_config):
    w = kayad_config.scoring
    prox_sum = sum(w.proximity.values())
    blind_sum = sum(w.blind.values())
    assert abs(prox_sum - 11.0) < 0.01, \
        f"Proximity weights sum to {prox_sum}, expected 11.0"
    assert abs(blind_sum - 12.0) < 0.01, \
        f"Blind weights sum to {blind_sum}, expected 12.0"


def test_config_missing_file_raises(tmp_path):
    from core.config import ProjectConfig
    with pytest.raises((FileNotFoundError, OSError)):
        ProjectConfig.from_json(str(tmp_path / 'nonexistent.json'))


def test_config_handles_partial_json(tmp_path):
    """Partial config should fill missing fields with defaults."""
    path = str(tmp_path / 'partial.json')
    with open(path, 'w') as f:
        json.dump({'project_name': 'Partial'}, f)
    from core.config import ProjectConfig
    cfg = ProjectConfig.from_json(path)
    assert cfg.project_name == 'Partial'
    assert cfg.grid.cell_size_m == 5.0  # default filled in


def test_config_threshold_keys(kayad_config):
    th = kayad_config.scoring.thresholds
    assert 'Very High' in th
    assert 'High' in th
    assert 'Moderate' in th
    assert 'Low' in th
    assert th['Very High'] == 75.0


def test_config_novelty_distance(kayad_config):
    assert kayad_config.scoring.novelty_distance_m == 500.0


def test_config_corridors(kayad_config):
    corrs = kayad_config.structure.corridors
    assert len(corrs) >= 2
    assert corrs[0]['name'] == 'Shallow_N28E'
    assert corrs[1]['name'] == 'Deep_N315E'
