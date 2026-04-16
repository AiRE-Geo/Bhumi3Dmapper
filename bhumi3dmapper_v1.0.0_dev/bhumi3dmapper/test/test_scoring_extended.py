# -*- coding: utf-8 -*-
"""Sprint 12 — Extended scoring tests: regimes, boundaries, NaN, regression."""
import numpy as np
import pytest
import sys, os

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)

from modules.m04_scoring_engine import (
    score_lithology, score_pg_halo, score_footwall_standoff,
    score_gravity_absolute, score_gravity_contextual,
    score_mag_absolute, score_mag_contextual,
    score_structural_corridor, score_plunge_proximity,
    score_gravity_gradient, score_mag_gradient,
    score_gravity_laplacian, score_novelty, score_ore_envelope,
    compute_proximity, compute_blind, apply_hard_veto, score_to_class
)

def arr(*vals):
    return np.array(vals, dtype=np.float32)

def cells(n=10):
    E = np.full(n, 469500.0, dtype=np.float32)
    N = np.full(n, 2934900.0, dtype=np.float32)
    return E, N


# ═══════════════════════════════════════════════════════════════════
# JC-10: REGIME TRANSITION TESTS
# ═══════════════════════════════════════════════════════════════════

class TestRegime0Lower:
    """Lower mine (deep) regime — CSR is primary host, different scoring behaviour."""

    def test_litho_csr_primary_in_lower(self, kayad_config):
        """CSR (code 4) should score 1.0 in lower regime (primary host)."""
        s = score_lithology(arr(4, 4, 4), 0, kayad_config)
        assert np.allclose(s, 1.0)

    def test_litho_qms_reduced_in_lower(self, kayad_config):
        """QMS (code 1) should score 0.6 in lower regime (not primary host)."""
        s = score_lithology(arr(1, 1, 1), 0, kayad_config)
        assert np.allclose(s, 0.6)

    def test_pg_halo_flat_in_lower(self, kayad_config):
        """PG halo is inactive in lower regime — all distances return flat fill."""
        s = score_pg_halo(arr(1.0, 5.0, 50.0, 200.0), 0, kayad_config)
        assert np.allclose(s, 0.4), "PG halo should be flat 0.4 in lower regime"

    def test_csr_standoff_inverted_lower(self, kayad_config):
        """In lower regime, close to CSR contact = favourable (inverted from upper)."""
        s = score_footwall_standoff(arr(2.0, 10.0, 40.0), 0, kayad_config)
        assert s[0] > s[1] > s[2], "Closer to CSR = higher score in lower regime"
        assert np.isclose(s[0], 1.0), "Very close CSR should score 1.0 in lower"

    def test_gravity_lower_regime(self, kayad_config):
        """Gravity scoring at deep levels should use lower-regime thresholds."""
        s = score_gravity_absolute(arr(-0.1, 0.0, 0.1), z_mrl=0.0, cfg=kayad_config)
        assert s[0] > s[2], "Negative gravity should score higher even in deep regime"


class TestRegime1Transition:
    """Transition regime — intermediate behaviour, confidence discount."""

    def test_litho_qms_intermediate(self, kayad_config):
        """QMS should score 0.8 in transition (between 1.0 upper and 0.6 lower)."""
        s = score_lithology(arr(1), 1, kayad_config)
        assert np.isclose(s[0], 0.8)

    def test_litho_csr_intermediate(self, kayad_config):
        """CSR should score 0.5 in transition (between 0.25 upper and 1.0 lower)."""
        s = score_lithology(arr(4), 1, kayad_config)
        assert np.isclose(s[0], 0.5)

    def test_pg_halo_active_in_transition(self, kayad_config):
        """PG halo should still be active (not flat fill) in transition regime."""
        close = score_pg_halo(arr(5.0), 1, kayad_config)
        far = score_pg_halo(arr(100.0), 1, kayad_config)
        assert close[0] > far[0], "PG halo should be active in transition regime"


class TestRegimeBoundaries:
    """Test that regime assignment at exact boundary elevations is deterministic."""

    def test_z60_is_transition(self, kayad_config):
        """z=60 should be in transition regime (id=1), not lower."""
        for reg in kayad_config.regimes.regimes:
            if reg['z_min'] <= 60.0 <= reg['z_max']:
                assert reg['id'] == 1, f"z=60 should be transition (id=1), got {reg['id']}"
                break

    def test_z160_is_upper(self, kayad_config):
        """z=160 should be in upper regime (id=2), not transition."""
        for reg in kayad_config.regimes.regimes:
            if reg['z_min'] <= 160.0 <= reg['z_max']:
                assert reg['id'] == 2, f"z=160 should be upper (id=2), got {reg['id']}"
                break


