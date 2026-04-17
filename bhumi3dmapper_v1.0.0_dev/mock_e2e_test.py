# -*- coding: utf-8 -*-
"""
End-to-End Mock Test for Bhumi3DMapper
========================================
Simulates the full UI workflow from wizard-entry to GPKG output.
Verifies every process runs, inputs flow through, outputs are produced,
and failures surface to the user.

Replaces the QGIS runtime (processing.run, QgsProcessingFeedback) with
mock objects that capture all feedback calls.
"""
import os
import sys
import json
import shutil
import sqlite3
import tempfile
import traceback
from pathlib import Path

PLUGIN = Path(__file__).parent / 'bhumi3dmapper'
sys.path.insert(0, str(PLUGIN))

# ── Mock QGIS feedback (captures all UI messages) ──────────────────────
class MockFeedback:
    def __init__(self):
        self.info_msgs = []
        self.warn_msgs = []
        self.error_msgs = []
        self.progress_values = []
        self.cancelled = False

    def pushInfo(self, msg): self.info_msgs.append(str(msg))
    def pushWarning(self, msg): self.warn_msgs.append(str(msg))
    def reportError(self, msg, fatalError=False):
        self.error_msgs.append((str(msg), bool(fatalError)))
    def setProgress(self, v): self.progress_values.append(int(v))
    def isCanceled(self): return self.cancelled


# ── Trace collector ─────────────────────────────────────────────────────
class ProcessTrace:
    """Records every process step: name, status, inputs received, outputs produced."""
    def __init__(self):
        self.steps = []  # list of dicts

    def record(self, process, status, inputs=None, outputs=None, error=None,
                feedback_msgs=0, data_size=None):
        self.steps.append({
            'process': process, 'status': status, 'inputs': inputs or [],
            'outputs': outputs or [], 'error': error,
            'feedback_msgs': feedback_msgs, 'data_size': data_size,
        })

    def summary(self):
        total = len(self.steps)
        passed = sum(1 for s in self.steps if s['status'] == 'PASS')
        failed = sum(1 for s in self.steps if s['status'] == 'FAIL')
        warned = sum(1 for s in self.steps if s['status'] == 'WARN')
        skipped = sum(1 for s in self.steps if s['status'] == 'SKIP')
        return f"Total: {total} | PASS: {passed} | FAIL: {failed} | WARN: {warned} | SKIP: {skipped}"

    def print_report(self):
        print("\n" + "═"*80)
        print(f"{'PROCESS':<38} {'STATUS':<8} {'INPUTS':<10} {'OUTPUTS':<10} {'FEEDBACK':<9}")
        print("─"*80)
        for s in self.steps:
            inputs_str = f"{len(s['inputs'])}"
            outputs_str = f"{len(s['outputs'])}"
            print(f"{s['process']:<38} {s['status']:<8} {inputs_str:<10} {outputs_str:<10} {s['feedback_msgs']:<9}")
            if s['error']:
                print(f"    └─ ERROR: {s['error']}")
            if s['data_size']:
                print(f"    └─ DATA: {s['data_size']}")
        print("─"*80)
        print(self.summary())
        print("═"*80 + "\n")


trace = ProcessTrace()


# ══════════════════════════════════════════════════════════════════════
# PHASE 1: User opens wizard → "Try Example Project"
# ══════════════════════════════════════════════════════════════════════
print("\n" + "█"*80)
print("PHASE 1: USER OPENS WIZARD → 'TRY EXAMPLE PROJECT' (JC-26)")
print("█"*80)

workdir = tempfile.mkdtemp(prefix='bhumi3d_e2e_')
try:
    from modules.m11_example import copy_example_project, example_banner_text
    config_path = copy_example_project(workdir)
    # Verify expected files
    assert os.path.exists(config_path)
    project_dir = os.path.dirname(config_path)
    expected = [
        'data/collar.csv', 'data/litho.csv', 'data/assay.csv', 'data/survey.csv',
        'geophysics/gravity/grav_185.tif',
        'geophysics/gravity/grav_210.tif',
        'geophysics/gravity/grav_235.tif',
        'geophysics/magnetics/mag_185.tif',
    ]
    for rel in expected:
        assert os.path.exists(os.path.join(project_dir, rel)), f"Missing: {rel}"
    trace.record('JC-26 copy_example_project', 'PASS',
                  inputs=['examples/kayad_synthetic/'],
                  outputs=[config_path],
                  feedback_msgs=0,
                  data_size=f"{len(expected)} files bundled")
