#!/usr/bin/env python3
"""
Bhumi3DMapper — Self-contained test runner (no pytest needed).
Runs all sprint tests using unittest discovery + direct function calls.
"""
import os, sys, json, re, csv, sqlite3, tempfile, traceback, time
import numpy as np
from PIL import Image

PLUGIN_DIR = os.path.join(os.path.dirname(__file__), 'bhumi3dmapper')
sys.path.insert(0, PLUGIN_DIR)

passed = 0
failed = 0
errors = []

def test(name):
    """Decorator to register and run a test function."""
    global passed, failed
    try:
        name_str = name.__name__
        name()
        passed += 1
        print(f"  ✓ {name_str}")
    except AssertionError as e:
        failed += 1
        errors.append((name.__name__, str(e)))
        print(f"  ✗ {name.__name__}: {e}")
    except Exception as e:
        failed += 1
        errors.append((name.__name__, traceback.format_exc()))
        print(f"  ✗ {name.__name__}: {type(e).__name__}: {e}")

def make_kayad_config():
    from core.config import ProjectConfig
    cfg = ProjectConfig(
        project_name='Kayad Test', deposit_type='SEDEX Pb-Zn',
        location='Ajmer, Rajasthan, India', crs_epsg=32643)
    cfg.grid.xmin = 468655.0; cfg.grid.ymin = 2932890.0
    cfg.grid.nx = 482; cfg.grid.ny = 722
    cfg.grid.cell_size_m = 5.0; cfg.grid.z_top_mrl = 460.0
    cfg.grid.z_bot_mrl = -260.0; cfg.grid.dz_m = 5.0
    return cfg

def make_synthetic_data(tmp_dir):
    collar = os.path.join(tmp_dir, 'collar.csv')
    with open(collar, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['BHID','XCOLLAR','YCOLLAR','ZCOLLAR','DEPTH'])
        w.writerow(['KYD001',469500,2934900,460,250])
        w.writerow(['KYD002',469600,2935000,455,200])
    litho = os.path.join(tmp_dir, 'litho.csv')
    with open(litho, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['BHID','FROM','TO','WIDTH','ROCKCODE'])
        w.writerow(['KYD001',0,50,50,'QMS']); w.writerow(['KYD001',50,100,50,'PG'])
        w.writerow(['KYD001',100,150,50,'CSR']); w.writerow(['KYD001',150,250,100,'QMS'])
        w.writerow(['KYD002',0,200,200,'QMS'])
    assay = os.path.join(tmp_dir, 'assay.csv')
    with open(assay, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['BHID','FROM','TO','WIDTH','ZN','PB'])
        w.writerow(['KYD001',0,10,10,12.5,1.2])
    grav_dir = os.path.join(tmp_dir, 'gravity'); os.makedirs(grav_dir, exist_ok=True)
    mag_dir = os.path.join(tmp_dir, 'magnetics'); os.makedirs(mag_dir, exist_ok=True)
    for mrl in [185, 210, 235]:
        a = np.random.uniform(-0.2, 0.5, (50,50)).astype(np.float32)
        Image.fromarray(a, mode='F').save(os.path.join(grav_dir, f'gravity_{mrl}.tif'))
        a = np.random.uniform(-50, 100, (10,10)).astype(np.float32)
        Image.fromarray(a/1e4, mode='F').save(os.path.join(mag_dir, f'mag_{mrl}.tif'))
    return {'collar':collar,'litho':litho,'assay':assay,'grav_dir':grav_dir,'mag_dir':mag_dir}

# ══════════════════════════════════════════════════════════════════════════
print("\n═══ SPRINT 1 — Plugin Skeleton ═══")

@test
def test_metadata_exists():
    assert os.path.exists(os.path.join(PLUGIN_DIR, 'metadata.txt'))

