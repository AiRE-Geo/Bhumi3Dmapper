# -*- coding: utf-8 -*-
"""
Tests for BH-08, BH-09, BH-10, BH-11 bug fixes.
Dr. Prithvi test run 2026-04-18.

Run:
    cd bhumi3dmapper_v1.0.0_dev
    python -m pytest bhumi3dmapper/test/test_bug_fixes_bh08_bh11.py -v
"""
import os
import sys
import json
import tempfile
import warnings

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from bhumi3dmapper.core.config import ProjectConfig, StructuralConfig


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

EXAMPLE_CONFIG = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'examples',
                 'kayad_synthetic', 'config.json')
)


def _minimal_config_dict(**overrides) -> dict:
    """Minimal JSON-serialisable config dict for from_json round-trip tests."""
    d = {
        'project_name': 'Test Project',
        'deposit_type': 'SEDEX Pb-Zn',
        'scoring_engine': 'json_model',
        'json_model_deposit_type': 'sedex_pbzn',
        'shared_repo_path': '/some/path',
        'override_low_coverage': True,
        'grid': {'nx': 10, 'ny': 10, 'z_top_mrl': 100.0, 'z_bot_mrl': 50.0},
        'drill': {
            'collar_csv': 'data/collar.csv',
            'assay_csv':  'data/assay.csv',
            'litho_csv':  'data/litho.csv',
            'survey_csv': 'data/survey.csv',
        },
        'geophysics': {
            'gravity_folder':    'geophysics/gravity',
            'magnetics_folder':  'geophysics/magnetics',
        },
        'outputs': {'output_dir': 'outputs'},
    }
    d.update(overrides)
    return d


# ─────────────────────────────────────────────────────────────────────────────
# BH-08: from_json must persist Engine 2 fields across save/reload
# ─────────────────────────────────────────────────────────────────────────────

class TestBH08FromJsonEngine2Fields:
    """from_json did not load scoring_engine / json_model_deposit_type /
    shared_repo_path / override_low_coverage — project re-open silently
    reverted to Engine 1."""

    def test_scoring_engine_persisted(self, tmp_path):
        d = _minimal_config_dict(scoring_engine='json_model')
        p = tmp_path / 'cfg.json'
        p.write_text(json.dumps(d))
        cfg = ProjectConfig.from_json(str(p))
        assert cfg.scoring_engine == 'json_model', (
            "BH-08: scoring_engine not loaded from JSON — re-open reverts to Engine 1"
        )

    def test_json_model_deposit_type_persisted(self, tmp_path):
        d = _minimal_config_dict(json_model_deposit_type='orogenic_au')
        p = tmp_path / 'cfg.json'
        p.write_text(json.dumps(d))
        cfg = ProjectConfig.from_json(str(p))
        assert cfg.json_model_deposit_type == 'orogenic_au'

    def test_shared_repo_path_persisted(self, tmp_path):
        d = _minimal_config_dict(shared_repo_path='/custom/repo')
        p = tmp_path / 'cfg.json'
        p.write_text(json.dumps(d))
        cfg = ProjectConfig.from_json(str(p))
        assert cfg.shared_repo_path == '/custom/repo'

    def test_override_low_coverage_persisted(self, tmp_path):
        d = _minimal_config_dict(override_low_coverage=True)
        p = tmp_path / 'cfg.json'
        p.write_text(json.dumps(d))
        cfg = ProjectConfig.from_json(str(p))
        assert cfg.override_low_coverage is True

    def test_default_remains_kayad_when_absent(self, tmp_path):
        """If scoring_engine not present in JSON, default 'kayad' is used."""
        d = _minimal_config_dict()
        del d['scoring_engine']
        p = tmp_path / 'cfg.json'
        p.write_text(json.dumps(d))
        cfg = ProjectConfig.from_json(str(p))
        assert cfg.scoring_engine == 'kayad'