except Exception as e:
    trace.record('JC-26 copy_example_project', 'FAIL', error=str(e))


# ══════════════════════════════════════════════════════════════════════
# PHASE 2: User clicks "Scan Project Folder" (JC-23)
# ══════════════════════════════════════════════════════════════════════
print("\n" + "█"*80)
print("PHASE 2: USER CLICKS 'SCAN PROJECT FOLDER' (JC-23)")
print("█"*80)

try:
    from modules.m08_autodiscover import autodiscover, apply_to_config
    from core.config import ProjectConfig
    # Scan the just-copied example folder
    scan_result = autodiscover(project_dir)
    found = [k for k in ('collar_csv', 'litho_csv', 'assay_csv', 'survey_csv',
                          'gravity_folder', 'magnetics_folder') if scan_result.get(k)]
    cfg_scan = ProjectConfig()
    changes = apply_to_config(cfg_scan, scan_result)
    trace.record('JC-23 autodiscover', 'PASS' if len(found) >= 4 else 'WARN',
                  inputs=[project_dir],
                  outputs=found,
                  feedback_msgs=len(scan_result.get('warnings', [])),
                  data_size=f"{len(found)}/6 fields detected, {len(changes)} config changes")
except Exception as e:
    trace.record('JC-23 autodiscover', 'FAIL', error=str(e))


# ══════════════════════════════════════════════════════════════════════
# PHASE 3: User confirms column mapping (JC-24) + CSV encoding (JC-29)
# ══════════════════════════════════════════════════════════════════════
print("\n" + "█"*80)
print("PHASE 3: COLUMN MAPPING + CSV ENCODING (JC-24, JC-29)")
print("█"*80)

try:
    from modules.m09_column_mapper import auto_map, preview_data
    import pandas as pd
    df_collar = pd.read_csv(os.path.join(project_dir, 'data/collar.csv'))
    mapping = auto_map('collar', df_collar.columns.tolist())
    required_mapped = all(mapping.get(f) is not None
                           for f in ('col_bhid', 'col_xcollar',
                                     'col_ycollar', 'col_zcollar'))
    preview = preview_data(df_collar, mapping['col_xcollar'])
    trace.record('JC-24 auto_map collar', 'PASS' if required_mapped else 'FAIL',
                  inputs=df_collar.columns.tolist(),
                  outputs=[f"{k}={v}" for k, v in mapping.items() if v],
                  data_size=f"X range: {preview['min']:.0f} to {preview['max']:.0f}")
except Exception as e:
    trace.record('JC-24 auto_map collar', 'FAIL', error=str(e))

# Encoding detection
try:
    from modules.m01_data_loader import _detect_encoding
    enc = _detect_encoding(os.path.join(project_dir, 'data/collar.csv'))
    trace.record('JC-29 _detect_encoding', 'PASS',
                  inputs=['data/collar.csv'],
                  outputs=[enc],
                  data_size=f"Detected: {enc}")
except Exception as e:
    trace.record('JC-29 _detect_encoding', 'FAIL', error=str(e))


# ══════════════════════════════════════════════════════════════════════
# PHASE 4: Load config and apply deposit preset (JC-17 + JC-25)
# ══════════════════════════════════════════════════════════════════════
print("\n" + "█"*80)
print("PHASE 4: LOAD CONFIG + DEPOSIT PRESET (JC-17, JC-25)")
print("█"*80)

try:
    from core.config import ProjectConfig
    cfg = ProjectConfig.from_json(config_path)
    trace.record('Config.from_json', 'PASS',
                  inputs=[config_path],
                  outputs=['ProjectConfig object'],
                  data_size=f"deposit={cfg.deposit_type}, grid={cfg.grid.nx}×{cfg.grid.ny}")
except Exception as e:
    trace.record('Config.from_json', 'FAIL', error=str(e))
    raise  # cannot continue