@test
def test_metadata_fields():
    import configparser
    c = configparser.ConfigParser()
    c.read(os.path.join(PLUGIN_DIR, 'metadata.txt'))
    g = c['general']
    for f in ['name','qgisMinimumVersion','description','version','author']:
        assert f in g, f"missing: {f}"
    assert g['name'] == 'Bhumi3DMapper'
    assert int(g['qgisMinimumVersion'].split('.')[0]) >= 3

@test
def test_init_exists():
    assert os.path.exists(os.path.join(PLUGIN_DIR, '__init__.py'))

@test
def test_icon_exists():
    assert os.path.exists(os.path.join(PLUGIN_DIR, 'icon.png'))

@test
def test_core_modules_present():
    assert os.path.exists(os.path.join(PLUGIN_DIR, 'core', 'config.py'))

@test
def test_processing_modules_present():
    for f in ['m01_data_loader.py','m02_drill_processor.py','m03_geophys_processor.py',
              'm04_scoring_engine.py','m05_gpkg_writer.py','m06_voxel_builder.py']:
        assert os.path.exists(os.path.join(PLUGIN_DIR, 'modules', f)), f"missing: {f}"

@test
def test_algorithms_present():
    for f in ['alg_load_data.py','alg_run_scoring.py','alg_gpkg_export.py',
              'alg_voxel_build.py','alg_load_results.py']:
        assert os.path.exists(os.path.join(PLUGIN_DIR, 'algorithms', f)), f"missing: {f}"

@test
def test_ui_present():
    for f in ['dock_panel.py','config_widget.py','wizard.py']:
        assert os.path.exists(os.path.join(PLUGIN_DIR, 'ui', f)), f"missing: {f}"

@test
def test_no_pyqt5_imports():
    bad = re.compile(r'^from PyQt5|^import PyQt5|^from PyQt6|^import PyQt6', re.MULTILINE)
    for root, dirs, files in os.walk(PLUGIN_DIR):
        dirs[:] = [d for d in dirs if d not in ('test','__pycache__','.git')]
        for fn in files:
            if fn.endswith('.py'):
                content = open(os.path.join(root, fn), encoding='utf-8').read()
                m = bad.findall(content)
                assert not m, f"{fn} has forbidden import: {m[0]}"

# ══════════════════════════════════════════════════════════════════════════
print("\n═══ SPRINT 2 — Configuration ═══")
cfg = make_kayad_config()

@test
def test_config_default():
    from core.config import ProjectConfig
    c = ProjectConfig()
    assert c.project_name == 'Unnamed Project'
    assert c.grid.cell_size_m == 5.0

@test
def test_config_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 'cfg.json')
        cfg.to_json(p)
        assert os.path.exists(p)
        from core.config import ProjectConfig
        loaded = ProjectConfig.from_json(p)
        assert loaded.project_name == 'Kayad Test'
        assert loaded.crs_epsg == 32643
        assert loaded.grid.nx == 482

@test
def test_config_z_levels():
    levels = cfg.grid.z_levels
    assert levels[0] == -260.0
    assert levels[-1] == 460.0
    assert len(levels) == 145

@test
def test_config_cells():
    assert cfg.grid.n_cells_per_level == 482 * 722

@test
def test_scoring_weights_sum():
    w = cfg.scoring
    ps = sum(w.proximity.values()); bs = sum(w.blind.values())
    assert abs(ps - 11.0) < 0.01, f"prox sum={ps}"
    assert abs(bs - 12.0) < 0.01, f"blind sum={bs}"

@test
def test_config_missing_raises():
    from core.config import ProjectConfig
    try:
        ProjectConfig.from_json('/nonexistent/path.json')
        assert False, "Should have raised"
    except (FileNotFoundError, OSError):
        pass

@test
def test_config_partial():
    from core.config import ProjectConfig
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 'partial.json')
        with open(p, 'w') as f: json.dump({'project_name':'Partial'}, f)
        c = ProjectConfig.from_json(p)
        assert c.project_name == 'Partial'
        assert c.grid.cell_size_m == 5.0