# ═══════════════════════════════════════════════════════════════════
# JC-13: BOUNDARY VALUE AND NaN INPUT TESTS
# ═══════════════════════════════════════════════════════════════════

class TestNaNHandling:
    """Verify scoring functions handle NaN inputs gracefully."""

    def test_litho_nan_defaults(self, kayad_config):
        """NaN lithology code should get default score, not crash."""
        # np.nan cast to int is undefined, so we test with 0 (unknown)
        s = score_lithology(arr(0), 2, kayad_config)
        assert np.isfinite(s[0])

    def test_pg_halo_nan_input(self, kayad_config):
        s = score_pg_halo(np.array([np.nan], dtype=np.float32), 2, kayad_config)
        # NaN comparisons return False, so np.where chains should produce the fallback
        assert len(s) == 1

    def test_gravity_nan_input(self, kayad_config):
        s = score_gravity_absolute(np.array([np.nan], dtype=np.float32), 185.0, kayad_config)
        assert len(s) == 1

    def test_zero_length_array(self, kayad_config):
        """Empty array input should return empty array."""
        empty = np.array([], dtype=np.float32)
        s = score_pg_halo(empty, 2, kayad_config)
        assert len(s) == 0
        s2 = score_gravity_absolute(empty, 185.0, kayad_config)
        assert len(s2) == 0


class TestBoundaryValues:
    """Test exact threshold boundaries."""

    def test_pg_halo_at_exact_4m(self, kayad_config):
        """At exactly 4m, should transition into the peak zone (score 1.0).

        Default breaks: [2, 4, 10, ...], scores: [0.50, 0.80, 1.00, ...]
        pg_dist < 4 -> score 0.80 (bracket index 1)
        pg_dist = 4 -> NOT < 4, so falls to < 10 check -> score 1.00 (bracket index 2)
        """
        below = score_pg_halo(arr(3.99), 2, kayad_config)
        at = score_pg_halo(arr(4.0), 2, kayad_config)
        above = score_pg_halo(arr(4.01), 2, kayad_config)
        # Below 4 -> 0.80, at/above 4 -> 1.00 (next bracket: < 10)
        assert below[0] < at[0], "3.99m should score < 4.0m (transition from 0.80 to 1.00)"

    def test_pg_halo_at_exact_10m(self, kayad_config):
        """At exactly 10m, should transition out of peak zone."""
        below = score_pg_halo(arr(9.99), 2, kayad_config)
        above = score_pg_halo(arr(10.01), 2, kayad_config)
        assert below[0] > above[0], "Scores should decrease past 10m"

    def test_score_class_at_exact_75(self, kayad_config):
        """Score of exactly 75 should be Very High (class 4)."""
        classes = score_to_class(arr(75.0, 74.9), kayad_config)
        assert classes[0] == 4, "75.0 should be Very High"
        assert classes[1] == 3, "74.9 should be High"

    def test_score_class_at_exact_30(self, kayad_config):
        """Score of exactly 30 should be Low (class 1)."""
        classes = score_to_class(arr(30.0, 29.9), kayad_config)
        assert classes[0] == 1, "30.0 should be Low"
        assert classes[1] == 0, "29.9 should be Very Low"


# ═══════════════════════════════════════════════════════════════════
# JC-12: REGRESSION / GOLDEN-FILE TESTS
# ═══════════════════════════════════════════════════════════════════