# ─────────────────────────────────────────────────────────────────────────────
# BH-09: Structural corridor gap must emit warnings.warn, not silently fallback
# ─────────────────────────────────────────────────────────────────────────────

class TestBH09CorridorGapWarning:
    """score_structural_corridor silently used corridors[0] for z_mrl values
    not covered by any corridor — no warning was emitted."""

    def _make_cfg_with_gap(self):
        """Return a ProjectConfig whose corridors leave a gap."""
        from bhumi3dmapper.core.config import ProjectConfig, StructuralConfig
        cfg = ProjectConfig()
        # Two corridors with a gap: upper covers 100–300, lower covers −300 to −100
        # Gap: −100 to +100
        cfg.structure = StructuralConfig(
            corridors=[
                {
                    'name': 'Upper',
                    'azimuth_deg': 28.0,
                    'plunge_deg': 30.0,
                    'plunge_azimuth_deg': 75.0,
                    'anchor_E': 469519.0,
                    'anchor_N': 2934895.0,
                    'anchor_mRL': 200.0,
                    'lateral_E_per_100m_down': 0.0,
                    'lateral_N_per_100m_down': 0.0,
                    'z_top_mrl': 300.0,
                    'z_bot_mrl': 100.0,
                },
                {
                    'name': 'Lower',
                    'azimuth_deg': 315.0,
                    'plunge_deg': 12.0,
                    'plunge_azimuth_deg': 63.0,
                    'anchor_E': 469519.0,
                    'anchor_N': 2934895.0,
                    'anchor_mRL': -200.0,
                    'lateral_E_per_100m_down': 0.0,
                    'lateral_N_per_100m_down': 0.0,
                    'z_top_mrl': -100.0,
                    'z_bot_mrl': -300.0,
                },
            ],
            score_breaks_m=[75, 150, 300],
            score_values=[1.0, 0.8, 0.5, 0.2],
        )
        return cfg

    def test_gap_emits_warning(self):
        from bhumi3dmapper.modules.m04_scoring_engine import score_structural_corridor
        cfg = self._make_cfg_with_gap()
        cell_E = np.array([469519.0])
        cell_N = np.array([2934895.0])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            score_structural_corridor(cell_E, cell_N, 0.0, cfg, 0)  # regime_id positional
        assert len(w) == 1, "BH-09: expected exactly 1 warning for gap z_mrl=0.0"
        assert 'corridor' in str(w[0].message).lower()
        assert '0.0' in str(w[0].message)

    def test_no_warning_when_covered(self):
        from bhumi3dmapper.modules.m04_scoring_engine import score_structural_corridor
        cfg = self._make_cfg_with_gap()
        cell_E = np.array([469519.0])
        cell_N = np.array([2934895.0])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            score_structural_corridor(cell_E, cell_N, 200.0, cfg, 0)
        corridor_warns = [x for x in w if 'corridor' in str(x.message).lower()
                          and 'gap' in str(x.message).lower()]
        assert len(corridor_warns) == 0, (
            "No warning expected when z_mrl is within a defined corridor"
        )

    def test_warning_names_the_gap_level(self):
        from bhumi3dmapper.modules.m04_scoring_engine import score_structural_corridor
        cfg = self._make_cfg_with_gap()
        cell_E = np.array([469519.0])
        cell_N = np.array([2934895.0])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            score_structural_corridor(cell_E, cell_N, 50.0, cfg, 0)
        assert any('50.0' in str(x.message) for x in w), (
            "Warning message should include the uncovered z_mrl value"
        )

    def test_default_kayad_corridors_cover_example_levels(self):
        """Default Kayad N28E corridor covers 60-460 mRL — example levels 185/210/235
        must not trigger the gap warning."""
        from bhumi3dmapper.modules.m04_scoring_engine import score_structural_corridor
        cfg = ProjectConfig()  # default corridors
        cell_E = np.array([469519.0])
        cell_N = np.array([2934895.0])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            for z in [185.0, 210.0, 235.0]:
                score_structural_corridor(cell_E, cell_N, z, cfg, 2)
        gap_warns = [x for x in w if 'gap' in str(x.message).lower()]
        assert len(gap_warns) == 0, (
            "Default Kayad corridors cover 185-235 mRL — no gap warning expected"
        )


