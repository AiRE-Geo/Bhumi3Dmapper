# -*- coding: utf-8 -*-
"""Sprint 4 — DataLoader tests using synthetic data."""
import os
import sys
import pytest

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)


def test_collar_loads(configured_config):
    from modules.m01_data_loader import DataLoader
    loader = DataLoader(configured_config)
    df = loader.load_collar()
    assert len(df) == 2
    assert 'XCOLLAR' in df.columns


def test_litho_loads_with_lcodes(configured_config):
    from modules.m01_data_loader import DataLoader
    loader = DataLoader(configured_config)
    df = loader.load_litho()
    assert len(df) > 0
    assert 'lcode' in df.columns
    assert 1 in df['lcode'].values  # QMS = 1


def test_gravity_loads(configured_config):
    from modules.m01_data_loader import DataLoader
    loader = DataLoader(configured_config)
    grids = loader.load_gravity()
    assert len(grids) == 3
    assert 185 in grids
    assert grids[185].shape == (50, 50)


def test_magnetics_loads(configured_config):
    from modules.m01_data_loader import DataLoader
    loader = DataLoader(configured_config)
    grids = loader.load_magnetics()
    assert len(grids) == 3
    assert 185 in grids


def test_validation_passes_with_good_data(configured_config):
    from modules.m01_data_loader import DataLoader
    loader = DataLoader(configured_config)
    result = loader.validate_all()
    assert result is True


def test_validation_fails_gracefully_bad_path(configured_config):
    """Missing files should not raise — should return False with clear message."""
    configured_config.drill.collar_csv = '/nonexistent/path/collar.csv'
    from modules.m01_data_loader import DataLoader
    loader = DataLoader(configured_config)
    result = loader.validate_all()
    assert result is False  # should return False, not raise


def test_empty_litho_rock_code_defaults_to_zero():
    """Unknown rock codes should default to 0, not crash."""
    from modules.m01_data_loader import DataLoader
    from core.config import ProjectConfig
    cfg = ProjectConfig()
    loader = DataLoader(cfg)
    result = loader._classify_rock_code('UNKNOWN_ROCK')
    assert result == 0
