"""
Module 04 — Scoring Engine
============================
Vectorized scoring functions for all criteria in both models.
All weights and thresholds come from ProjectConfig — no hardcoded values.

To add a new criterion:
  1. Write a score_<name>(inputs, cfg) function returning np.ndarray[float32, 0-1]
  2. Add it to compute_proximity() or compute_blind() with its weight key
  3. Add the weight key to ScoringWeightsConfig in config.py
"""
import math, numpy as np, os, warnings
warnings.filterwarnings('ignore')

try:
    from core.config import ProjectConfig, ScoringWeightsConfig, StructuralConfig
except ImportError:
    import sys; sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from core.config import ProjectConfig, ScoringWeightsConfig, StructuralConfig


# ══════════════════════════════════════════════════════════════════════════════
# INDIVIDUAL CRITERION FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def score_lithology(lv: np.ndarray, regime_id: int, cfg: ProjectConfig,
                    litho_scores: dict = None) -> np.ndarray:
    """
    C1 — Lithology. Score based on host rock type.
    litho_scores: override per-regime score table.
    Default: primary host=1.0 upper, secondary host=1.0 lower, hard veto=0.
    """
    if litho_scores is None:
        # Default score tables per regime_id
        litho_scores = {
            2: {1: 1.0, 2: 0.0, 3: 0.30, 4: 0.25, 5: 0.40, 0: 0.25},  # upper
            1: {1: 0.8, 2: 0.0, 3: 0.30, 4: 0.50, 5: 0.40, 0: 0.30},  # transition
            0: {1: 0.6, 2: 0.0, 3: 0.30, 4: 1.00, 5: 0.40, 0: 0.30},  # lower
        }
    tbl = litho_scores.get(regime_id, litho_scores.get(0, {}))
    return np.array([tbl.get(int(x), 0.25) for x in lv], dtype=np.float32)


def score_pg_halo(pg_dist: np.ndarray, regime_id: int) -> np.ndarray:
    """C2 — Structural marker (PG) contact halo. Inactive in lower regime."""
    if regime_id == 0:
        return np.full(len(pg_dist), 0.4, dtype=np.float32)
    return np.where(pg_dist < 2,  0.50,
           np.where(pg_dist < 4,  0.80,
           np.where(pg_dist < 10, 1.00,
           np.where(pg_dist < 15, 0.70,
           np.where(pg_dist < 20, 0.50,
           np.where(pg_dist < 30, 0.35,
           np.where(pg_dist < 50, 0.25, 0.15))))))).astype(np.float32)


def score_footwall_standoff(standoff: np.ndarray, regime_id: int) -> np.ndarray:
    """C3 — Footwall (CSR) standoff. Inverts below transition."""
    if regime_id == 0:  # lower: contact = favourable
        return np.where(standoff < 5,  1.00,
               np.where(standoff < 15, 0.70,
               np.where(standoff < 30, 0.45, 0.25))).astype(np.float32)
    return np.where(standoff < 5,   0.40,
           np.where(standoff < 10,  0.65,
           np.where(standoff < 40,  1.00,
           np.where(standoff < 60,  0.70,
           np.where(standoff < 100, 0.40, 0.20))))).astype(np.float32)


def score_gravity_absolute(grav: np.ndarray, z_mrl: float) -> np.ndarray:
    """C4 — Gravity (proximity model): absolute mGal thresholds."""
    if z_mrl >= 310:
        return np.where(grav < -0.10, 0.95,
               np.where(grav < -0.03, 0.80,
               np.where(grav <  0.05, 0.60,
               np.where(grav <  0.30, 0.40,
               np.where(grav <  0.80, 0.25, 0.10))))).astype(np.float32)
    elif z_mrl >= 160:
        return np.where(grav < 0,    0.75,
               np.where(grav < 0.05, 0.60,
               np.where(grav < 0.10, 0.45, 0.30))).astype(np.float32)
    else:
        return np.where(grav < 0,    0.65,
               np.where(grav < 0.05, 0.55, 0.40)).astype(np.float32)


def score_gravity_contextual(grav: np.ndarray, grav_mean: float,
                              grav_std: float) -> np.ndarray:
    """C4 — Gravity (blind model): z-score relative to level mean."""
    zn = (grav - grav_mean) / max(grav_std, 0.001)
    return np.where(zn < -1.5, 1.00,
           np.where(zn < -0.75, 0.90,
           np.where(zn < -0.25, 0.75,
           np.where(zn <  0.0,  0.60,
           np.where(zn <  0.5,  0.45,
           np.where(zn <  1.0,  0.30, 0.15)))))).astype(np.float32)


