# -*- coding: utf-8 -*-
"""Sprint 3 — Criterion function tests. No QGIS needed."""
import numpy as np
import pytest
import sys
import os

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)

from modules.m04_scoring_engine import (
    score_lithology, score_pg_halo, score_footwall_standoff,
    score_gravity_absolute, score_gravity_contextual,
    score_mag_absolute, score_mag_contextual,
    score_structural_corridor, score_plunge_proximity,
    score_gravity_gradient, score_mag_gradient,
    score_gravity_laplacian, score_novelty,
    compute_proximity, compute_blind, apply_hard_veto, score_to_class
)


# ── Helpers ────────────────────────────────────────────────────────────────
def arr(*vals):
    return np.array(vals, dtype=np.float32)


def cells(n=10):
    E = np.full(n, 469500.0, dtype=np.float32)
    N = np.full(n, 2934900.0, dtype=np.float32)
    return E, N


# ── C1 — Lithology ─────────────────────────────────────────────────────────
def test_litho_qms_upper(kayad_config):
    s = score_lithology(arr(1, 1, 1), 2, kayad_config)
    assert np.allclose(s, 1.0), "QMS in upper regime should score 1.0"


def test_litho_amphibolite_always_zero(kayad_config):
    for regime in [0, 1, 2]:
        s = score_lithology(arr(2), regime, kayad_config)
        assert s[0] == 0.0, f"Amphibolite must score 0.0 in all regimes (regime={regime})"


def test_litho_csr_lower(kayad_config):
    s = score_lithology(arr(4), 0, kayad_config)
    assert s[0] == 1.0, "CSR in lower regime should score 1.0"


# ── C2 — PG halo ────────────────────────────────────────────────────────────
def test_pg_halo_peak_zone():
    s = score_pg_halo(arr(5.0, 7.0, 9.0), regime_id=2)
    assert np.all(s == 1.0), "4–10m PG halo should score 1.0"


def test_pg_halo_immediate_contact():
    s = score_pg_halo(arr(1.0), regime_id=2)
    assert s[0] < 1.0, "0–2m (immediate contact) should score < 1.0"


def test_pg_halo_inactive_lower():
    s = score_pg_halo(arr(5.0, 100.0), regime_id=0)
    assert np.allclose(s, 0.4), "PG halo inactive in lower regime — flat 0.4"


# ── C3 — CSR standoff ──────────────────────────────────────────────────────
def test_csr_standoff_optimal_upper():
    s = score_footwall_standoff(arr(15.0, 25.0, 35.0), regime_id=2)
    assert np.all(s == 1.0), "10–40m standoff = 1.0 in upper regime"


def test_csr_contact_optimal_lower():
    s = score_footwall_standoff(arr(2.0, 4.0), regime_id=0)
    assert np.all(s == 1.0), "<5m CSR standoff = 1.0 in lower regime (inverted)"


def test_csr_poor_standoff_upper():
    s = score_footwall_standoff(arr(200.0), regime_id=2)
    assert s[0] < 0.3, "200m standoff should score poorly"


# ── C4 — Gravity ───────────────────────────────────────────────────────────
def test_gravity_absolute_strong_negative():
    s = score_gravity_absolute(arr(-0.15, -0.05, 0.0, 0.5), z_mrl=310.0)
    assert s[0] > s[1] > s[2] > s[3], "More negative gravity → higher score"


def test_gravity_contextual_negative_wins():
    s = score_gravity_contextual(arr(-2.0, 0.0, 2.0), grav_mean=0.0, grav_std=1.0)
    assert s[0] > s[1] > s[2], "Z-score < 0 should score higher"


# ── C5 — Magnetics ─────────────────────────────────────────────────────────
def test_mag_absolute_local_minimum():
    s = score_mag_absolute(arr(-15.0, -5.0, 5.0, 50.0))
    assert s[0] > s[1] > s[2] > s[3], "More negative mag → higher score"


def test_mag_contextual_local_minimum():
    s = score_mag_contextual(arr(-20.0, 0.0, 20.0), mag_mean=0.0, mag_std=10.0)
    assert s[0] > s[1] > s[2]


# ── C6 — Structural corridor ──────────────────────────────────────────────
def test_corridor_near_axis_high(kayad_config):
    # Cells right on the corridor anchor should score high
    E = np.array([469519.0], dtype=np.float32)
    N = np.array([2934895.0], dtype=np.float32)
    s, ax_E, ax_N = score_structural_corridor(E, N, 185.0, kayad_config, 2)
    assert s[0] >= 0.8, f"Cell on corridor axis should score >= 0.8, got {s[0]}"


def test_corridor_far_from_axis_low(kayad_config):
    E = np.array([470500.0], dtype=np.float32)
    N = np.array([2934000.0], dtype=np.float32)
    s, _, _ = score_structural_corridor(E, N, 185.0, kayad_config, 2)
    assert s[0] <= 0.3, f"Cell 1km from axis should score low, got {s[0]}"


# ── C7 — Plunge proximity ─────────────────────────────────────────────────
def test_plunge_near_axis():
    s = score_plunge_proximity(arr(469519.0), arr(2934895.0), 469519.0, 2934895.0)
    assert s[0] == 1.0, "Cell at plunge axis should score 1.0"


# ── Hard veto ──────────────────────────────────────────────────────────────
def test_hard_veto_amphibolite(kayad_config):
    lv = arr(2, 1, 1)
    scores = arr(95.0, 90.0, 85.0)
    result = apply_hard_veto(scores, lv, kayad_config)
    assert result[0] <= 20.0, "Amphibolite must be capped at 20"
    assert result[1] == 90.0, "QMS must be unaffected"
    assert result[2] == 85.0, "QMS must be unaffected"


