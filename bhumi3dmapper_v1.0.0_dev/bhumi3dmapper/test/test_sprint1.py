# -*- coding: utf-8 -*-
"""Sprint 1 — plugin skeleton, no QGIS import needed for these tests."""
import os
import re
import sys

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(PLUGIN_DIR))


def test_metadata_exists():
    path = os.path.join(PLUGIN_DIR, 'metadata.txt')
    assert os.path.exists(path), "metadata.txt missing"


def test_metadata_required_fields():
    import configparser
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(PLUGIN_DIR, 'metadata.txt'))
    g = cfg['general']
    for field in ['name', 'qgisMinimumVersion', 'description', 'version', 'author']:
        assert field in g, f"metadata.txt missing: {field}"
    assert g['name'] == 'Bhumi3DMapper'
    assert int(g['qgisMinimumVersion'].split('.')[0]) >= 3


def test_init_py_exists():
    assert os.path.exists(os.path.join(PLUGIN_DIR, '__init__.py'))


def test_icon_exists():
    assert os.path.exists(os.path.join(PLUGIN_DIR, 'icon.png')), \
        "icon.png missing — create a 48x48 PNG"


def test_core_modules_present():
    for fname in ['config.py']:
        assert os.path.exists(os.path.join(PLUGIN_DIR, 'core', fname)), \
            f"core/{fname} missing — copy from ProspectivityMapper_Framework"


def test_processing_modules_present():
    for fname in ['m01_data_loader.py', 'm02_drill_processor.py',
                  'm03_geophys_processor.py', 'm04_scoring_engine.py',
                  'm05_gpkg_writer.py', 'm06_voxel_builder.py']:
        assert os.path.exists(os.path.join(PLUGIN_DIR, 'modules', fname)), \
            f"modules/{fname} missing — copy from ProspectivityMapper_Framework"


def test_algorithms_present():
    for fname in ['alg_load_data.py', 'alg_run_scoring.py',
                  'alg_gpkg_export.py', 'alg_voxel_build.py',
                  'alg_load_results.py']:
        assert os.path.exists(os.path.join(PLUGIN_DIR, 'algorithms', fname)), \
            f"algorithms/{fname} missing"


def test_ui_present():
    for fname in ['dock_panel.py', 'config_widget.py', 'wizard.py']:
        assert os.path.exists(os.path.join(PLUGIN_DIR, 'ui', fname)), \
            f"ui/{fname} missing"


def test_no_pyqt5_imports():
    """CRITICAL: all Qt imports must use qgis.PyQt for dual Qt5/Qt6 compat."""
    bad = re.compile(r'^from PyQt5|^import PyQt5|^from PyQt6|^import PyQt6',
                     re.MULTILINE)
    for root, dirs, files in os.walk(PLUGIN_DIR):
        dirs[:] = [d for d in dirs if d not in ('test', '__pycache__', '.git')]
        for fname in files:
            if fname.endswith('.py'):
                content = open(os.path.join(root, fname), encoding='utf-8').read()
                matches = bad.findall(content)
                assert not matches, \
                    f"{fname} contains PyQt5/6 direct import — use qgis.PyQt instead"