# ─────────────────────────────────────────────────────────────────────────────
# BH-10: Relative paths in config.json must resolve to absolute on from_json
# ─────────────────────────────────────────────────────────────────────────────

class TestBH10RelativePathResolution:
    """from_json must resolve relative drill/geophysics/output paths relative
    to the config file's own directory, not the process CWD."""

    def test_drill_paths_become_absolute(self, tmp_path):
        cfg_dir = tmp_path / 'myproject'
        cfg_dir.mkdir()
        d = _minimal_config_dict()  # drill paths are relative: 'data/collar.csv' etc.
        p = cfg_dir / 'config.json'
        p.write_text(json.dumps(d))
        cfg = ProjectConfig.from_json(str(p))
        assert os.path.isabs(cfg.drill.collar_csv), "collar_csv must be absolute"
        assert str(cfg_dir) in cfg.drill.collar_csv
        assert os.path.isabs(cfg.drill.litho_csv)
        assert os.path.isabs(cfg.drill.assay_csv)
        assert os.path.isabs(cfg.drill.survey_csv)

    def test_geophysics_paths_become_absolute(self, tmp_path):
        cfg_dir = tmp_path / 'proj2'
        cfg_dir.mkdir()
        d = _minimal_config_dict()
        p = cfg_dir / 'cfg.json'
        p.write_text(json.dumps(d))
        cfg = ProjectConfig.from_json(str(p))
        assert os.path.isabs(cfg.geophysics.gravity_folder)
        assert os.path.isabs(cfg.geophysics.magnetics_folder)
        assert str(cfg_dir) in cfg.geophysics.gravity_folder

    def test_output_dir_becomes_absolute(self, tmp_path):
        cfg_dir = tmp_path / 'proj3'
        cfg_dir.mkdir()
        d = _minimal_config_dict()
        p = cfg_dir / 'cfg.json'
        p.write_text(json.dumps(d))
        cfg = ProjectConfig.from_json(str(p))
        assert os.path.isabs(cfg.outputs.output_dir)

    def test_already_absolute_paths_unchanged(self, tmp_path):
        # Use a platform-correct absolute path so os.path.isabs() returns True
        abs_collar = os.path.abspath(str(tmp_path / 'data' / 'collar.csv'))
        d = _minimal_config_dict()
        d['drill']['collar_csv'] = abs_collar
        p = tmp_path / 'cfg.json'
        p.write_text(json.dumps(d))
        cfg = ProjectConfig.from_json(str(p))
        assert cfg.drill.collar_csv == abs_collar, (
            "Absolute paths in config must not be modified by from_json"
        )

    @pytest.mark.skipif(not os.path.exists(EXAMPLE_CONFIG),
                        reason="Kayad example not present")
    def test_example_config_resolves_correctly(self):
        """The live Kayad example config resolves all paths correctly."""
        cfg = ProjectConfig.from_json(EXAMPLE_CONFIG)
        assert os.path.isabs(cfg.drill.collar_csv)
        assert os.path.exists(cfg.drill.collar_csv), (
            f"Resolved collar path does not exist: {cfg.drill.collar_csv}"
        )
        assert os.path.isdir(cfg.geophysics.gravity_folder), (
            f"Resolved gravity folder does not exist: {cfg.geophysics.gravity_folder}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# BH-11: load_magnetics must warn when values are anomalously large (nT scale)
# ─────────────────────────────────────────────────────────────────────────────

class TestBH11MagneticsScaleWarning:
    """load_magnetics was silent when values were orders of magnitude too large
    (nT data loaded as µSI).  Scoring with C5/C8 thresholds was silently wrong."""

    def _loader_with_mag(self, tmp_path, mag_value: float):
        """Return a DataLoader whose load_magnetics() returns {0: array_of(mag_value)}."""
        import numpy as np
        from bhumi3dmapper.core.config import ProjectConfig, GeophysicsConfig
        from bhumi3dmapper.modules.m01_data_loader import DataLoader

        # Write a trivial 10×10 TIF using numpy (no GDAL needed — use PIL fallback)
        mag_dir = tmp_path / 'mag'
        mag_dir.mkdir()
        arr = np.full((10, 10), mag_value, dtype=np.float32)

        # Write as a raw binary TIF via PIL if available, else write a fake file
        # and monkey-patch the loader to return the dict directly.
        cfg = ProjectConfig()
        cfg.geophysics = GeophysicsConfig(
            magnetics_folder=str(mag_dir),
            magnetics_units='uSI',
            magnetics_nodatavalue=-9999.0,
            magnetics_pixel_size_m=30.0,
        )
        loader = DataLoader(cfg)
        # Monkey-patch _load_tif_folder to bypass file I/O
        loader._mock_mag_arr = arr
        original = loader._load_tif_folder

        def fake_load(folder, scale=1.0, nodata=-9999.0):
            if folder == str(mag_dir):
                return {0: loader._mock_mag_arr * scale}
            return original(folder, scale=scale, nodata=nodata)

        loader._load_tif_folder = fake_load
        return loader

    def test_large_values_emit_warning(self, tmp_path):
        """Values > 5000 (nT scale) must trigger BH-11 warning."""
        loader = self._loader_with_mag(tmp_path, mag_value=35_000.0)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            loader.load_magnetics()
        bh11_warns = [x for x in w if 'BH-11' in str(x.message)]
        assert len(bh11_warns) == 1, (
            "BH-11: expected warning for anomalously large magnetics values (35000 µSI)"
        )
        assert '35000' in str(bh11_warns[0].message) or '35,000' in str(bh11_warns[0].message)

    def test_normal_values_no_warning(self, tmp_path):
        """Typical µSI values (<200) must not trigger BH-11 warning."""
        loader = self._loader_with_mag(tmp_path, mag_value=15.0)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            loader.load_magnetics()
        bh11_warns = [x for x in w if 'BH-11' in str(x.message)]
        assert len(bh11_warns) == 0, (
            "BH-11: no warning expected for normal µSI values (~15)"
        )

    def test_warning_mentions_unit_setting(self, tmp_path):
        """BH-11 warning must guide the user to check magnetics_units."""
        loader = self._loader_with_mag(tmp_path, mag_value=50_000.0)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            loader.load_magnetics()
        bh11_warns = [x for x in w if 'BH-11' in str(x.message)]
        assert bh11_warns, "Expected BH-11 warning"
        msg = str(bh11_warns[0].message)
        assert 'uSI' in msg or 'magnetics_units' in msg, (
            "Warning must mention the unit setting so user knows what to fix"
        )

    def test_boundary_5000_triggers_warning(self, tmp_path):
        """Exactly at the 5000 boundary: values above must warn, below must not."""
        loader_above = self._loader_with_mag(tmp_path, mag_value=5_001.0)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            loader_above.load_magnetics()
        assert any('BH-11' in str(x.message) for x in w), "5001 must trigger warning"

    @pytest.mark.skipif(not os.path.exists(EXAMPLE_CONFIG),
                        reason="Kayad example not present")
    def test_kayad_example_magnetics_no_warning(self):
        """The Kayad synthetic magnetics (correctly in µSI, ~0–23 range)
        must not trigger the BH-11 warning."""
        from bhumi3dmapper.modules.m01_data_loader import DataLoader
        cfg = ProjectConfig.from_json(EXAMPLE_CONFIG)
        loader = DataLoader(cfg)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            loader.load_magnetics()
        bh11_warns = [x for x in w if 'BH-11' in str(x.message)]
        assert len(bh11_warns) == 0, (
            f"Kayad example magnetics are correctly in µSI — no BH-11 warning expected. "
            f"Got: {[str(x.message) for x in bh11_warns]}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Integration: all fixes together — full mini-pipeline smoke test
# ─────────────────────────────────────────────────────────────────────────────

class TestIntegrationBH08to11:

    @pytest.mark.skipif(not os.path.exists(EXAMPLE_CONFIG),
                        reason="Kayad example not present")
    def test_kayad_pipeline_runs_without_error(self):
        """Full smoke test: load → drill → geophys → score.
        Must complete mRL 235 scoring without any exception."""
        from bhumi3dmapper.modules.m01_data_loader import DataLoader
        from bhumi3dmapper.modules.m02_drill_processor import DrillProcessor
        from bhumi3dmapper.modules.m03_geophys_processor import GeophysicsProcessor
        from bhumi3dmapper.modules.m04_scoring_engine import compute_proximity, compute_blind

        cfg = ProjectConfig.from_json(EXAMPLE_CONFIG)
        loader = DataLoader(cfg)
        collar  = loader.load_collar()
        litho   = loader.load_litho()
        survey  = loader.load_survey()
        grav    = loader.load_gravity()
        mag     = loader.load_magnetics()

        dp = DrillProcessor(cfg)
        dp.build_lookups(collar, litho, survey_df=survey)
        gp = GeophysicsProcessor(cfg)
        gp.load(grav, mag)

        g = cfg.grid
        cols = np.arange(g.nx); rows = np.arange(g.ny)
        CC, CR = np.meshgrid(cols, rows)
        cell_E = (g.xmin + (CC + 0.5) * g.cell_size_m).astype(np.float32).ravel()
        cell_N = (g.ymin + (CR + 0.5) * g.cell_size_m).astype(np.float32).ravel()
        dist_ore = np.full(len(cell_E), 9999.0, np.float32)

        # Only test one level for speed
        z = 235.0
        lv, pg, csr = dp.geology_at_level(z)
        gf = gp.at_level(z)
        inputs = {
            'lv': lv, 'pg': pg, 'csr': csr,
            'grav': gf['grav'], 'grav_raw': gf['grav_raw'],
            'grav_gradient': gf['grav_gradient'], 'grav_laplacian': gf['grav_laplacian'],
            'mag': gf['mag'], 'mag_gradient': gf['mag_gradient'],
            'cell_E': cell_E, 'cell_N': cell_N,
            'z_mrl': z, 'regime_id': 2,
            'dist_ore': dist_ore, 'ore_area': 50000,
            'grav_mean': gf['grav_mean'], 'grav_std': gf['grav_std'],
            'mag_mean': gf['mag_mean'],   'mag_std':  gf['mag_std'],
            'gg_mean':  gf['gg_mean'],    'gg_std':   gf['gg_std'],
            'lap_std':  gf['lap_std'],    'mg_p50':   gf['mg_p50'],
            'block_model_df': None,
        }
        pr = compute_proximity(inputs, cfg)
        br = compute_blind(inputs, cfg)

        assert 'score' in pr and 'score' in br
        assert pr['score'].shape == (g.nx * g.ny,)
        assert float(pr['score'].max()) <= 100.0
        assert float(br['score'].max()) <= 100.0
        # Amphibolite cells must be hard-vetoed at 20.0
        amp_mask = lv == 2
        if amp_mask.any():
            assert float(pr['score'][amp_mask].max()) == 20.0, (
                "Amphibolite cells must be capped at 20.0 by hard veto"
            )
        # At least some cells with CSR (code 4) should score above veto cap
        csr_mask = lv == 4
        if csr_mask.any():
            assert float(pr['score'][csr_mask].max()) > 20.0, (
                "CSR cells should score above the Amphibolite veto cap"
            )