def score_mag_absolute(mag: np.ndarray) -> np.ndarray:
    """C5 — Magnetics (proximity model): absolute µSI thresholds."""
    return np.where(mag < -10, 1.00,
           np.where(mag <  -5, 0.90,
           np.where(mag <   0, 0.75,
           np.where(mag <  10, 0.60,
           np.where(mag <  30, 0.40,
           np.where(mag <  60, 0.25, 0.12)))))).astype(np.float32)


def score_mag_contextual(mag: np.ndarray, mag_mean: float,
                         mag_std: float) -> np.ndarray:
    """C5 — Magnetics (blind model): z-score."""
    zm = (mag - mag_mean) / max(mag_std, 1.0)
    return np.where(zm < -1.5, 1.00,
           np.where(zm < -0.75, 0.90,
           np.where(zm < -0.25, 0.75,
           np.where(zm <  0.0,  0.60,
           np.where(zm <  0.5,  0.45,
           np.where(zm <  1.0,  0.30, 0.15)))))).astype(np.float32)


def score_structural_corridor(cell_E: np.ndarray, cell_N: np.ndarray,
                               z_mrl: float,
                               cfg: ProjectConfig,
                               regime_id: int) -> tuple:
    """
    C6 — Structural corridor.
    Returns (score, axis_E, axis_N) for the active corridor at this level.
    """
    sc   = cfg.structure
    br   = sc.score_breaks_m
    sv   = sc.score_values

    # Find active corridor for this level and regime
    active = None
    for corr in sc.corridors:
        if corr['z_bot_mrl'] <= z_mrl <= corr['z_top_mrl']:
            active = corr; break
    if active is None:
        active = sc.corridors[0]

    az_r  = math.radians(active['azimuth_deg'])
    dz    = active['anchor_mRL'] - z_mrl
    ax_E  = active['anchor_E'] + dz * active.get('lateral_E_per_100m_down', 0) / 100
    ax_N  = active['anchor_N'] + dz * active.get('lateral_N_per_100m_down', 0) / 100

    # Perpendicular distance to corridor axis
    dEv   = cell_E - ax_E
    dNv   = cell_N - ax_N
    ue    = math.sin(az_r); un = math.cos(az_r)
    perp  = np.abs(-dEv * un + dNv * ue)

    score = np.full(len(cell_E), sv[-1], dtype=np.float32)
    for i in range(len(br) - 1, -1, -1):
        score = np.where(perp < br[i], sv[i], score)

    return score, ax_E, ax_N


def score_plunge_proximity(cell_E: np.ndarray, cell_N: np.ndarray,
                            ax_E: float, ax_N: float) -> np.ndarray:
    """
    C7 — Plunge axis proximity (PROXIMITY-BIASED).
    Rewards cells near the projected centre of the known ore shoot.
    """
    d = np.sqrt((cell_E - ax_E)**2 + (cell_N - ax_N)**2)
    return np.where(d < 75,  1.00,
           np.where(d < 150, 0.80,
           np.where(d < 300, 0.55,
           np.where(d < 600, 0.30, 0.10)))).astype(np.float32)


def score_gravity_gradient(grav_grad: np.ndarray, grav: np.ndarray,
                            grav_mean: float, gg_mean: float,
                            gg_std: float) -> np.ndarray:
    """C7b — Gravity gradient (blind model, replaces plunge proximity)."""
    g40 = gg_mean + 0.15 * gg_std
    g80 = gg_mean + 0.95 * gg_std
    g90 = gg_mean + 1.40 * gg_std
    c7b = np.where((grav_grad >= g40) & (grav_grad <= g80), 0.90,
          np.where((grav_grad >= gg_mean) & (grav_grad < g40), 0.70,
          np.where(grav_grad > g80, 0.55,
          np.where(grav_grad > g90, 0.35, 0.25)))).astype(np.float32)
    c7b = np.where(grav < grav_mean, c7b + 0.10, c7b)
    return np.clip(c7b, 0, 1).astype(np.float32)