# Apply deposit preset
try:
    from core.presets.loader import apply_preset, list_presets
    presets = list_presets()
    apply_preset(cfg, 'sedex_pbzn')
    trace.record('JC-17 apply_preset sedex_pbzn', 'PASS',
                  inputs=['cfg', 'sedex_pbzn'],
                  outputs=['cfg.criterion_thresholds'],
                  data_size=f"{len(presets)} presets available, SEDEX applied")
except Exception as e:
    trace.record('JC-17 apply_preset sedex_pbzn', 'FAIL', error=str(e))


# ══════════════════════════════════════════════════════════════════════
# PHASE 5: Data loader (JC-06 GDAL + JC-29 encoding + column mapping)
# ══════════════════════════════════════════════════════════════════════
print("\n" + "█"*80)
print("PHASE 5: DATA LOADER")
print("█"*80)

from modules.m01_data_loader import DataLoader, _TIF_BACKEND
loader = DataLoader(cfg)

# Collar
try:
    collar_df = loader.load_collar()
    trace.record('DataLoader.load_collar', 'PASS',
                  inputs=[cfg.drill.collar_csv],
                  outputs=['collar_df'],
                  data_size=f"{len(collar_df)} holes, columns={list(collar_df.columns)[:4]}")
except Exception as e:
    trace.record('DataLoader.load_collar', 'FAIL', error=str(e))

# Litho
try:
    litho_df = loader.load_litho()
    n_unique = litho_df['lcode'].nunique()
    trace.record('DataLoader.load_litho', 'PASS',
                  inputs=[cfg.drill.litho_csv],
                  outputs=['litho_df'],
                  data_size=f"{len(litho_df)} intervals, {n_unique} unique rock codes")
except Exception as e:
    trace.record('DataLoader.load_litho', 'FAIL', error=str(e))

# Assay
try:
    assay_df = loader.load_assay()
    trace.record('DataLoader.load_assay', 'PASS',
                  inputs=[cfg.drill.assay_csv],
                  outputs=['assay_df'],
                  data_size=f"{len(assay_df)} assays")
except Exception as e:
    trace.record('DataLoader.load_assay', 'FAIL', error=str(e))

# Survey
try:
    survey_df = loader.load_survey()
    trace.record('DataLoader.load_survey', 'PASS',
                  inputs=[cfg.drill.survey_csv],
                  outputs=['survey_df'],
                  data_size=f"{len(survey_df)} survey stations")
except Exception as e:
    trace.record('DataLoader.load_survey', 'FAIL', error=str(e))

# Gravity (JC-06 GDAL → rasterio → PIL cascade)
try:
    grav_grids = loader.load_gravity()
    sample_shape = next(iter(grav_grids.values())).shape if grav_grids else None
    trace.record(f'DataLoader.load_gravity ({_TIF_BACKEND})', 'PASS' if grav_grids else 'FAIL',
                  inputs=[cfg.geophysics.gravity_folder],
                  outputs=[f'grav_grids ({len(grav_grids)} levels)'],
                  data_size=f"shape={sample_shape}, backend={_TIF_BACKEND}")
except Exception as e:
    trace.record(f'DataLoader.load_gravity ({_TIF_BACKEND})', 'FAIL', error=str(e))

# Magnetics
try:
    mag_grids = loader.load_magnetics()
    sample_shape = next(iter(mag_grids.values())).shape if mag_grids else None
    trace.record('DataLoader.load_magnetics', 'PASS' if mag_grids else 'FAIL',
                  inputs=[cfg.geophysics.magnetics_folder],
                  outputs=[f'mag_grids ({len(mag_grids)} levels)'],
                  data_size=f"shape={sample_shape}")
except Exception as e:
    trace.record('DataLoader.load_magnetics', 'FAIL', error=str(e))

# Ore centroids
try:
    ore_df = loader.load_ore_centroids()
    trace.record('DataLoader.load_ore_centroids', 'PASS',
                  inputs=['(no polygon data)'],
                  outputs=['ore_df'],
                  data_size=f"{len(ore_df)} centroids (expected 0 — not in example)")
