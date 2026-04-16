# -*- coding: utf-8 -*-
"""Tests for deposit type presets."""
import pytest
import sys, os
import numpy as np

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)

from core.presets.loader import list_presets, load_preset, apply_preset
from core.config import ProjectConfig
from modules.m04_scoring_engine import score_lithology, compute_proximity, compute_blind


def test_list_presets():
    """Should list at least 4 deposit type presets."""
    presets = list_presets()
    assert len(presets) >= 4
    assert 'sedex_pbzn' in presets
    assert 'vms_cuzn' in presets
    assert 'epithermal_au' in presets
    assert 'porphyry_cumo' in presets


def test_load_sedex_preset():
    """SEDEX preset should load and contain criterion_thresholds."""
    data = load_preset('sedex_pbzn')
    assert 'deposit_type' in data
    assert data['deposit_type'] == 'SEDEX Pb-Zn'
    assert 'criterion_thresholds' in data


def test_load_vms_preset():
    data = load_preset('vms_cuzn')
    assert data['deposit_type'] == 'VMS Cu-Zn'
    ct = data['criterion_thresholds']
    # VMS: felsic volcanic (code 5) should be primary host in upper regime
    assert ct['litho_scores']['2']['5'] == 1.0


def test_apply_vms_preset():
    """Applying VMS preset should change lithology scoring."""
    cfg = ProjectConfig()
    apply_preset(cfg, 'vms_cuzn')
    assert cfg.deposit_type == 'VMS Cu-Zn'
    # Felsic volcanic should now score 1.0 in upper regime
    s = score_lithology(np.array([5], dtype=np.float32), 2, cfg)
    assert np.isclose(s[0], 1.0)
    # QMS should score low in VMS
    s2 = score_lithology(np.array([1], dtype=np.float32), 2, cfg)
    assert s2[0] < 0.5


def test_apply_porphyry_preset():
    """Porphyry preset should change ore envelope minimum radius."""
    cfg = ProjectConfig()
    apply_preset(cfg, 'porphyry_cumo')
    assert cfg.criterion_thresholds.ore_envelope_min_radius == 100


def test_preset_not_found():
    with pytest.raises(FileNotFoundError):
        load_preset('nonexistent_deposit')


def test_all_presets_produce_valid_scores():
    """Every preset should produce scores in [0, 100] for both models."""
    arr = lambda *v: np.array(v, dtype=np.float32)
    E = np.full(5, 469500.0, dtype=np.float32)
    N = np.full(5, 2934900.0, dtype=np.float32)

    inputs = {
        'lv': arr(1, 3, 4, 5, 0),
        'pg': arr(6, 20, 50, 100, 200),
        'csr': arr(20, 5, 30, 80, 150),
        'grav': np.full(5, -0.05, dtype=np.float32),
        'grav_raw': np.full(5, -0.05, dtype=np.float32),
        'grav_gradient': np.full(5, 0.0005, dtype=np.float32),
        'grav_laplacian': np.full(5, -0.0001, dtype=np.float32),
        'mag': np.full(5, -5.0, dtype=np.float32),
        'mag_gradient': np.full(5, 0.05, dtype=np.float32),
        'cell_E': E, 'cell_N': N, 'z_mrl': 185.0, 'regime_id': 2,
        'dist_ore': np.full(5, 300.0, dtype=np.float32),
        'ore_area': 30000.0,
        'grav_mean': 0.0, 'grav_std': 0.05,
        'mag_mean': 5.0, 'mag_std': 15.0,
        'gg_mean': 0.0003, 'gg_std': 0.0002,
        'lap_std': 0.00005, 'mg_p50': 0.04,
        'block_model_df': None,
    }

    for preset_name in list_presets():
        cfg = ProjectConfig()
        apply_preset(cfg, preset_name)
        prox = compute_proximity(inputs, cfg)
        blind = compute_blind(inputs, cfg)
        assert 0 <= prox['score'].min() <= prox['score'].max() <= 100, \
            f"Preset {preset_name}: proximity scores out of range"
        assert 0 <= blind['score'].min() <= blind['score'].max() <= 100, \
            f"Preset {preset_name}: blind scores out of range"