# ── Score classification ────────────────────────────────────────────────────
def test_score_classes(kayad_config):
    scores = arr(80.0, 65.0, 50.0, 35.0, 20.0)
    classes = score_to_class(scores, kayad_config)
    assert list(classes) == [4, 3, 2, 1, 0], \
        "Expected [VH, H, M, L, VL] = [4,3,2,1,0]"


# ── Gravity gradient (blind C7b) ──────────────────────────────────────────
def test_gravity_gradient_returns_valid():
    gg = arr(0.0003, 0.001, 0.005)
    grav = arr(-0.05, 0.0, 0.1)
    s = score_gravity_gradient(gg, grav, grav_mean=0.0, gg_mean=0.0003, gg_std=0.0002)
    assert np.all((s >= 0) & (s <= 1))


def test_gravity_gradient_g90_branch():
    """Verify the g90 branch is reachable (was dead code before JC-02 fix)."""
    gg_mean, gg_std = 0.0003, 0.0002
    g40 = gg_mean + 0.15 * gg_std   # 0.00033
    g80 = gg_mean + 0.95 * gg_std   # 0.00049
    g90 = gg_mean + 1.40 * gg_std   # 0.00058
    # Value well above g90
    above_g90 = arr(0.001)
    grav = arr(0.1)  # above mean, no bonus
    s = score_gravity_gradient(above_g90, grav, grav_mean=0.0,
                                gg_mean=gg_mean, gg_std=gg_std)
    assert np.isclose(s[0], 0.35), f"Above g90 should score 0.35, got {s[0]}"
    # Value between g80 and g90
    between_g80_g90 = arr(0.00053)
    s2 = score_gravity_gradient(between_g80_g90, grav, grav_mean=0.0,
                                 gg_mean=gg_mean, gg_std=gg_std)
    assert np.isclose(s2[0], 0.55), f"Between g80-g90 should score 0.55, got {s2[0]}"
    # Value between g40 and g80
    between_g40_g80 = arr(0.00040)
    s3 = score_gravity_gradient(between_g40_g80, grav, grav_mean=0.0,
                                 gg_mean=gg_mean, gg_std=gg_std)
    assert np.isclose(s3[0], 0.90), f"Between g40-g80 should score 0.90, got {s3[0]}"
    # Value below mean
    below_mean = arr(0.0001)
    s4 = score_gravity_gradient(below_mean, grav, grav_mean=0.0,
                                 gg_mean=gg_mean, gg_std=gg_std)
    assert np.isclose(s4[0], 0.25), f"Below mean should score 0.25, got {s4[0]}"


# ── Mag gradient (blind C8) ──────────────────────────────────────────────
def test_mag_gradient_returns_valid():
    mg = arr(0.02, 0.05, 0.1)
    mag = arr(-5.0, 0.0, 10.0)
    s = score_mag_gradient(mg, mag, mag_mean=5.0, mg_p50=0.04)
    assert np.all((s >= 0) & (s <= 1))


# ── Laplacian (blind C9) ─────────────────────────────────────────────────
def test_laplacian_negative_scores_high():
    lap = arr(-0.001, 0.0, 0.001)
    s = score_gravity_laplacian(lap, lap_std=0.0005)
    assert s[0] > s[1] > s[2], "Negative Laplacian should score highest"


# ── Novelty ──────────────────────────────────────────────────────────────
def test_novelty_decreases_near_ore(kayad_config):
    s = score_novelty(arr(1000.0, 500.0, 200.0, 50.0), kayad_config)
    assert s[0] > s[1] > s[2] > s[3], \
        "Novelty score must decrease as distance to known ore decreases"


# ── Score range invariant ───────────────────────────────────────────────────
def test_proximity_score_in_range(kayad_config):
    E, N = cells()
    inputs = {
        'lv': arr(1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
        'pg': arr(6, 6, 6, 6, 6, 6, 6, 6, 6, 6),
        'csr': arr(20, 20, 20, 20, 20, 20, 20, 20, 20, 20),
        'grav': np.full(10, -0.05, dtype=np.float32),
        'grav_raw': np.full(10, -0.05, dtype=np.float32),
        'grav_gradient': np.full(10, 0.0005, dtype=np.float32),
        'grav_laplacian': np.full(10, -0.0001, dtype=np.float32),
        'mag': np.full(10, -5.0, dtype=np.float32),
        'mag_gradient': np.full(10, 0.05, dtype=np.float32),
        'cell_E': E, 'cell_N': N, 'z_mrl': 185.0, 'regime_id': 2,
        'dist_ore': np.full(10, 50.0, dtype=np.float32),
        'ore_area': 30000.0,
        'grav_mean': 0.0, 'grav_std': 0.05,
        'mag_mean': 5.0, 'mag_std': 15.0,
        'gg_mean': 0.0003, 'gg_std': 0.0002,
        'lap_std': 0.00005, 'mg_p50': 0.04,
        'block_model_df': None,
    }
    result = compute_proximity(inputs, kayad_config)
    assert 0 <= result['score'].min() <= result['score'].max() <= 100, \
        "All proximity scores must be in [0, 100]"
    result_b = compute_blind(inputs, kayad_config)
    assert 0 <= result_b['score'].min() <= result_b['score'].max() <= 100, \
        "All blind scores must be in [0, 100]"