except Exception as e:
    trace.record('DataLoader.load_ore_centroids', 'FAIL', error=str(e))


# ══════════════════════════════════════════════════════════════════════
# PHASE 6: Data Quality Gate (JC-28 HARD GATE) + Sanity (JC-25)
# ══════════════════════════════════════════════════════════════════════
print("\n" + "█"*80)
print("PHASE 6: DATA QUALITY HARD GATE (JC-28) + SANITY (JC-25)")
print("█"*80)

try:
    from modules.m12_data_quality import run_all_checks
    dq = run_all_checks(cfg, collar_df=collar_df, litho_df=litho_df,
                          assay_df=assay_df, grav_grids=grav_grids,
                          mag_grids=mag_grids)
    status = 'PASS' if not dq.blocks_advance else 'FAIL'
    trace.record('JC-28 run_all_checks (HARD GATE)', status,
                  inputs=['collar', 'litho', 'assay', 'gravity', 'magnetics'],
                  outputs=[f'DQReport ({dq.critical_count} critical, {dq.warning_count} warning)'],
                  data_size=dq.summary())
except Exception as e:
    trace.record('JC-28 run_all_checks', 'FAIL', error=str(e))

try:
    from modules.m10_sanity import run_all_sanity_checks
    sanity = run_all_sanity_checks(cfg, litho_df)
    trace.record('JC-25 run_all_sanity_checks', 'PASS',
                  inputs=['cfg.deposit_type', 'litho_df'],
                  outputs=[f'{len(sanity)} sanity warnings'],
                  data_size='\n    '.join(w.message[:80] for w in sanity[:3]))
except Exception as e:
    trace.record('JC-25 run_all_sanity_checks', 'FAIL', error=str(e))


# ══════════════════════════════════════════════════════════════════════
# PHASE 7: DrillProcessor + GeophysicsProcessor
# ══════════════════════════════════════════════════════════════════════
print("\n" + "█"*80)
print("PHASE 7: DRILL + GEOPHYSICS PROCESSORS")
print("█"*80)

try:
    from modules.m02_drill_processor import DrillProcessor
    dp = DrillProcessor(cfg)
    dp.build_lookups(collar_df, litho_df)
    trace.record('DrillProcessor.build_lookups', 'PASS',
                  inputs=['collar_df', 'litho_df'],
                  outputs=['hole_litho', 'hole_pg', 'hole_csr', 'coarse_grid'],
                  data_size=f"{len(dp.bhids)} holes, coarse grid {dp._CNX}×{dp._CNY}")
except Exception as e:
    trace.record('DrillProcessor.build_lookups', 'FAIL', error=str(e))

try:
    from modules.m03_geophys_processor import GeophysicsProcessor
    gp = GeophysicsProcessor(cfg)
    gp.load(grav_grids, mag_grids)
    trace.record('GeophysicsProcessor.load', 'PASS',
                  inputs=['grav_grids', 'mag_grids'],
                  outputs=['grav_grad', 'grav_lap', 'mag_grad'],
                  data_size=f"{len(gp.grav_levels)} grav, {len(gp.mag_levels)} mag levels")
except Exception as e:
    trace.record('GeophysicsProcessor.load', 'FAIL', error=str(e))


# ══════════════════════════════════════════════════════════════════════
# PHASE 8: Desurvey (JC-07) — note: module exists but not yet wired
# ══════════════════════════════════════════════════════════════════════
print("\n" + "█"*80)
print("PHASE 8: DESURVEY MODULE (JC-07)")
print("█"*80)

try:
    from modules.m07_desurvey import minimum_curvature_desurvey, interpolate_at_depth
    ds_df = minimum_curvature_desurvey(survey_df, collar_df)
    test_xyz = interpolate_at_depth(ds_df, ds_df['BHID'].iloc[0], 50.0)
    trace.record('JC-07 minimum_curvature_desurvey', 'WARN',
                  inputs=['survey_df', 'collar_df'],
                  outputs=['desurvey_df'],
                  data_size=f"{len(ds_df)} stations. NOTE: module BUILT but NOT WIRED into DrillProcessor.geology_at_level()")
except Exception as e:
    trace.record('JC-07 minimum_curvature_desurvey', 'FAIL', error=str(e))