# ══════════════════════════════════════════════════════════════════════════
print("\n═══ SPRINT 3 — Scoring Engine ═══")
from modules.m04_scoring_engine import (
    score_lithology, score_pg_halo, score_footwall_standoff,
    score_gravity_absolute, score_gravity_contextual,
    score_mag_absolute, score_mag_contextual,
    score_structural_corridor, score_plunge_proximity,
    score_gravity_gradient, score_mag_gradient,
    score_gravity_laplacian, score_novelty,
    compute_proximity, compute_blind, apply_hard_veto, score_to_class
)
def arr(*v): return np.array(v, dtype=np.float32)

@test
def test_litho_qms_upper():
    s = score_lithology(arr(1,1,1), 2, cfg)
    assert np.allclose(s, 1.0)

@test
def test_litho_amphibolite_zero():
    for r in [0,1,2]:
        s = score_lithology(arr(2), r, cfg)
        assert s[0] == 0.0, f"regime={r}"

@test
def test_litho_csr_lower():
    s = score_lithology(arr(4), 0, cfg)
    assert s[0] == 1.0

@test
def test_pg_halo_peak():
    s = score_pg_halo(arr(5.0,7.0,9.0), regime_id=2)
    assert np.all(s == 1.0)

@test
def test_pg_halo_inactive_lower():
    s = score_pg_halo(arr(5.0,100.0), regime_id=0)
    assert np.allclose(s, 0.4)

@test
def test_csr_standoff_upper():
    s = score_footwall_standoff(arr(15.0,25.0,35.0), regime_id=2)
    assert np.all(s == 1.0)

@test
def test_csr_contact_lower():
    s = score_footwall_standoff(arr(2.0,4.0), regime_id=0)
    assert np.all(s == 1.0)

@test
def test_gravity_negative_wins():
    s = score_gravity_absolute(arr(-0.15,-0.05,0.0,0.5), z_mrl=310.0)
    assert s[0] > s[1] > s[2] > s[3]

@test
def test_gravity_contextual():
    s = score_gravity_contextual(arr(-2.0,0.0,2.0), grav_mean=0.0, grav_std=1.0)
    assert s[0] > s[1] > s[2]

@test
def test_mag_minimum():
    s = score_mag_absolute(arr(-15.0,-5.0,5.0,50.0))
    assert s[0] > s[1] > s[2] > s[3]

@test
def test_mag_contextual():
    s = score_mag_contextual(arr(-20.0,0.0,20.0), mag_mean=0.0, mag_std=10.0)
    assert s[0] > s[1] > s[2]

@test
def test_corridor_near():
    E = np.array([469519.0], dtype=np.float32)
    N = np.array([2934895.0], dtype=np.float32)
    s, _, _ = score_structural_corridor(E, N, 185.0, cfg, 2)
    assert s[0] >= 0.8, f"got {s[0]}"

@test
def test_hard_veto():
    lv = arr(2,1,1); scores = arr(95.0,90.0,85.0)
    r = apply_hard_veto(scores, lv, cfg)
    assert r[0] <= 20.0; assert r[1] == 90.0

@test
def test_score_classes():
    scores = arr(80.0,65.0,50.0,35.0,20.0)
    cl = score_to_class(scores, cfg)
    assert list(cl) == [4,3,2,1,0]

@test
def test_laplacian_negative_high():
    s = score_gravity_laplacian(arr(-0.001,0.0,0.001), lap_std=0.0005)
    assert s[0] > s[1] > s[2]

@test
def test_novelty_decreases():
    s = score_novelty(arr(1000.0,500.0,200.0,50.0), cfg)
    assert s[0] > s[1] > s[2] > s[3]

