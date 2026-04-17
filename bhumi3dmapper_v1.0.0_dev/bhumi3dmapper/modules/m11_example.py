# -*- coding: utf-8 -*-
"""
Module 11 — Example Project Loader
====================================
Copies the bundled synthetic SEDEX example project to a user-chosen location
and returns the path to config.json so the wizard can load and run it.

Pure Python, no QGIS imports.
"""
import os
import shutil
from typing import Optional

EXAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'examples', 'kayad_synthetic')


def copy_example_project(target_dir: str, folder_name: str = 'bhumi3d_example') -> str:
    """
    Copy the bundled example to target_dir/folder_name.
    Returns absolute path to config.json inside the copy.
    """
    if not os.path.isdir(EXAMPLE_DIR):
        raise FileNotFoundError(
            f"Example data not bundled with plugin: {EXAMPLE_DIR}")

    target = os.path.join(target_dir, folder_name)
    if os.path.exists(target):
        # Remove existing to avoid stale files
        shutil.rmtree(target)
    shutil.copytree(EXAMPLE_DIR, target)

    # Rewrite config.json with absolute paths so it works from any target location
    config_path = os.path.join(target, 'config.json')
    _rewrite_config_paths(config_path, target)
    return config_path


def _rewrite_config_paths(config_path: str, example_root: str):
    """Replace relative paths in config.json with absolute paths."""
    import json
    with open(config_path) as f:
        cfg = json.load(f)
    # Expected relative paths in the template
    cfg['drill']['collar_csv']         = os.path.join(example_root, 'data', 'collar.csv')
    cfg['drill']['litho_csv']          = os.path.join(example_root, 'data', 'litho.csv')
    cfg['drill']['assay_csv']          = os.path.join(example_root, 'data', 'assay.csv')
    cfg['drill']['survey_csv']         = os.path.join(example_root, 'data', 'survey.csv')
    cfg['geophysics']['gravity_folder']   = os.path.join(example_root, 'geophysics', 'gravity')
    cfg['geophysics']['magnetics_folder'] = os.path.join(example_root, 'geophysics', 'magnetics')
    cfg['outputs']['output_dir']       = os.path.join(example_root, 'outputs')
    cfg['outputs']['project_name']     = 'Bhumi3D_Example_DO_NOT_USE_FOR_REAL'
    with open(config_path, 'w') as f:
        json.dump(cfg, f, indent=2)


def is_example_output(output_path: str) -> bool:
    """Check if a given output GPKG was produced from the example project."""
    name = os.path.basename(output_path).lower()
    return 'example' in name or 'do_not_use' in name


def example_banner_text() -> str:
    """Return the banner text to prepend to example outputs."""
    return "⚠️ EXAMPLE DATA — NOT YOUR PROJECT"
