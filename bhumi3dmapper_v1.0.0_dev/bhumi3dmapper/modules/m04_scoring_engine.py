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
import math, numpy as np, os

try:
    from ..core.config import ProjectConfig, ScoringWeightsConfig, StructuralConfig
except ImportError:
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
    ct = cfg.criterion_thresholds
    if litho_scores is None:
        litho_scores = ct.litho_scores
    tbl = litho_scores.get(regime_id, litho_scores.get(0, {}))
    return np.array([tbl.get(int(x), ct.litho_default_score) for x in lv], dtype=np.float32)


def score_pg_halo(pg_dist: np.ndarray, regime_id: int, cfg: ProjectConfig = None) -> np.ndarray:
    """C2 — Structural marker (PG) contact halo. Inactive in lower regime."""
    if cfg is not None:
        ct = cfg.criterion_thresholds
        br, sv = ct.pg_breaks, ct.pg_scores
        fill = ct.pg_lower_fill
    else:
        br = [2, 4, 10, 15, 20, 30, 50]
        sv = [0.50, 0.80, 1.00, 0.70, 0.50, 0.35, 0.25, 0.15]
        fill = 0.4
    if regime_id == 0:
        return np.full(len(pg_dist), fill, dtype=np.float32)
    score = np.full(len(pg_dist), sv[-1], dtype=np.float32)
    for i in range(len(br) - 1, -1, -1):
        score = np.where(pg_dist < br[i], sv[i], score)
    return score


def score_footwall_standoff(standoff: np.ndarray, regime_id: int, cfg: ProjectConfig = None) -> np.ndarray:
    """C3 — Footwall (CSR) standoff. Inverts below transition."""
    if cfg is not None:
        ct = cfg.criterion_thresholds
    if regime_id == 0:  # lower: contact = favourable
        br = ct.csr_lower_breaks if cfg else [5, 15, 30]
        sv = ct.csr_lower_scores if cfg else [1.00, 0.70, 0.45, 0.25]
    else:
        br = ct.csr_upper_breaks if cfg else [5, 10, 40, 60, 100]
        sv = ct.csr_upper_scores if cfg else [0.40, 0.65, 1.00, 0.70, 0.40, 0.20]
    score = np.full(len(standoff), sv[-1], dtype=np.float32)
    for i in range(len(br) - 1, -1, -1):
        score = np.where(standoff < br[i], sv[i], score)
    return score


def score_gravity_absolute(grav: np.ndarray, z_mrl: float, cfg: ProjectConfig = None) -> np.ndarray:
    """C4 — Gravity (proximity model): absolute mGal thresholds."""
    if cfg is not None:
        ct = cfg.criterion_thresholds
        if z_mrl >= ct.grav_abs_z_upper:
            br, sv = ct.grav_abs_upper_breaks, ct.grav_abs_upper_scores
        elif z_mrl >= ct.grav_abs_z_mid:
            br, sv = ct.grav_abs_mid_breaks, ct.grav_abs_mid_scores
        else:
            br, sv = ct.grav_abs_lower_breaks, ct.grav_abs_lower_scores
    else:
        if z_mrl >= 310:
            br = [-0.10, -0.03, 0.05, 0.30, 0.80]
            sv = [0.95, 0.80, 0.60, 0.40, 0.25, 0.10]
        elif z_mrl >= 160:
            br = [0, 0.05, 0.10]
            sv = [0.75, 0.60, 0.45, 0.30]
        else:
            br = [0, 0.05]
            sv = [0.65, 0.55, 0.40]
    score = np.full(len(grav), sv[-1], dtype=np.float32)
    for i in range(len(br) - 1, -1, -1):
        score = np.where(grav < br[i], sv[i], score)
    return score


def score_gravity_contextual(grav: np.ndarray, grav_mean: float,
                              grav_std: float, cfg: ProjectConfig = None) -> np.ndarray:
    """C4 — Gravity (blind model): z-score relative to level mean."""
    if cfg is not None:
        ct = cfg.criterion_thresholds
        br, sv = ct.contextual_zscore_breaks, ct.contextual_zscore_scores
    else:
        br = [-1.5, -0.75, -0.25, 0.0, 0.5, 1.0]
        sv = [1.00, 0.90, 0.75, 0.60, 0.45, 0.30, 0.15]
    zn = (grav - grav_mean) / max(grav_std, 0.001)
    score = np.full(len(grav), sv[-1], dtype=np.float32)
    for i in range(len(br) - 1, -1, -1):
        score = np.where(zn < br[i], sv[i], score)
    return score