def score_mag_gradient(mag_grad: np.ndarray, mag: np.ndarray,
                        mag_mean: float, mg_p50: float) -> np.ndarray:
    """C8 — Magnetic gradient (blind model)."""
    c8 = np.where(mag_grad >= mg_p50 * 1.5, 0.85,
         np.where(mag_grad >= mg_p50,       0.70,
         np.where(mag_grad >= mg_p50 * 0.5, 0.50, 0.25))).astype(np.float32)
    c8 = np.where(mag < mag_mean, c8 + 0.10, c8)
    return np.clip(c8, 0, 1).astype(np.float32)


def score_gravity_laplacian(laplacian: np.ndarray, lap_std: float) -> np.ndarray:
    """C9 — Gravity Laplacian (blind model). Negative = closed density deficit."""
    ln = laplacian / max(lap_std, 1e-8)
    return np.where(ln < -1.5,  1.00,
           np.where(ln < -0.75, 0.85,
           np.where(ln < -0.25, 0.65,
           np.where(ln <  0.0,  0.50,
           np.where(ln <  0.5,  0.35, 0.20))))).astype(np.float32)


def score_grade_model(cell_E: np.ndarray, cell_N: np.ndarray,
                      block_model_df, cfg: ProjectConfig) -> np.ndarray:
    """C9 — Grade model endorsement. Scores cells within known grade domains."""
    bmc    = cfg.block_model
    scores = np.zeros(len(cell_E), dtype=np.float32)
    if block_model_df is None or block_model_df.empty:
        return scores
    for domain, score in bmc.domain_scores.items():
        sub = block_model_df[block_model_df['domain'] == domain]
        if sub.empty: continue
        min_E = sub[bmc.col_xcenter].min() - 50; max_E = sub[bmc.col_xcenter].max() + 50
        min_N = sub[bmc.col_ycenter].min() - 50; max_N = sub[bmc.col_ycenter].max() + 50
        mask  = ((cell_E >= min_E) & (cell_E <= max_E) &
                 (cell_N >= min_N) & (cell_N <= max_N))
        scores = np.where(mask, np.maximum(scores, score), scores)
    return scores


def score_ore_envelope(dist_ore: np.ndarray, ore_area: float) -> np.ndarray:
    """C10 — Ore envelope proximity (PROXIMITY-BIASED)."""
    eq_r = max(math.sqrt(ore_area / math.pi) if ore_area > 0 else 50, 50)
    rat  = dist_ore / eq_r
    return np.where(rat < 0.5, 1.0,
           np.where(rat < 1.0, 0.8,
           np.where(rat < 2.0, 0.5,
           np.where(rat < 3.5, 0.3, 0.1)))).astype(np.float32)


def score_novelty(dist_ore: np.ndarray, cfg: ProjectConfig) -> np.ndarray:
    """C10 — Novelty (blind model). Rewards cells far from known ore."""
    nd = cfg.scoring.novelty_distance_m
    return np.where(dist_ore > nd * 1.5, 1.00,
           np.where(dist_ore > nd,       0.85,
           np.where(dist_ore > nd * 0.6, 0.65,
           np.where(dist_ore > nd * 0.3, 0.45,
           np.where(dist_ore > nd * 0.15,0.30, 0.15))))).astype(np.float32)


# ══════════════════════════════════════════════════════════════════════════════
# COMPOSITE SCORE BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def apply_hard_veto(scores: np.ndarray, lv: np.ndarray,
                    cfg: ProjectConfig) -> np.ndarray:
    veto_code = cfg.lithology.hard_veto_code
    cap       = cfg.lithology.veto_score_cap
    return np.where(lv == veto_code, np.minimum(scores, cap), scores)


def score_to_class(scores: np.ndarray, cfg: ProjectConfig) -> np.ndarray:
    th = cfg.scoring.thresholds
    return np.where(scores >= th.get('Very High', 75), 4,
           np.where(scores >= th.get('High',      60), 3,
           np.where(scores >= th.get('Moderate',  45), 2,
           np.where(scores >= th.get('Low',       30), 1, 0)))).astype(np.uint8)


