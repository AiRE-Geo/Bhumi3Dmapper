# -*- coding: utf-8 -*-
"""Tests for JC-26 example project loader."""
import json
import os
import sys
import tempfile

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)

from modules.m11_example import (
    copy_example_project, is_example_output, example_banner_text, EXAMPLE_DIR
)


def test_example_dir_exists():
    """The bundled example directory must exist in the plugin."""
    assert os.path.isdir(EXAMPLE_DIR), f"Example not bundled at {EXAMPLE_DIR}"


def test_example_has_required_files():
    """Bundled example has config.json, data CSVs, and geophysics TIFs."""
    assert os.path.exists(os.path.join(EXAMPLE_DIR, 'config.json'))
    assert os.path.exists(os.path.join(EXAMPLE_DIR, 'data', 'collar.csv'))
    assert os.path.exists(os.path.join(EXAMPLE_DIR, 'data', 'litho.csv'))
    assert os.path.exists(os.path.join(EXAMPLE_DIR, 'data', 'assay.csv'))
    assert os.path.exists(os.path.join(EXAMPLE_DIR, 'data', 'survey.csv'))
    assert os.path.exists(os.path.join(EXAMPLE_DIR, 'geophysics', 'gravity'))
    assert os.path.exists(os.path.join(EXAMPLE_DIR, 'geophysics', 'magnetics'))
    # At least 3 TIFs per geophysics folder
    grav_tifs = [f for f in os.listdir(os.path.join(EXAMPLE_DIR, 'geophysics', 'gravity'))
                 if f.endswith('.tif')]
    assert len(grav_tifs) >= 3


def test_copy_example_to_tempdir():
    """Copying should produce a fully-usable project."""
    with tempfile.TemporaryDirectory() as d:
        cfg_path = copy_example_project(d)
        assert os.path.exists(cfg_path)
        with open(cfg_path) as f:
            cfg = json.load(f)
        # Paths should be absolute after rewrite
        assert os.path.isabs(cfg['drill']['collar_csv'])
        assert os.path.exists(cfg['drill']['collar_csv'])
        assert os.path.isabs(cfg['geophysics']['gravity_folder'])
        assert os.path.isdir(cfg['geophysics']['gravity_folder'])


def test_copy_overwrites_existing():
    """Copying again should replace existing folder cleanly."""
    with tempfile.TemporaryDirectory() as d:
        p1 = copy_example_project(d)
        p2 = copy_example_project(d)  # should not fail
        assert p1 == p2


def test_is_example_output():
    """Banner detection by filename."""
    assert is_example_output('/tmp/Bhumi3D_Example_DO_NOT_USE_FOR_REAL_mRL+0185.gpkg')
    assert not is_example_output('/tmp/MyProject_Prospectivity_mRL+0185.gpkg')


def test_example_banner_text():
    """Banner text must clearly warn."""
    t = example_banner_text()
    assert 'EXAMPLE' in t
    assert 'NOT' in t.upper() or 'DO NOT' in t.upper()


def test_config_uses_sedex_preset():
    """Bundled example uses SEDEX deposit type."""
    cfg_path = os.path.join(EXAMPLE_DIR, 'config.json')
    with open(cfg_path) as f:
        cfg = json.load(f)
    assert cfg.get('deposit_type') == 'SEDEX Pb-Zn'


def test_example_data_has_veto_lithology():
    """Example litho.csv must include amphibolite (code 2) for veto demonstration."""
    collar = os.path.join(EXAMPLE_DIR, 'data', 'litho.csv')
    with open(collar) as f:
        content = f.read()
    assert 'AMPH' in content or 'AM' in content