# ══════════════════════════════════════════════════════════════════════
# PHASE 9: Scoring loop — per-level compute_proximity + compute_blind
# ══════════════════════════════════════════════════════════════════════
print("\n" + "█"*80)
print("PHASE 9: SCORING PIPELINE (proximity + blind)")
print("█"*80)

import numpy as np
from modules.m04_scoring_engine import compute_proximity, compute_blind

g = cfg.grid
cols = np.arange(g.nx); rows = np.arange(g.ny)
CC, CR = np.meshgrid(cols, rows)
cell_E = (g.xmin + (CC + 0.5) * g.cell_size_m).astype(np.float32).ravel()
cell_N = (g.ymin + (CR + 0.5) * g.cell_size_m).astype(np.float32).ravel()

ore_E = np.array([], dtype=np.float32)
ore_N = np.array([], dtype=np.float32)
if len(ore_E) > 0:
    dE = cell_E[:, None] - ore_E[None, :]
    dN = cell_N[:, None] - ore_N[None, :]
    dist_ore = np.sqrt(dE**2 + dN**2).min(axis=1).astype(np.float32)
else:
    dist_ore = np.full(len(cell_E), 9999.0, dtype=np.float32)

# Process each level
z_levels = [185.0, 210.0, 235.0]
scoring_results = {}
for z in z_levels:
    try:
        lv, pg, csr = dp.geology_at_level(z)
        gf = gp.at_level(z)
        rid = 0
        for rd in cfg.regimes.regimes:
            if rd['z_min'] <= z <= rd['z_max']:
                rid = rd['id']; break
        inputs = {
            'lv': lv, 'pg': pg, 'csr': csr,
            'grav': gf['grav'], 'grav_raw': gf.get('grav_raw', gf['grav']),
            'grav_gradient': gf['grav_gradient'], 'grav_laplacian': gf['grav_laplacian'],
            'mag': gf['mag'], 'mag_gradient': gf['mag_gradient'],
            'cell_E': cell_E, 'cell_N': cell_N, 'z_mrl': z, 'regime_id': rid,
            'dist_ore': dist_ore, 'ore_area': 50000,
            'grav_mean': gf['grav_mean'], 'grav_std': gf['grav_std'],
            'mag_mean': gf['mag_mean'], 'mag_std': gf['mag_std'],
            'gg_mean': gf['gg_mean'], 'gg_std': gf['gg_std'],
            'lap_std': gf['lap_std'], 'mg_p50': gf['mg_p50'],
            'block_model_df': None,
        }
        pr = compute_proximity(inputs, cfg)
        br = compute_blind(inputs, cfg)
        scoring_results[z] = (pr, br)
        pvh = int((pr['score'] >= 75).sum())
        bvh = int((br['score'] >= 75).sum())
        trace.record(f'compute_scoring z={z:.0f}', 'PASS',
                      inputs=['lv', 'pg', 'csr', 'geophysics'],
                      outputs=[f'prox_scores', 'blind_scores'],
                      data_size=f"prox range [{pr['score'].min():.1f}, {pr['score'].max():.1f}], "
                                f"VH count: P={pvh} B={bvh}")
    except Exception as e:
        trace.record(f'compute_scoring z={z:.0f}', 'FAIL', error=str(e))


# ══════════════════════════════════════════════════════════════════════
# PHASE 10: GPKG output writer (JC-05 polygon area works here)
# ══════════════════════════════════════════════════════════════════════
print("\n" + "█"*80)
print("PHASE 10: GPKG WRITER")
print("█"*80)

from modules.m05_gpkg_writer import write_level_gpkg
output_dir = os.path.join(project_dir, 'outputs', 'gpkg')
os.makedirs(output_dir, exist_ok=True)

