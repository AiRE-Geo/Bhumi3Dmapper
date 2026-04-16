# -*- coding: utf-8 -*-
"""Sprint 6 — Full pipeline integration test without QGIS."""
import os
import sys
import sqlite3
import pytest
import numpy as np

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)


@pytest.fixture(scope='module')
def synthetic_data_mod(tmp_path_factory):
    """Module-scoped synthetic data for integration tests."""
    import csv
    from PIL import Image
    tmp = tmp_path_factory.mktemp('synth')

    collar = tmp / 'collar.csv'
    with open(collar, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['BHID', 'XCOLLAR', 'YCOLLAR', 'ZCOLLAR', 'DEPTH'])
        w.writerow(['KYD001', 469500, 2934900, 460, 250])
        w.writerow(['KYD002', 469600, 2935000, 455, 200])

    litho = tmp / 'litho.csv'
    with open(litho, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['BHID', 'FROM', 'TO', 'WIDTH', 'ROCKCODE'])
        w.writerow(['KYD001', 0, 50, 50, 'QMS'])
        w.writerow(['KYD001', 50, 100, 50, 'PG'])
        w.writerow(['KYD001', 100, 150, 50, 'CSR'])
        w.writerow(['KYD001', 150, 250, 100, 'QMS'])
        w.writerow(['KYD002', 0, 200, 200, 'QMS'])

    assay = tmp / 'assay.csv'
    with open(assay, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['BHID', 'FROM', 'TO', 'WIDTH', 'ZN', 'PB'])
        w.writerow(['KYD001', 0, 10, 10, 12.5, 1.2])

    grav_dir = tmp / 'gravity'
    grav_dir.mkdir()
    for mrl in [185, 210, 235]:
        a = np.random.uniform(-0.2, 0.5, (50, 50)).astype(np.float32)
        Image.fromarray(a, mode='F').save(str(grav_dir / f'gravity_{mrl}.tif'))

    mag_dir = tmp / 'magnetics'
    mag_dir.mkdir()
    for mrl in [185, 210, 235]:
        a = np.random.uniform(-50, 100, (10, 10)).astype(np.float32)
        Image.fromarray(a / 1e4, mode='F').save(str(mag_dir / f'mag_{mrl}.tif'))

    return {
        'collar': str(collar), 'litho': str(litho), 'assay': str(assay),
        'grav_dir': str(grav_dir), 'mag_dir': str(mag_dir),
    }