def score_mag_absolute(mag: np.ndarray, cfg: ProjectConfig = None) -> np.ndarray:
    """C5 — Magnetics (proximity model): absolute µSI thresholds."""
    if cfg is not None:
        ct = cfg.criterion_thresholds
        br, sv = ct.mag_abs_breaks, ct.mag_abs_scores
    else:
        br = [-10, -5, 0, 10, 30, 60]
        sv = [1.00, 0.90, 0.75, 0.60, 0.40, 0.25, 0.12]
    score = np.full(len(mag), sv[-1], dtype=np.float32)
    for i in range(len(br) - 1, -1, -1):
        score = np.where(mag < br[i], sv[i], score)
    return score


def score_mag_contextual(mag: np.ndarray, mag_mean: float,
                         mag_std: float, cfg: ProjectConfig = None) -> np.ndarray:
    """C5 — Magnetics (blind model): z-score."""
    if cfg is not None:
        ct = cfg.criterion_thresholds
        br, sv = ct.contextual_zscore_breaks, ct.contextual_zscore_scores
    else:
        br = [-1.5, -0.75, -0.25, 0.0, 0.5, 1.0]
        sv = [1.00, 0.90, 0.75, 0.60, 0.45, 0.30, 0.15]
    zm = (mag - mag_mean) / max(mag_std, 1.0)
    score = np.full(len(mag), sv[-1], dtype=np.float32)
    for i in range(len(br) - 1, -1, -1):
        score = np.where(zm < br[i], sv[i], score)
    return score


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
                            ax_E: float, ax_N: float, cfg: ProjectConfig = None) -> np.ndarray:
    """
    C7 — Plunge axis proximity (PROXIMITY-BIASED).
    Rewards cells near the projected centre of the known ore shoot.
    """
    if cfg is not None:
        ct = cfg.criterion_thresholds
        br, sv = ct.plunge_breaks, ct.plunge_scores
    else:
        br = [75, 150, 300, 600]
        sv = [1.00, 0.80, 0.55, 0.30, 0.10]
    d = np.sqrt((cell_E - ax_E)**2 + (cell_N - ax_N)**2)
    score = np.full(len(cell_E), sv[-1], dtype=np.float32)
    for i in range(len(br) - 1, -1, -1):
        score = np.where(d < br[i], sv[i], score)
    return score


def score_gravity_gradient(grav_grad: np.ndarray, grav: np.ndarray,
                            grav_mean: float, gg_mean: float,
                            gg_std: float, cfg: ProjectConfig = None) -> np.ndarray:
    """C7b — Gravity gradient (blind model, replaces plunge proximity)."""
    if cfg is not None:
        ct = cfg.criterion_thresholds
        p40m, p80m, p90m = ct.grav_grad_p40_mult, ct.grav_grad_p80_mult, ct.grav_grad_p90_mult
        sv = ct.grav_grad_scores
        bonus = ct.grav_grad_bonus
    else:
        p40m, p80m, p90m = 0.15, 0.95, 1.40
        sv = [0.90, 0.70, 0.55, 0.35, 0.25]
        bonus = 0.10
    g40 = gg_mean + p40m * gg_std
    g80 = gg_mean + p80m * gg_std
    g90 = gg_mean + p90m * gg_std
    c7b = np.where(grav_grad > g90, sv[3],
          np.where(grav_grad > g80, sv[2],
          np.where((grav_grad >= g40) & (grav_grad <= g80), sv[0],
          np.where(grav_grad >= gg_mean, sv[1], sv[4])))).astype(np.float32)
    c7b = np.where(grav < grav_mean, c7b + bonus, c7b)
    return np.clip(c7b, 0, 1).astype(np.float32)