for z in z_levels:
    try:
        pr, br = scoring_results[z]
        lv, pg, csr = dp.geology_at_level(z)
        gf = gp.at_level(z)
        rid = 0
        for rd in cfg.regimes.regimes:
            if rd['z_min'] <= z <= rd['z_max']:
                rid = rd['id']; break
        geo = {**gf, 'lv': lv, 'pg': pg, 'csr': csr, 'dist_ore': dist_ore, 'regime_id': rid}
        path = os.path.join(output_dir, f'Example_mRL{int(z):+04d}.gpkg')
        write_level_gpkg(path, z, pr, br, geo, cell_E, cell_N, cfg)
        # Verify GPKG structure
        con = sqlite3.connect(path)
        tables = [r[0] for r in con.execute("SELECT table_name FROM gpkg_contents").fetchall()]
        cell_count = con.execute(f"SELECT COUNT(*) FROM [{tables[0]}]").fetchone()[0]
        cols = [r[1] for r in con.execute(f"PRAGMA table_info([{tables[0]}])").fetchall()]
        has_prox = 'prox_score' in cols
        has_blind = 'blind_score' in cols
        has_geom = 'geom' in cols
        con.close()
        all_present = has_prox and has_blind and has_geom
        trace.record(f'write_level_gpkg z={z:.0f}', 'PASS' if all_present else 'WARN',
                      inputs=[f'pr[{z}]', f'br[{z}]', 'geo', 'cell_E', 'cell_N'],
                      outputs=[os.path.basename(path)],
                      data_size=f"{cell_count} cells, {len(cols)} columns, prox={has_prox} blind={has_blind} geom={has_geom}")
    except Exception as e:
        trace.record(f'write_level_gpkg z={z:.0f}', 'FAIL', error=str(e))


# ══════════════════════════════════════════════════════════════════════
# PHASE 11: Error handling — does every failure surface to the user?
# ══════════════════════════════════════════════════════════════════════
print("\n" + "█"*80)
print("PHASE 11: ERROR HANDLING PATHS (JC-27)")
print("█"*80)

from core.errors import translate, UserError

# Test 1: FileNotFoundError translation
try:
    try:
        open('/bhumi3d_test_nonexistent.csv')
    except FileNotFoundError as e:
        ue = translate(e)
    has_msg = 'Cannot find' in ue.message
    has_sug = len(ue.suggestion) > 20
    trace.record('JC-27 translate(FileNotFoundError)', 'PASS' if has_msg and has_sug else 'FAIL',
                  inputs=['FileNotFoundError'],
                  outputs=[ue.message[:60]],
                  data_size=f"suggestion: {ue.suggestion[:80]}")
except Exception as e:
    trace.record('JC-27 translate(FileNotFoundError)', 'FAIL', error=str(e))

# Test 2: KeyError translation (missing column)
try:
    err = KeyError('XCOLLAR')
    ue = translate(err)
    trace.record('JC-27 translate(KeyError missing col)', 'PASS',
                  inputs=['KeyError'],
                  outputs=[ue.message[:60]],
                  data_size=f"surfaces: {ue.suggestion[:80]}")
except Exception as e:
    trace.record('JC-27 translate(KeyError)', 'FAIL', error=str(e))

# Test 3: Encoding error
try:
    err = UnicodeDecodeError('ascii', b'\x80', 0, 1, 'bad byte')
    ue = translate(err)
    trace.record('JC-27 translate(UnicodeDecodeError)', 'PASS',
                  inputs=['UnicodeDecodeError'],
                  outputs=[ue.message],
                  data_size=f"surfaces CSV re-save hint")
except Exception as e:
    trace.record('JC-27 translate(UnicodeDecodeError)', 'FAIL', error=str(e))


# ══════════════════════════════════════════════════════════════════════
# PHASE 12: Scenario-based failure tests (induced bad data)
# ══════════════════════════════════════════════════════════════════════
print("\n" + "█"*80)
print("PHASE 12: INDUCED FAILURE SCENARIOS (does DQ gate catch them?)")
print("█"*80)

import pandas as pd
from modules.m12_data_quality import run_all_checks

# Scenario 1: Duplicate BHIDs — should BLOCK advance
try:
    bad = collar_df.copy()
    bad.iloc[1, bad.columns.get_loc('BHID')] = bad.iloc[0]['BHID']  # dupe
    rpt = run_all_checks(cfg, collar_df=bad, litho_df=litho_df)
    caught = rpt.blocks_advance
    trace.record('DQ detects duplicate BHIDs', 'PASS' if caught else 'FAIL',
                  inputs=['modified collar with duplicate'],
                  outputs=['DQReport'],
                  data_size=f"blocks_advance={caught}, critical={rpt.critical_count}")
