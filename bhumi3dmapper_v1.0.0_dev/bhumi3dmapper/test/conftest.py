# -*- coding: utf-8 -*-
"""Shared pytest fixtures — no QGIS dependency."""
import os
import sys
import csv
import pytest
import numpy as np
from PIL import Image

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)


@pytest.fixture
def kayad_config():
    """Minimal valid config matching Kayad project."""
    from core.config import ProjectConfig
    cfg = ProjectConfig(
        project_name='Kayad Test',
        deposit_type='SEDEX Pb-Zn',
        location='Ajmer, Rajasthan, India',
        crs_epsg=32643,
    )
    cfg.grid.xmin = 468655.0
    cfg.grid.ymin = 2932890.0
    cfg.grid.nx = 482
    cfg.grid.ny = 722
    cfg.grid.cell_size_m = 5.0
    cfg.grid.z_top_mrl = 460.0
    cfg.grid.z_bot_mrl = -260.0
    cfg.grid.dz_m = 5.0
    return cfg


@pytest.fixture
def tmp_config_path(tmp_path, kayad_config):
    path = str(tmp_path / 'test_config.json')
    kayad_config.to_json(path)
    return path


@pytest.fixture
def synthetic_data(tmp_path):
    """Create minimal valid synthetic Kayad-style inputs."""
    # Collar CSV
    collar = tmp_path / 'collar.csv'
    with open(collar, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['BHID', 'XCOLLAR', 'YCOLLAR', 'ZCOLLAR', 'DEPTH'])
        w.writerow(['KYD001', 469500, 2934900, 460, 250])
        w.writerow(['KYD002', 469600, 2935000, 455, 200])

    # Litho CSV
    litho = tmp_path / 'litho.csv'
    with open(litho, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['BHID', 'FROM', 'TO', 'WIDTH', 'ROCKCODE'])
        w.writerow(['KYD001', 0, 50, 50, 'QMS'])
        w.writerow(['KYD001', 50, 100, 50, 'PG'])
        w.writerow(['KYD001', 100, 150, 50, 'CSR'])
        w.writerow(['KYD001', 150, 250, 100, 'QMS'])
        w.writerow(['KYD002', 0, 200, 200, 'QMS'])

    # Assay CSV
    assay = tmp_path / 'assay.csv'
    with open(assay, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['BHID', 'FROM', 'TO', 'WIDTH', 'ZN', 'PB'])
        w.writerow(['KYD001', 0, 10, 10, 12.5, 1.2])
        w.writerow(['KYD001', 10, 20, 10, 8.3, 0.8])

    # Gravity TIFs (small 50×50, 3 levels)
    grav_dir = tmp_path / 'gravity'
    grav_dir.mkdir()
    for mrl in [185, 210, 235]:
        arr = np.random.uniform(-0.2, 0.5, (50, 50)).astype(np.float32)
        img = Image.fromarray(arr, mode='F')
        img.save(str(grav_dir / f'gravity_{mrl}.tif'))

    # Magnetics TIFs
    mag_dir = tmp_path / 'magnetics'
    mag_dir.mkdir()
    for mrl in [185, 210, 235]:
        arr = np.random.uniform(-50, 100, (10, 10)).astype(np.float32)
        img = Image.fromarray(arr / 1e4, mode='F')
        img.save(str(mag_dir / f'mag_{mrl}.tif'))

    return {
        'collar': str(collar),
        'litho': str(litho),
        'assay': str(assay),
        'grav_dir': str(grav_dir),
        'mag_dir': str(mag_dir),
    }


@pytest.fixture
def configured_config(synthetic_data, tmp_path):
    from core.config import ProjectConfig
    cfg = ProjectConfig(project_name='SyntheticTest')
    cfg.drill.collar_csv = synthetic_data['collar']
    cfg.drill.litho_csv = synthetic_data['litho']
    cfg.drill.assay_csv = synthetic_data['assay']
    cfg.geophysics.gravity_folder = synthetic_data['grav_dir']
    cfg.geophysics.magnetics_folder = synthetic_data['mag_dir']
    cfg.grid.nx = 50
    cfg.grid.ny = 50
    return cfg