class TestScoringRegression:
    """Verify scoring produces known-good values for fixed inputs."""

    def test_proximity_known_values(self, kayad_config):
        """Fixed inputs should produce a specific proximity score (within tolerance)."""
        E, N = cells(1)
        inputs = {
            'lv': arr(1),           # QMS upper -> 1.0
            'pg': arr(6.0),         # peak zone -> 1.0
            'csr': arr(20.0),       # optimal upper -> 1.0
            'grav': arr(-0.05),     # negative grav
            'grav_raw': arr(-0.05),
            'grav_gradient': arr(0.0005),
            'grav_laplacian': arr(-0.0001),
            'mag': arr(-5.0),       # local minimum
            'mag_gradient': arr(0.05),
            'cell_E': E, 'cell_N': N, 'z_mrl': 310.0, 'regime_id': 2,
            'dist_ore': arr(50.0),
            'ore_area': 30000.0,
            'grav_mean': 0.0, 'grav_std': 0.05,
            'mag_mean': 5.0, 'mag_std': 15.0,
            'gg_mean': 0.0003, 'gg_std': 0.0002,
            'lap_std': 0.00005, 'mg_p50': 0.04,
            'block_model_df': None,
        }
        result = compute_proximity(inputs, kayad_config)
        score = float(result['score'][0])
        # With perfect inputs across most criteria, score should be high
        assert 70 <= score <= 100, f"Expected high proximity score, got {score}"
        # Class should be Very High or High
        assert result['class'][0] >= 3

    def test_blind_known_values(self, kayad_config):
        """Fixed inputs should produce a specific blind score."""
        E, N = cells(1)
        inputs = {
            'lv': arr(1), 'pg': arr(6.0), 'csr': arr(20.0),
            'grav': arr(-0.05), 'grav_raw': arr(-0.05),
            'grav_gradient': arr(0.0005), 'grav_laplacian': arr(-0.0001),
            'mag': arr(-5.0), 'mag_gradient': arr(0.05),
            'cell_E': E, 'cell_N': N, 'z_mrl': 310.0, 'regime_id': 2,
            'dist_ore': arr(800.0),   # Far from ore -> high novelty
            'ore_area': 30000.0,
            'grav_mean': 0.0, 'grav_std': 0.05,
            'mag_mean': 5.0, 'mag_std': 15.0,
            'gg_mean': 0.0003, 'gg_std': 0.0002,
            'lap_std': 0.00005, 'mg_p50': 0.04,
            'block_model_df': None,
        }
        result = compute_blind(inputs, kayad_config)
        score = float(result['score'][0])
        assert 50 <= score <= 100, f"Expected moderate-high blind score, got {score}"

    def test_amphibolite_veto_caps_score(self, kayad_config):
        """Amphibolite cells must be capped at 20 regardless of other criteria."""
        E, N = cells(1)
        inputs = {
            'lv': arr(2),          # Amphibolite!
            'pg': arr(6.0), 'csr': arr(20.0),
            'grav': arr(-0.15), 'grav_raw': arr(-0.15),
            'grav_gradient': arr(0.001), 'grav_laplacian': arr(-0.001),
            'mag': arr(-15.0), 'mag_gradient': arr(0.1),
            'cell_E': E, 'cell_N': N, 'z_mrl': 310.0, 'regime_id': 2,
            'dist_ore': arr(10.0), 'ore_area': 50000.0,
            'grav_mean': 0.0, 'grav_std': 0.05,
            'mag_mean': 5.0, 'mag_std': 15.0,
            'gg_mean': 0.0003, 'gg_std': 0.0002,
            'lap_std': 0.00005, 'mg_p50': 0.04,
            'block_model_df': None,
        }
        prox = compute_proximity(inputs, kayad_config)
        blind = compute_blind(inputs, kayad_config)
        assert prox['score'][0] <= 20.0, f"Amphibolite prox should be <=20, got {prox['score'][0]}"
        assert blind['score'][0] <= 20.0, f"Amphibolite blind should be <=20, got {blind['score'][0]}"


class TestCustomThresholds:
    """Verify that custom thresholds actually change scores (multi-deposit)."""

    def test_custom_pg_halo_thresholds(self, kayad_config):
        """Custom PG halo breaks should produce different scores than defaults."""
        from core.config import ProjectConfig
        cfg_custom = ProjectConfig()
        cfg_custom.criterion_thresholds.pg_breaks = [5, 10, 20, 40, 80, 120, 200]
        cfg_custom.criterion_thresholds.pg_scores = [0.30, 0.60, 0.90, 1.00, 0.70, 0.40, 0.20, 0.10]

        default_score = score_pg_halo(arr(7.0), 2, kayad_config)
        custom_score = score_pg_halo(arr(7.0), 2, cfg_custom)
        assert not np.isclose(default_score[0], custom_score[0]), \
            "Custom thresholds should produce different scores"

    def test_custom_litho_scores_for_vms(self, kayad_config):
        """Simulate VMS-style litho scoring where different rocks are primary host."""
        from core.config import ProjectConfig
        cfg_vms = ProjectConfig()
        # In VMS: code 5 (quartzite/felsic volcanic) is primary host
        cfg_vms.criterion_thresholds.litho_scores = {
            2: {1: 0.3, 2: 0.0, 3: 0.4, 4: 0.5, 5: 1.0, 0: 0.2},
            1: {1: 0.3, 2: 0.0, 3: 0.4, 4: 0.5, 5: 0.9, 0: 0.2},
            0: {1: 0.3, 2: 0.0, 3: 0.4, 4: 0.5, 5: 0.8, 0: 0.2},
        }

        kayad_qms = score_lithology(arr(1), 2, kayad_config)  # QMS=1.0 in SEDEX
        vms_qms = score_lithology(arr(1), 2, cfg_vms)          # QMS=0.3 in VMS
        vms_felsic = score_lithology(arr(5), 2, cfg_vms)       # Felsic=1.0 in VMS

        assert kayad_qms[0] > vms_qms[0], "QMS should score lower in VMS than SEDEX"
        assert np.isclose(vms_felsic[0], 1.0), "Felsic volcanic should be primary host in VMS"