def compute_proximity(inputs: dict, cfg: ProjectConfig) -> dict:
    """
    Compute all proximity model scores.
    inputs dict keys: lv, pg, csr, grav, mag, grav_gradient, grav_laplacian,
                      mag_gradient, cell_E, cell_N, z_mrl, regime_id,
                      dist_ore, ore_area, grav_mean, grav_std,
                      mag_mean, mag_std, gg_mean, gg_std, lap_std, mg_p50,
                      block_model_df (optional)
    """
    z     = inputs['z_mrl']
    rid   = inputs['regime_id']
    w     = cfg.scoring.proximity

    c1  = score_lithology(inputs['lv'], rid, cfg)
    c2  = score_pg_halo(inputs['pg'], rid)
    c3  = score_footwall_standoff(inputs['csr'], rid)
    c4  = score_gravity_absolute(inputs['grav'], z)
    c5  = score_mag_absolute(inputs['mag'])
    c6, ax_E, ax_N = score_structural_corridor(
            inputs['cell_E'], inputs['cell_N'], z, cfg, rid)
    c7  = score_plunge_proximity(inputs['cell_E'], inputs['cell_N'], ax_E, ax_N)
    c9  = score_grade_model(inputs['cell_E'], inputs['cell_N'],
                            inputs.get('block_model_df'), cfg)
    c10 = score_ore_envelope(inputs['dist_ore'], inputs.get('ore_area', 50000))

    W   = sum(w.values())
    raw = (c1  * w.get('c1_lithology', 2.0)
         + c2  * w.get('c2_pg_halo', 1.5)
         + c3  * w.get('c3_csr_standoff', 1.5)
         + c4  * w.get('c4_gravity', 0.8)
         + c5  * w.get('c5_magnetics', 1.0)
         + c6  * w.get('c6_structural_corridor', 1.5)
         + c7  * w.get('c7_plunge_proximity', 1.0)
         + c9  * w.get('c9_grade_model', 0.7)
         + c10 * w.get('c10_ore_envelope', 1.0))
    score = np.clip(np.round(raw / W * 100, 1), 0, 100).astype(np.float32)
    score = apply_hard_veto(score, inputs['lv'], cfg)
    return {'score': score, 'class': score_to_class(score, cfg),
            'c1':c1,'c2':c2,'c3':c3,'c4':c4,'c5':c5,
            'c6':c6,'c7':c7,'c9':c9,'c10':c10}


def compute_blind(inputs: dict, cfg: ProjectConfig) -> dict:
    """
    Compute all blind environment model scores.
    Same input dict as compute_proximity() — uses contextual geophysics.
    """
    z     = inputs['z_mrl']
    rid   = inputs['regime_id']
    w     = cfg.scoring.blind

    c1  = score_lithology(inputs['lv'], rid, cfg)
    c2  = score_pg_halo(inputs['pg'], rid)
    c3  = score_footwall_standoff(inputs['csr'], rid)
    c4  = score_gravity_contextual(inputs['grav'],
                                    inputs['grav_mean'], inputs['grav_std'])
    c5  = score_mag_contextual(inputs['mag'],
                                inputs['mag_mean'], inputs['mag_std'])
    c6, _, _ = score_structural_corridor(
            inputs['cell_E'], inputs['cell_N'], z, cfg, rid)
    c7b = score_gravity_gradient(inputs['grav_gradient'], inputs['grav'],
                                  inputs['grav_mean'], inputs['gg_mean'],
                                  inputs['gg_std'])
    c8  = score_mag_gradient(inputs['mag_gradient'], inputs['mag'],
                              inputs['mag_mean'], inputs['mg_p50'])
    c9l = score_gravity_laplacian(inputs['grav_laplacian'], inputs['lap_std'])
    c10 = score_novelty(inputs['dist_ore'], cfg)

    W   = sum(w.values())
    raw = (c1  * w.get('c1_lithology', 2.0)
         + c2  * w.get('c2_pg_halo', 1.5)
         + c3  * w.get('c3_csr_standoff', 1.5)
         + c4  * w.get('c4_contextual_gravity', 1.2)
         + c5  * w.get('c5_contextual_mag', 1.2)
         + c6  * w.get('c6_structural_corridor', 1.5)
         + c7b * w.get('c7b_grav_gradient', 0.9)
         + c8  * w.get('c8_mag_gradient', 0.9)
         + c9l * w.get('c9_laplacian', 0.8)
         + c10 * w.get('c10_novelty', 0.5))
    score = np.clip(np.round(raw / W * 100, 1), 0, 100).astype(np.float32)
    score = apply_hard_veto(score, inputs['lv'], cfg)
    return {'score': score, 'class': score_to_class(score, cfg),
            'c1':c1,'c2':c2,'c3':c3,'c4':c4,'c5':c5,
            'c6':c6,'c7b':c7b,'c8':c8,'c9_lap':c9l,'c10':c10}