def score_mag_gradient(mag_grad: np.ndarray, mag: np.ndarray,
                        mag_mean: float, mg_p50: float, cfg: ProjectConfig = None) -> np.ndarray:
    """C8 — Magnetic gradient (blind model)."""
    if cfg is not None:
        ct = cfg.criterion_thresholds
        mults, sv = ct.mag_grad_mults, ct.mag_grad_scores
        bonus = ct.mag_grad_bonus
    else:
        mults = [1.5, 1.0, 0.5]
        sv = [0.85, 0.70, 0.50, 0.25]
        bonus = 0.10
    c8 = np.where(mag_grad >= mg_p50 * mults[0], sv[0],
         np.where(mag_grad >= mg_p50 * mults[1], sv[1],
         np.where(mag_grad >= mg_p50 * mults[2], sv[2], sv[3]))).astype(np.float32)
    c8 = np.where(mag < mag_mean, c8 + bonus, c8)
    return np.clip(c8, 0, 1).astype(np.float32)


def score_gravity_laplacian(laplacian: np.ndarray, lap_std: float, cfg: ProjectConfig = None) -> np.ndarray:
    """C9 — Gravity Laplacian (blind model). Negative = closed density deficit."""
    if cfg is not None:
        ct = cfg.criterion_thresholds
        br, sv = ct.laplacian_breaks, ct.laplacian_scores
    else:
        br = [-1.5, -0.75, -0.25, 0.0, 0.5]
        sv = [1.00, 0.85, 0.65, 0.50, 0.35, 0.20]
    ln = laplacian / max(lap_std, 1e-8)
    score = np.full(len(laplacian), sv[-1], dtype=np.float32)
    for i in range(len(br) - 1, -1, -1):
        score = np.where(ln < br[i], sv[i], score)
    return score


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


def score_ore_envelope(dist_ore: np.ndarray, ore_area: float, cfg: ProjectConfig = None) -> np.ndarray:
    """C10 — Ore envelope proximity (PROXIMITY-BIASED)."""
    if cfg is not None:
        ct = cfg.criterion_thresholds
        br, sv = ct.ore_envelope_breaks, ct.ore_envelope_scores
        min_r = ct.ore_envelope_min_radius
    else:
        br = [0.5, 1.0, 2.0, 3.5]
        sv = [1.0, 0.8, 0.5, 0.3, 0.1]
        min_r = 50
    eq_r = max(math.sqrt(ore_area / math.pi) if ore_area > 0 else min_r, min_r)
    rat  = dist_ore / eq_r
    score = np.full(len(dist_ore), sv[-1], dtype=np.float32)
    for i in range(len(br) - 1, -1, -1):
        score = np.where(rat < br[i], sv[i], score)
    return score


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
    c2  = score_pg_halo(inputs['pg'], rid, cfg)
    c3  = score_footwall_standoff(inputs['csr'], rid, cfg)
    c4  = score_gravity_absolute(inputs['grav'], z, cfg)
    c5  = score_mag_absolute(inputs['mag'], cfg)
    c6, ax_E, ax_N = score_structural_corridor(
            inputs['cell_E'], inputs['cell_N'], z, cfg, rid)
    c7  = score_plunge_proximity(inputs['cell_E'], inputs['cell_N'], ax_E, ax_N, cfg)
    c9  = score_grade_model(inputs['cell_E'], inputs['cell_N'],
                            inputs.get('block_model_df'), cfg)
    c10 = score_ore_envelope(inputs['dist_ore'], inputs.get('ore_area', 50000), cfg)

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
    c2  = score_pg_halo(inputs['pg'], rid, cfg)
    c3  = score_footwall_standoff(inputs['csr'], rid, cfg)
    c4  = score_gravity_contextual(inputs['grav'],
                                    inputs['grav_mean'], inputs['grav_std'], cfg)
    c5  = score_mag_contextual(inputs['mag'],
                                inputs['mag_mean'], inputs['mag_std'], cfg)
    c6, _, _ = score_structural_corridor(
            inputs['cell_E'], inputs['cell_N'], z, cfg, rid)
    c7b = score_gravity_gradient(inputs['grav_gradient'], inputs['grav'],
                                  inputs['grav_mean'], inputs['gg_mean'],
                                  inputs['gg_std'], cfg)
    c8  = score_mag_gradient(inputs['mag_gradient'], inputs['mag'],
                              inputs['mag_mean'], inputs['mg_p50'], cfg)
    c9l = score_gravity_laplacian(inputs['grav_laplacian'], inputs['lap_std'], cfg)
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
