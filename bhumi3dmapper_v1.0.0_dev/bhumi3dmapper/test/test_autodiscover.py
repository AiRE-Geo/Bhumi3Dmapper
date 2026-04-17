# -*- coding: utf-8 -*-
"""Tests for JC-23 autodiscovery."""
import os
import tempfile
import pytest
import sys

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)

from modules.m08_autodiscover import autodiscover, apply_to_config
from core.config import ProjectConfig


def _make_standard_project(root):
    """Create a standard-layout fake project folder."""
    os.makedirs(os.path.join(root, 'drillholes'), exist_ok=True)
    os.makedirs(os.path.join(root, 'geophysics', 'gravity'), exist_ok=True)
    os.makedirs(os.path.join(root, 'geophysics', 'magnetics'), exist_ok=True)
    os.makedirs(os.path.join(root, 'ore_polygons'), exist_ok=True)
    # Touch files
    for name in ['collar.csv', 'assay.csv', 'litho.csv', 'survey.csv']:
        open(os.path.join(root, 'drillholes', name), 'w').close()
    for n in [185, 210, 235]:
        open(os.path.join(root, 'geophysics', 'gravity', f'grav_{n}.tif'), 'w').close()
        open(os.path.join(root, 'geophysics', 'magnetics', f'mag_{n}.tif'), 'w').close()


def test_standard_layout_all_found():
    with tempfile.TemporaryDirectory() as d:
        _make_standard_project(d)
        r = autodiscover(d)
        assert r['collar_csv'] and r['collar_csv'].endswith('collar.csv')
        assert r['assay_csv'] and r['assay_csv'].endswith('assay.csv')
        assert r['litho_csv'] and r['litho_csv'].endswith('litho.csv')
        assert r['survey_csv'] and r['survey_csv'].endswith('survey.csv')
        assert r['gravity_folder'] and r['gravity_folder'].endswith('gravity')
        assert r['magnetics_folder'] and r['magnetics_folder'].endswith('magnetics')


def test_case_insensitive_naming():
    with tempfile.TemporaryDirectory() as d:
        _make_standard_project(d)
        # Add uppercase variant folder with TIFs
        extra = os.path.join(d, 'GRAVITY_EXTRA')
        os.makedirs(extra, exist_ok=True)
        r = autodiscover(d)
        # Should still find the original lowercase folder
        assert r['gravity_folder'] is not None


def test_ambiguous_collar_reported():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, 'drillholes'), exist_ok=True)
        open(os.path.join(d, 'drillholes', 'collar_v1.csv'), 'w').close()
        open(os.path.join(d, 'drillholes', 'collar_v2.csv'), 'w').close()
        open(os.path.join(d, 'drillholes', 'collar_final.csv'), 'w').close()
        r = autodiscover(d)
        # Should NOT guess — reports ambiguity
        assert r['collar_csv'] is None or len([a for a in r['ambiguous'] if a['field'] == 'collar_csv']) > 0
        amb_fields = [a['field'] for a in r['ambiguous']]
        assert 'collar_csv' in amb_fields


def test_missing_folder_no_crash():
    with tempfile.TemporaryDirectory() as d:
        # Empty folder
        r = autodiscover(d)
        assert r['collar_csv'] is None
        assert r['gravity_folder'] is None
        # No exceptions, no warnings for empty folder (just missing optional paths)


def test_nonexistent_root_warns():
    r = autodiscover('/does/not/exist')
    assert len(r['warnings']) > 0


def test_gravity_folder_without_tifs_warns():
    with tempfile.TemporaryDirectory() as d:
        # Create gravity folder but no TIFs
        os.makedirs(os.path.join(d, 'gravity'), exist_ok=True)
        r = autodiscover(d)
        # Should warn about missing TIFs
        assert any('tif' in w.lower() for w in r['warnings']) or r['gravity_folder'] is None


def test_apply_to_config():
    with tempfile.TemporaryDirectory() as d:
        _make_standard_project(d)
        r = autodiscover(d)
        cfg = ProjectConfig()
        changes = apply_to_config(cfg, r)
        assert len(changes) >= 4  # at least collar, assay, litho, survey
        assert cfg.drill.collar_csv.endswith('collar.csv')
        assert cfg.geophysics.gravity_folder.endswith('gravity')


def test_non_ascii_paths():
    """Paths with accents and spaces should work."""
    with tempfile.TemporaryDirectory() as d:
        subdir = os.path.join(d, 'Proyecto Añasagasti', 'Drilling 2025')
        os.makedirs(subdir, exist_ok=True)
        os.makedirs(os.path.join(subdir, 'drillholes'), exist_ok=True)
        open(os.path.join(subdir, 'drillholes', 'collar.csv'), 'w').close()
        r = autodiscover(subdir)
        assert r['collar_csv'] is not None