@pytest.fixture(scope='module')
def full_pipeline_output(tmp_path_factory, synthetic_data_mod):
    """Run full pipeline on 3 mRL levels and return output dir."""
    tmp = tmp_path_factory.mktemp('pipeline')
    from core.config import ProjectConfig
    from modules.m01_data_loader import DataLoader
    from modules.m02_drill_processor import DrillProcessor
    from modules.m03_geophys_processor import GeophysicsProcessor
    from modules.m04_scoring_engine import compute_proximity, compute_blind
    from modules.m05_gpkg_writer import write_level_gpkg

    cfg = ProjectConfig(project_name='IntegrationTest', crs_epsg=32643)
    cfg.drill.collar_csv = synthetic_data_mod['collar']
    cfg.drill.litho_csv = synthetic_data_mod['litho']
    cfg.drill.assay_csv = synthetic_data_mod['assay']
    cfg.geophysics.gravity_folder = synthetic_data_mod['grav_dir']
    cfg.geophysics.magnetics_folder = synthetic_data_mod['mag_dir']
    cfg.geophysics.gravity_pixel_size_m = 5.0
    cfg.geophysics.magnetics_pixel_size_m = 30.0
    cfg.grid.xmin = 469490.0
    cfg.grid.ymin = 2934890.0
    cfg.grid.nx = 50
    cfg.grid.ny = 50
    cfg.grid.z_top_mrl = 235.0
    cfg.grid.z_bot_mrl = 185.0
    cfg.grid.dz_m = 25.0
    cfg.outputs.output_dir = str(tmp)
    cfg.outputs.project_name = 'IntegrationTest'

    # Save config
    config_path = str(tmp / 'config.json')
    cfg.to_json(config_path)

    # Run pipeline
    loader = DataLoader(cfg)
    collar_df = loader.load_collar()
    litho_df = loader.load_litho()
    grav_grids = loader.load_gravity()
    mag_grids = loader.load_magnetics()

    dp = DrillProcessor(cfg)
    dp.build_lookups(collar_df, litho_df)

    gp = GeophysicsProcessor(cfg)
    gp.load(grav_grids, mag_grids)

    # Cell coords
    cols = np.arange(cfg.grid.nx)
    rows = np.arange(cfg.grid.ny)
    CC, CR = np.meshgrid(cols, rows)
    cell_E = (cfg.grid.xmin + (CC + 0.5) * cfg.grid.cell_size_m).ravel().astype(np.float32)
    cell_N = (cfg.grid.ymin + (CR + 0.5) * cfg.grid.cell_size_m).ravel().astype(np.float32)
    all_ore_E = np.array([469500.0], dtype=np.float32)
    all_ore_N = np.array([2934900.0], dtype=np.float32)
    dE = cell_E[:, None] - all_ore_E[None, :]
    dN = cell_N[:, None] - all_ore_N[None, :]
    dist_ore = np.sqrt(dE**2 + dN**2).min(axis=1).astype(np.float32)

    gpkg_paths = []
    for z in [185.0, 210.0, 235.0]:
        gf = gp.at_level(z)
        lv, pg, csr = dp.geology_at_level(z)
        inputs = {
            'lv': lv, 'pg': pg, 'csr': csr,
            'grav': gf['grav'], 'grav_raw': gf.get('grav_raw', gf['grav']),
            'grav_gradient': gf['grav_gradient'],
            'grav_laplacian': gf['grav_laplacian'],
            'mag': gf['mag'], 'mag_gradient': gf['mag_gradient'],
            'cell_E': cell_E, 'cell_N': cell_N,
            'z_mrl': z, 'regime_id': 2,
            'dist_ore': dist_ore, 'ore_area': 30000.0,
            'grav_mean': gf['grav_mean'], 'grav_std': gf['grav_std'],
            'mag_mean': gf['mag_mean'], 'mag_std': gf['mag_std'],
            'gg_mean': gf['gg_mean'], 'gg_std': gf['gg_std'],
            'lap_std': gf['lap_std'], 'mg_p50': gf['mg_p50'],
            'block_model_df': None,
        }
        prox = compute_proximity(inputs, cfg)
        blind = compute_blind(inputs, cfg)
        geo = {**gf, 'lv': lv, 'pg': pg, 'csr': csr,
               'dist_ore': dist_ore, 'regime_id': 2}
        path = str(tmp / f'IntegrationTest_Prospectivity_mRL{int(z):+04d}.gpkg')
        write_level_gpkg(path, z, prox, blind, geo, cell_E, cell_N, cfg)
        gpkg_paths.append(path)

    return {'config_path': config_path, 'output_dir': str(tmp),
            'gpkg_paths': gpkg_paths, 'cfg': cfg}


def test_pipeline_creates_3_gpkgs(full_pipeline_output):
    for path in full_pipeline_output['gpkg_paths']:
        assert os.path.exists(path), f"GPKG not created: {path}"


def test_pipeline_gpkgs_have_correct_cell_count(full_pipeline_output):
    cfg = full_pipeline_output['cfg']
    expected = cfg.grid.nx * cfg.grid.ny
    for path in full_pipeline_output['gpkg_paths']:
        con = sqlite3.connect(path)
        tables = [r[0] for r in con.execute(
            "SELECT table_name FROM gpkg_contents").fetchall()]
        count = con.execute(f"SELECT COUNT(*) FROM [{tables[0]}]").fetchone()[0]
        assert count == expected, f"{path}: expected {expected} cells, got {count}"
        con.close()


def test_pipeline_scores_are_valid(full_pipeline_output):
    for path in full_pipeline_output['gpkg_paths']:
        con = sqlite3.connect(path)
        tables = [r[0] for r in con.execute(
            "SELECT table_name FROM gpkg_contents").fetchall()]
        rows = con.execute(
            f"SELECT prox_score, blind_score FROM [{tables[0]}]").fetchall()
        for ps, bs in rows:
            assert 0 <= ps <= 100
            assert 0 <= bs <= 100
        con.close()


def test_pipeline_amphibolite_veto(full_pipeline_output):
    """All amphibolite cells must be capped at score 20."""
    for path in full_pipeline_output['gpkg_paths']:
        con = sqlite3.connect(path)
        tables = [r[0] for r in con.execute(
            "SELECT table_name FROM gpkg_contents").fetchall()]
        bad = con.execute(
            f"SELECT COUNT(*) FROM [{tables[0]}] "
            f"WHERE litho_code=2 AND prox_score > 20").fetchone()[0]
        assert bad == 0, f"{path}: {bad} amphibolite cells have prox_score > 20"
        con.close()


def test_pipeline_config_json_saved(full_pipeline_output):
    import json
    with open(full_pipeline_output['config_path']) as f:
        data = json.load(f)
    assert data['project_name'] == 'IntegrationTest'
    assert data['crs_epsg'] == 32643