@test
def test_proximity_in_range():
    n = 10
    E = np.full(n, 469500.0, dtype=np.float32)
    N = np.full(n, 2934900.0, dtype=np.float32)
    inputs = {
        'lv': np.ones(n, dtype=np.uint8), 'pg': np.full(n,6.0,dtype=np.float32),
        'csr': np.full(n,20.0,dtype=np.float32),
        'grav': np.full(n,-0.05,dtype=np.float32),
        'grav_raw': np.full(n,-0.05,dtype=np.float32),
        'grav_gradient': np.full(n,0.0005,dtype=np.float32),
        'grav_laplacian': np.full(n,-0.0001,dtype=np.float32),
        'mag': np.full(n,-5.0,dtype=np.float32),
        'mag_gradient': np.full(n,0.05,dtype=np.float32),
        'cell_E':E, 'cell_N':N, 'z_mrl':185.0, 'regime_id':2,
        'dist_ore': np.full(n,50.0,dtype=np.float32), 'ore_area':30000.0,
        'grav_mean':0.0,'grav_std':0.05,'mag_mean':5.0,'mag_std':15.0,
        'gg_mean':0.0003,'gg_std':0.0002,'lap_std':0.00005,'mg_p50':0.04,
        'block_model_df':None,
    }
    r = compute_proximity(inputs, cfg)
    assert 0 <= r['score'].min() <= r['score'].max() <= 100
    b = compute_blind(inputs, cfg)
    assert 0 <= b['score'].min() <= b['score'].max() <= 100

# ══════════════════════════════════════════════════════════════════════════
print("\n═══ SPRINT 4 — Data Loader ═══")
with tempfile.TemporaryDirectory() as TMP:
    SD = make_synthetic_data(TMP)
    from core.config import ProjectConfig as PC
    from modules.m01_data_loader import DataLoader

    ccfg = PC(project_name='SyntheticTest')
    ccfg.drill.collar_csv = SD['collar']; ccfg.drill.litho_csv = SD['litho']
    ccfg.drill.assay_csv = SD['assay']
    ccfg.geophysics.gravity_folder = SD['grav_dir']
    ccfg.geophysics.magnetics_folder = SD['mag_dir']
    ccfg.grid.nx = 50; ccfg.grid.ny = 50

    @test
    def test_collar_loads():
        loader = DataLoader(ccfg)
        df = loader.load_collar()
        assert len(df) == 2
        assert 'XCOLLAR' in df.columns

    @test
    def test_litho_loads():
        loader = DataLoader(ccfg)
        df = loader.load_litho()
        assert len(df) > 0
        assert 'lcode' in df.columns
        assert 1 in df['lcode'].values

    @test
    def test_gravity_loads():
        loader = DataLoader(ccfg)
        grids = loader.load_gravity()
        assert len(grids) == 3
        assert 185 in grids
        assert grids[185].shape == (50, 50)

    @test
    def test_validation_passes():
        loader = DataLoader(ccfg)
        assert loader.validate_all() is True

    @test
    def test_validation_fails_bad_path():
        from core.config import ProjectConfig
        bad = ProjectConfig()
        bad.drill.collar_csv = '/nonexistent/collar.csv'
        loader = DataLoader(bad)
        assert loader.validate_all() is False