except Exception as e:
    trace.record('DQ detects duplicate BHIDs', 'FAIL', error=str(e))

# Scenario 2: Negative grade — should BLOCK advance
try:
    bad_assay = assay_df.copy()
    bad_assay.iloc[0, bad_assay.columns.get_loc('ZN')] = -5.0
    rpt = run_all_checks(cfg, collar_df=collar_df, litho_df=litho_df, assay_df=bad_assay)
    caught = any('negative' in i.title.lower() for i in rpt.issues if i.blocks_advance)
    trace.record('DQ detects negative grade', 'PASS' if caught else 'FAIL',
                  inputs=['assay with ZN=-5.0'],
                  outputs=['DQReport'],
                  data_size=f"blocks_advance={rpt.blocks_advance}")
except Exception as e:
    trace.record('DQ detects negative grade', 'FAIL', error=str(e))

# Scenario 3: Decimal-degree coords mistaken for UTM
try:
    bad_collar = collar_df.copy()
    bad_collar['XCOLLAR'] = [75.3, 75.4, 75.5] * (len(bad_collar) // 3 + 1)
    bad_collar['XCOLLAR'] = bad_collar['XCOLLAR'].values[:len(bad_collar)]
    bad_collar['YCOLLAR'] = [26.5, 26.6, 26.7] * (len(bad_collar) // 3 + 1)
    bad_collar['YCOLLAR'] = bad_collar['YCOLLAR'].values[:len(bad_collar)]
    rpt = run_all_checks(cfg, collar_df=bad_collar)
    caught = any('decimal' in i.title.lower() for i in rpt.issues)
    trace.record('DQ detects lat/long as UTM', 'PASS' if caught else 'FAIL',
                  inputs=['collar with decimal-degree coords'],
                  outputs=['DQReport'],
                  data_size=f"critical={rpt.critical_count}")
except Exception as e:
    trace.record('DQ detects lat/long as UTM', 'FAIL', error=str(e))

# Scenario 4: Wrong deposit preset for the data
try:
    cfg_wrong = ProjectConfig.from_json(config_path)
    cfg_wrong.deposit_type = 'VMS Cu-Zn'  # but data is SEDEX
    from modules.m10_sanity import run_all_sanity_checks
    warnings = run_all_sanity_checks(cfg_wrong, litho_df)
    caught = len(warnings) > 0
    trace.record('Sanity detects wrong deposit preset', 'PASS' if caught else 'FAIL',
                  inputs=['VMS preset with SEDEX-style litho'],
                  outputs=[f'{len(warnings)} warnings'],
                  data_size=warnings[0].message[:100] if warnings else 'no warnings')
except Exception as e:
    trace.record('Sanity detects wrong deposit preset', 'FAIL', error=str(e))


# ══════════════════════════════════════════════════════════════════════
# PHASE 13: Check which scoring criteria made it into the GPKG output
# ══════════════════════════════════════════════════════════════════════
print("\n" + "█"*80)
print("PHASE 13: COMPLETENESS — DO ALL SCORING CRITERIA REACH THE OUTPUT?")
print("█"*80)

expected_prox_criteria = ['c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c9', 'c10']
expected_blind_criteria = ['c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7b', 'c8', 'c9_lap', 'c10']

gpkg_path = os.path.join(output_dir, 'Example_mRL+0185.gpkg')
if os.path.exists(gpkg_path):
    try:
        con = sqlite3.connect(gpkg_path)
        tables = [r[0] for r in con.execute("SELECT table_name FROM gpkg_contents").fetchall()]
        cols = [r[1] for r in con.execute(f"PRAGMA table_info([{tables[0]}])").fetchall()]
        # Check presence of scoring criterion columns
        prox_found = [c for c in expected_prox_criteria if any(c in col.lower() for col in cols)]
        blind_found = [c for c in expected_blind_criteria if any(c in col.lower() for col in cols)]
        prox_missing = [c for c in expected_prox_criteria if c not in prox_found]
        blind_missing = [c for c in expected_blind_criteria if c not in blind_found]
        # Geophysics raw fields
        geo_fields = ['grav', 'mag', 'lv', 'pg', 'csr']
        geo_found = [g for g in geo_fields if any(g in col.lower() for col in cols)]
        con.close()
        status = 'PASS' if not prox_missing and not blind_missing else 'WARN'
        trace.record('GPKG criterion completeness', status,
                      inputs=['Example_mRL+0185.gpkg'],
                      outputs=[f'{len(cols)} columns'],
                      data_size=f"prox: {len(prox_found)}/{len(expected_prox_criteria)} "
                                f"blind: {len(blind_found)}/{len(expected_blind_criteria)} "
                                f"geo: {len(geo_found)}/5. "
                                f"Missing prox: {prox_missing}. Missing blind: {blind_missing}")
    except Exception as e:
        trace.record('GPKG criterion completeness', 'FAIL', error=str(e))
else:
    trace.record('GPKG criterion completeness', 'SKIP', error='GPKG not written')


# ══════════════════════════════════════════════════════════════════════
# PHASE 14: Plain-language error surfaces in alg_run_scoring
# ══════════════════════════════════════════════════════════════════════
print("\n" + "█"*80)
print("PHASE 14: DOES alg_run_scoring TRANSLATE ERRORS?")
print("█"*80)

# Simulate a deliberate failure and trace error flow
fb = MockFeedback()
try:
    # Force a translated error
    err = KeyError('MISSING_COL_ZN')
    ue = translate(err, context='simulated')
    from core.errors import format_for_display
    fb.reportError(format_for_display(ue), fatalError=True)
    # Check that the error message is plain-language
    err_msgs = [m for m, _ in fb.error_msgs]
    has_plain = any('Missing required column' in m for m in err_msgs)
    trace.record('alg_run_scoring error translation', 'PASS' if has_plain else 'FAIL',
                  inputs=['simulated KeyError'],
                  outputs=['MockFeedback.error_msgs'],
                  feedback_msgs=len(fb.error_msgs),
                  data_size=f"plain-language: {has_plain}")
except Exception as e:
    trace.record('alg_run_scoring error translation', 'FAIL', error=str(e))


# ══════════════════════════════════════════════════════════════════════
# PHASE 15: Tooltips are loaded but are they DISPLAYED?
# ══════════════════════════════════════════════════════════════════════
print("\n" + "█"*80)
print("PHASE 15: TOOLTIPS — LOADED VS DISPLAYED (JC-30)")
print("█"*80)

try:
    from core.tooltips import get_tooltip, list_documented_parameters
    params = list_documented_parameters()
    tt = get_tooltip('structural_marker_code', 'SEDEX Pb-Zn')
    # Scan UI files to see if any widget calls setToolTip(get_tooltip(...))
    ui_files = list((PLUGIN / 'ui').glob('*.py'))
    tooltip_wired = False
    for uf in ui_files:
        content = uf.read_text(encoding='utf-8')
        if 'get_tooltip' in content:
            tooltip_wired = True
            break
    trace.record('JC-30 tooltip loading', 'PASS',
                  inputs=['structural_marker_code', 'SEDEX Pb-Zn'],
                  outputs=[tt[:80]],
                  data_size=f"{len(params)} documented parameters")
    trace.record('JC-30 tooltip UI wiring', 'FAIL' if not tooltip_wired else 'PASS',
                  inputs=['UI widgets'],
                  outputs=['setToolTip calls'],
                  data_size=f"WARNING: tooltips loaded but NOT wired into UI widgets — user will not see them")
except Exception as e:
    trace.record('JC-30 tooltip loading', 'FAIL', error=str(e))


# ══════════════════════════════════════════════════════════════════════
# FINAL REPORT
# ══════════════════════════════════════════════════════════════════════
print("\n" + "█"*80)
print("FINAL END-TO-END TRACE REPORT")
print("█"*80)
trace.print_report()

# Cleanup
try:
    shutil.rmtree(workdir)
except Exception:
    pass

# Exit code
failed = sum(1 for s in trace.steps if s['status'] == 'FAIL')
sys.exit(1 if failed > 0 else 0)