# ══════════════════════════════════════════════════════════════════════════
print("\n═══ SPRINT 5 — GeoPackage Writer ═══")
with tempfile.TemporaryDirectory() as TMP:
    from modules.m05_gpkg_writer import write_level_gpkg
    n = 25
    cE = np.array([469500.0+(i%5)*5 for i in range(n)], dtype=np.float32)
    cN = np.array([2934900.0+(i//5)*5 for i in range(n)], dtype=np.float32)
    geo = {'lv':np.ones(n,dtype=np.uint8),'pg':np.full(n,6.0,dtype=np.float32),
           'csr':np.full(n,20.0,dtype=np.float32),'grav':np.full(n,-0.05,dtype=np.float32),
           'grav_raw':np.full(n,-0.05,dtype=np.float32),
           'grav_gradient':np.full(n,0.0005,dtype=np.float32),
           'grav_laplacian':np.full(n,-0.0001,dtype=np.float32),
           'mag':np.full(n,-5.0,dtype=np.float32),'mag_gradient':np.full(n,0.05,dtype=np.float32),
           'dist_ore':np.linspace(10,1000,n).astype(np.float32),'regime_id':2,
           'grav_mean':0.0,'grav_std':0.05,'mag_mean':5.0,'mag_std':15.0,
           'gg_mean':0.0003,'gg_std':0.0002,'lap_std':0.00005,'mg_p50':0.04}
    prox = {'c1':np.ones(n,dtype=np.float32),'c2':np.full(n,0.8,dtype=np.float32),
            'c3':np.full(n,0.9,dtype=np.float32),'c4':np.full(n,0.75,dtype=np.float32),
            'c5':np.full(n,0.7,dtype=np.float32),'c6':np.full(n,0.95,dtype=np.float32),
            'c7':np.full(n,0.85,dtype=np.float32),'c9':np.full(n,0.75,dtype=np.float32),
            'c10':np.full(n,0.8,dtype=np.float32),
            'score':np.full(n,82.5,dtype=np.float32),'class':np.full(n,4,dtype=np.uint8)}
    blind = {'c1':np.ones(n,dtype=np.float32),'c2':np.full(n,0.8,dtype=np.float32),
             'c3':np.full(n,0.9,dtype=np.float32),'c4':np.full(n,0.7,dtype=np.float32),
             'c5':np.full(n,0.65,dtype=np.float32),'c6':np.full(n,0.95,dtype=np.float32),
             'c7b':np.full(n,0.75,dtype=np.float32),'c8':np.full(n,0.7,dtype=np.float32),
             'c9_lap':np.full(n,0.8,dtype=np.float32),'c10':np.full(n,0.6,dtype=np.float32),
             'score':np.full(n,79.0,dtype=np.float32),'class':np.full(n,3,dtype=np.uint8)}

    gpkg_path = os.path.join(TMP, 'test_mRL+185.gpkg')
    write_level_gpkg(gpkg_path, 185.0, prox, blind, geo, cE, cN, cfg)

    @test
    def test_gpkg_created():
        assert os.path.exists(gpkg_path)
        assert os.path.getsize(gpkg_path) > 1000

    @test
    def test_gpkg_valid_sqlite():
        con = sqlite3.connect(gpkg_path)
        tables = [r[0] for r in con.execute("SELECT table_name FROM gpkg_contents").fetchall()]
        assert len(tables) > 0
        con.close()

    @test
    def test_gpkg_geometry():
        con = sqlite3.connect(gpkg_path)
        rows = con.execute("SELECT * FROM gpkg_geometry_columns").fetchall()
        assert len(rows) > 0
        con.close()

    @test
    def test_gpkg_row_count():
        con = sqlite3.connect(gpkg_path)
        tables = [r[0] for r in con.execute("SELECT table_name FROM gpkg_contents").fetchall()]
        count = con.execute(f"SELECT COUNT(*) FROM [{tables[0]}]").fetchone()[0]
        assert count == 25, f"got {count}"
        con.close()

    @test
    def test_gpkg_fields():
        con = sqlite3.connect(gpkg_path)
        tables = [r[0] for r in con.execute("SELECT table_name FROM gpkg_contents").fetchall()]
        cols = [r[1] for r in con.execute(f"PRAGMA table_info([{tables[0]}])").fetchall()]
        for f in ['prox_score','blind_score','prox_class_id','blind_class_id',
                   'litho_code','litho_name','regime_name','dist_ore_m']:
            assert f in cols, f"missing: {f}"
        con.close()

    @test
    def test_gpkg_score_range():
        con = sqlite3.connect(gpkg_path)
        tables = [r[0] for r in con.execute("SELECT table_name FROM gpkg_contents").fetchall()]
        rows = con.execute(f"SELECT prox_score, blind_score FROM [{tables[0]}]").fetchall()
        for ps, bs in rows:
            assert 0 <= ps <= 100; assert 0 <= bs <= 100
        con.close()

    @test
    def test_gpkg_novel_target():
        con = sqlite3.connect(gpkg_path)
        tables = [r[0] for r in con.execute("SELECT table_name FROM gpkg_contents").fetchall()]
        rows = con.execute(f"SELECT dist_ore_m, novel_target FROM [{tables[0]}]").fetchall()
        for dist, novel in rows:
            if dist > 500: assert novel == 1, f"dist={dist}"
            else: assert novel == 0, f"dist={dist}"
        con.close()

    @test
    def test_gpkg_srs():
        con = sqlite3.connect(gpkg_path)
        srids = [r[0] for r in con.execute("SELECT srs_id FROM gpkg_spatial_ref_sys").fetchall()]
        assert 32643 in srids
        con.close()

# ══════════════════════════════════════════════════════════════════════════
print("\n═══ SPRINT 6 — Integration (Full Pipeline) ═══")
with tempfile.TemporaryDirectory() as TMP:
    SD = make_synthetic_data(TMP)
    from core.config import ProjectConfig
    from modules.m01_data_loader import DataLoader
    from modules.m02_drill_processor import DrillProcessor
    from modules.m03_geophys_processor import GeophysicsProcessor
    from modules.m04_scoring_engine import compute_proximity, compute_blind
    from modules.m05_gpkg_writer import write_level_gpkg

    icfg = ProjectConfig(project_name='IntegrationTest', crs_epsg=32643)
    icfg.drill.collar_csv = SD['collar']; icfg.drill.litho_csv = SD['litho']
    icfg.drill.assay_csv = SD['assay']
    icfg.geophysics.gravity_folder = SD['grav_dir']
    icfg.geophysics.magnetics_folder = SD['mag_dir']
    icfg.geophysics.gravity_pixel_size_m = 5.0
    icfg.geophysics.magnetics_pixel_size_m = 30.0
    icfg.grid.xmin = 469490.0; icfg.grid.ymin = 2934890.0
    icfg.grid.nx = 50; icfg.grid.ny = 50
    icfg.grid.z_top_mrl = 235.0; icfg.grid.z_bot_mrl = 185.0; icfg.grid.dz_m = 25.0
    icfg.outputs.output_dir = TMP; icfg.outputs.project_name = 'IntegrationTest'

    config_path = os.path.join(TMP, 'config.json')
    icfg.to_json(config_path)

    loader = DataLoader(icfg)
    collar_df = loader.load_collar(); litho_df = loader.load_litho()
    grav_grids = loader.load_gravity(); mag_grids = loader.load_magnetics()

    dp = DrillProcessor(icfg); dp.build_lookups(collar_df, litho_df)
    gp = GeophysicsProcessor(icfg); gp.load(grav_grids, mag_grids)

    cols = np.arange(icfg.grid.nx); rows = np.arange(icfg.grid.ny)
    CC, CR = np.meshgrid(cols, rows)
    cell_E = (icfg.grid.xmin + (CC+0.5)*icfg.grid.cell_size_m).ravel().astype(np.float32)
    cell_N = (icfg.grid.ymin + (CR+0.5)*icfg.grid.cell_size_m).ravel().astype(np.float32)
    ore_E = np.array([469500.0], dtype=np.float32)
    ore_N = np.array([2934900.0], dtype=np.float32)
    dist_ore = np.sqrt((cell_E-ore_E[0])**2+(cell_N-ore_N[0])**2).astype(np.float32)

    gpkg_paths = []
    for z in [185.0, 210.0, 235.0]:
        gf = gp.at_level(z); lv, pg, csr_ = dp.geology_at_level(z)
        inputs = {'lv':lv,'pg':pg,'csr':csr_,'grav':gf['grav'],
                  'grav_raw':gf.get('grav_raw',gf['grav']),
                  'grav_gradient':gf['grav_gradient'],'grav_laplacian':gf['grav_laplacian'],
                  'mag':gf['mag'],'mag_gradient':gf['mag_gradient'],
                  'cell_E':cell_E,'cell_N':cell_N,'z_mrl':z,'regime_id':2,
                  'dist_ore':dist_ore,'ore_area':30000.0,
                  'grav_mean':gf['grav_mean'],'grav_std':gf['grav_std'],
                  'mag_mean':gf['mag_mean'],'mag_std':gf['mag_std'],
                  'gg_mean':gf['gg_mean'],'gg_std':gf['gg_std'],
                  'lap_std':gf['lap_std'],'mg_p50':gf['mg_p50'],
                  'block_model_df':None}
        pr = compute_proximity(inputs, icfg); br = compute_blind(inputs, icfg)
        geo_ = {**gf,'lv':lv,'pg':pg,'csr':csr_,'dist_ore':dist_ore,'regime_id':2}
        p = os.path.join(TMP, f'IntegrationTest_mRL{int(z):+04d}.gpkg')
        write_level_gpkg(p, z, pr, br, geo_, cell_E, cell_N, icfg)
        gpkg_paths.append(p)

    @test
    def test_pipeline_creates_3_gpkgs():
        for p in gpkg_paths: assert os.path.exists(p), f"missing: {p}"

    @test
    def test_pipeline_cell_counts():
        expected = icfg.grid.nx * icfg.grid.ny
        for p in gpkg_paths:
            con = sqlite3.connect(p)
            tables = [r[0] for r in con.execute("SELECT table_name FROM gpkg_contents").fetchall()]
            count = con.execute(f"SELECT COUNT(*) FROM [{tables[0]}]").fetchone()[0]
            assert count == expected, f"got {count}"
            con.close()

    @test
    def test_pipeline_scores_valid():
        for p in gpkg_paths:
            con = sqlite3.connect(p)
            tables = [r[0] for r in con.execute("SELECT table_name FROM gpkg_contents").fetchall()]
            rows = con.execute(f"SELECT prox_score, blind_score FROM [{tables[0]}]").fetchall()
            for ps, bs in rows: assert 0<=ps<=100; assert 0<=bs<=100
            con.close()

    @test
    def test_pipeline_amphibolite_veto():
        for p in gpkg_paths:
            con = sqlite3.connect(p)
            tables = [r[0] for r in con.execute("SELECT table_name FROM gpkg_contents").fetchall()]
            bad = con.execute(f"SELECT COUNT(*) FROM [{tables[0]}] WHERE litho_code=2 AND prox_score>20").fetchone()[0]
            assert bad == 0
            con.close()

    @test
    def test_pipeline_config_saved():
        with open(config_path) as f: data = json.load(f)
        assert data['project_name'] == 'IntegrationTest'

# ══════════════════════════════════════════════════════════════════════════
print("\n═══ SPRINT 7 — Qt6 Compatibility ═══")

@test
def test_no_direct_qt_imports():
    bad = re.compile(r'from PyQt5\b|import PyQt5\b|from PyQt6\b|import PyQt6\b')
    for root, dirs, fnames in os.walk(PLUGIN_DIR):
        dirs[:] = [d for d in dirs if d not in ('__pycache__','.git','test')]
        for fn in fnames:
            if fn.endswith('.py'):
                content = open(os.path.join(root,fn), encoding='utf-8', errors='ignore').read()
                m = bad.findall(content)
                assert not m, f"{fn}: {m[0]}"

@test
def test_core_no_qgis_imports():
    qgis_re = re.compile(r'^from qgis|^import qgis', re.MULTILINE)
    for subdir in ['core','modules']:
        d = os.path.join(PLUGIN_DIR, subdir)
        if not os.path.isdir(d): continue
        for fn in os.listdir(d):
            if not fn.endswith('.py'): continue
            content = open(os.path.join(d, fn), encoding='utf-8').read()
            m = qgis_re.findall(content)
            assert not m, f"{subdir}/{fn} imports QGIS: {m[0]}"

# ══════════════════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"RESULTS: {passed} passed, {failed} failed")
print(f"{'='*60}")
if errors:
    print("\nFailed tests:")
    for name, msg in errors:
        print(f"  {name}: {msg[:200]}")
sys.exit(1 if failed else 0)
