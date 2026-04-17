"""
ProspectivityMapper — Core Configuration Schema
================================================
All project parameters are defined here as dataclasses.
Edit project_config.json (exported from the UI) to customise for each new project.
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
import json, os

@dataclass
class GridConfig:
    """5×5m (or custom) horizontal grid definition."""
    xmin: float = 468655.0
    ymin: float = 2932890.0
    cell_size_m: float = 5.0
    nx: int = 482
    ny: int = 722
    epsg: int = 32643
    z_top_mrl: float = 460.0
    z_bot_mrl: float = -260.0
    dz_m: float = 5.0

    @property
    def z_levels(self):
        import numpy as np
        n = int(round((self.z_top_mrl - self.z_bot_mrl) / self.dz_m)) + 1
        return list(np.linspace(self.z_bot_mrl, self.z_top_mrl, n))

    @property
    def n_cells_per_level(self):
        return self.nx * self.ny


@dataclass
class DrillDataConfig:
    """Paths to drill database CSV/Excel files."""
    collar_csv: str = ""
    assay_csv: str = ""
    litho_csv: str = ""
    survey_csv: str = ""
    # Column name mapping — change if your columns differ
    col_bhid: str = "BHID"
    col_from: str = "FROM"
    col_to: str = "TO"
    col_xcollar: str = "XCOLLAR"
    col_ycollar: str = "YCOLLAR"
    col_zcollar: str = "ZCOLLAR"
    col_depth: str = "DEPTH"
    col_rockcode: str = "ROCKCODE"
    col_azimuth: str = "BRG"
    col_dip: str = "DIP"
    col_zn: str = "ZN"
    col_pb: str = "PB"
    col_ag: str = "AG"
    # Ore threshold (Pb+Zn %)
    ore_threshold_pct: float = 2.0
    # Max search radius for nearest-hole assignment (m)
    hole_search_radius_m: float = 300.0
    # Custom column mapping — overrides col_* defaults when set (JC-24)
    # Format: {'col_bhid': 'HOLE_ID', 'col_xcollar': 'EAST', ...}
    column_mapping: Dict[str, str] = field(default_factory=dict)


@dataclass
class LithologyConfig:
    """
    Lithology code mapping and ore-host definitions.
    Extend rock_codes dict for your project's lithologies.
    """
    # Map your rock codes to integer IDs (0=unknown,1=primary_host,2=hard_veto,3=structural,4=secondary_host,5=other)
    rock_codes: Dict[str, int] = field(default_factory=lambda: {
        "QMS": 1, "QUARTZ MICA SCHIST": 1,           # primary host upper
        "AM": 2, "AMP": 2, "AMPH": 2, "AMPHIBOLITE": 2,  # hard veto
        "PG": 3, "PEGMATITE": 3,                      # structural marker
        "CSR": 4, "CALC-SILICATE": 4,                 # secondary/lower host
        "QZ": 5, "QUARTZITE": 5,                      # other
    })
    # Which code is the "hard veto" (never ore-bearing)
    hard_veto_code: int = 2
    # Score cap for veto lithology (0-100)
    veto_score_cap: float = 20.0
    # Minimum fraction for primary host classification
    primary_host_min_fraction: float = 0.60
    # Minimum fraction for secondary host classification
    secondary_host_min_fraction: float = 0.50


@dataclass
class StructuralConfig:
    """
    Structural corridor definitions.
    Supports multiple corridors for different depth regimes.
    """
    # Each corridor: name, azimuth_deg, plunge_deg, plunge_azimuth_deg,
    #                anchor_E, anchor_N, anchor_mRL,
    #                lateral_shift_E_per_100m, lateral_shift_N_per_100m,
    #                z_top_mrl, z_bot_mrl
    corridors: List[Dict] = field(default_factory=lambda: [
        {
            "name": "Shallow_N28E",
            "azimuth_deg": 28.0,
            "plunge_deg": 30.0,
            "plunge_azimuth_deg": 75.0,
            "anchor_E": 469519.0,
            "anchor_N": 2934895.0,
            "anchor_mRL": 185.0,
            "lateral_E_per_100m_down": 1.22,
            "lateral_N_per_100m_down": 0.33,
            "z_top_mrl": 460.0,
            "z_bot_mrl": 60.0,
        },
        {
            "name": "Deep_N315E",
            "azimuth_deg": 315.0,
            "plunge_deg": 12.0,
            "plunge_azimuth_deg": 63.0,
            "anchor_E": 470210.0,
            "anchor_N": 2935041.0,
            "anchor_mRL": -140.0,
            "lateral_E_per_100m_down": 4.10,
            "lateral_N_per_100m_down": 1.71,
            "z_top_mrl": -40.0,
            "z_bot_mrl": -265.0,
        }
    ])
    # Corridor proximity scoring thresholds (m from axis)
    score_breaks_m: List[float] = field(default_factory=lambda: [75, 150, 300, 500])
    score_values: List[float] = field(default_factory=lambda: [1.00, 0.80, 0.55, 0.30, 0.10])
    # True when the user has explicitly configured corridors for their project.
    # False = only the built-in Kayad N28E/N315E defaults are present.
    # JsonScoringEngine checks this before accepting the c6→fault_proximity PARTIAL bridge:
    # if False, the bridge is demoted to MISSING for that run (Dr. Prithvi ruling 2,
    # BH-REM-P1 addendum 2026-04-17).
    user_defined: bool = False

    def corridors_defined(self) -> bool:
        """
        Return True if the user has explicitly defined structural corridors
        for this project (not just the Kayad built-in defaults).

        JsonScoringEngine uses this to decide whether to honour the
        c6_structural_corridor → fault_proximity PARTIAL bridge.
        When False, that bridge is demoted to MISSING at score time — the
        Kayad geometry is not valid for greenfields reconnaissance targets.
        """
        return self.user_defined


@dataclass
class DepthRegimeConfig:
    """
    Depth-regime boundaries and behaviour flags.
    Change thresholds to match your deposit's depth structure.
    """
    # Regime names: 0=lower, 1=transition, 2=upper (or more if needed)
    regimes: List[Dict] = field(default_factory=lambda: [
        {"name": "upper",      "z_min": 160.0, "z_max": 9999.0, "id": 2},
        {"name": "transition", "z_min": 60.0,  "z_max": 160.0,  "id": 1},
        {"name": "lower",      "z_min": -9999.0,"z_max": 60.0,  "id": 0},
    ])
    # Confidence discount applied in transition zone (fraction)
    transition_confidence_discount: float = 0.30


@dataclass
class GeophysicsConfig:
    """Paths to geophysical raster data (TIF/TIFF, float32)."""
    # Gravity: folder containing TIFs named *_<mRL>.tif
    gravity_folder: str = ""
    gravity_units: str = "mGal"
    gravity_nodatavalue: float = -9999.0
    gravity_pixel_size_m: float = 5.0
    # Magnetic susceptibility: folder containing TIFs
    magnetics_folder: str = ""
    magnetics_units: str = "uSI"
    magnetics_nodatavalue: float = -9999.0
    magnetics_pixel_size_m: float = 30.0
    # IP (optional) — folder of PNG/TIF section images
    ip_folder: str = ""
    ip_available: bool = False
    # Additional geophysics layers (extendable)
    extra_geophys: List[Dict] = field(default_factory=list)


@dataclass
class OrePolygonConfig:
    """Known mineralisation polygon inputs."""
    # Folder containing one GPKG per level, or a single multi-level GPKG
    polygon_folder: str = ""
    # Pattern to extract mRL from filename, e.g. r'(-?\d+)' from 'Ore_-185.gpkg'
    mrl_pattern: str = r'(-?\d+)'
    # If using a CSV of centroids instead of polygons
    centroids_csv: str = ""


@dataclass
class BlockModelConfig:
    """Grade block model CSVs — one per domain or a combined file."""
    # Dict of domain_name → path to CSV
    domain_files: Dict[str, str] = field(default_factory=dict)
    # Column names in block model CSVs
    col_xcenter: str = "XC"
    col_ycenter: str = "YC"
    col_zcenter: str = "ZC"
    col_grade_primary: str = "ZN"
    col_grade_secondary: str = "PB"
    # Grade threshold for endorsement score = 1.0
    endorsement_grade_pct: float = 5.0
    # Score by domain
    domain_scores: Dict[str, float] = field(default_factory=lambda: {
        "main_lens": 0.75, "k18": 0.90, "ne": 0.60, "s1": 0.50, "s2": 0.40
    })


@dataclass
class ScoringThresholdsConfig:
    """
    Criterion-specific scoring thresholds — configurable per deposit type.
    Kayad SEDEX Pb-Zn defaults are provided. Override for VMS, epithermal, porphyry, etc.
    """
    # C1 — Lithology score tables per regime {regime_id: {lcode: score}}
    litho_scores: Dict[int, Dict[int, float]] = field(default_factory=lambda: {
        2: {1: 1.0, 2: 0.0, 3: 0.30, 4: 0.25, 5: 0.40, 0: 0.25},  # upper
        1: {1: 0.8, 2: 0.0, 3: 0.30, 4: 0.50, 5: 0.40, 0: 0.30},  # transition
        0: {1: 0.6, 2: 0.0, 3: 0.30, 4: 1.00, 5: 0.40, 0: 0.30},  # lower
    })
    litho_default_score: float = 0.25

    # C2 — PG halo distance breaks (m) and scores
    pg_breaks: List[float] = field(default_factory=lambda: [2, 4, 10, 15, 20, 30, 50])
    pg_scores: List[float] = field(default_factory=lambda: [0.50, 0.80, 1.00, 0.70, 0.50, 0.35, 0.25, 0.15])
    pg_lower_fill: float = 0.4

    # C3 — CSR/footwall standoff breaks + scores per regime
    csr_upper_breaks: List[float] = field(default_factory=lambda: [5, 10, 40, 60, 100])
    csr_upper_scores: List[float] = field(default_factory=lambda: [0.40, 0.65, 1.00, 0.70, 0.40, 0.20])
    csr_lower_breaks: List[float] = field(default_factory=lambda: [5, 15, 30])
    csr_lower_scores: List[float] = field(default_factory=lambda: [1.00, 0.70, 0.45, 0.25])

    # C4a — Gravity absolute thresholds (mGal) per depth zone
    grav_abs_z_upper: float = 310.0
    grav_abs_z_mid: float = 160.0
    grav_abs_upper_breaks: List[float] = field(default_factory=lambda: [-0.10, -0.03, 0.05, 0.30, 0.80])
    grav_abs_upper_scores: List[float] = field(default_factory=lambda: [0.95, 0.80, 0.60, 0.40, 0.25, 0.10])
    grav_abs_mid_breaks: List[float] = field(default_factory=lambda: [0, 0.05, 0.10])
    grav_abs_mid_scores: List[float] = field(default_factory=lambda: [0.75, 0.60, 0.45, 0.30])
    grav_abs_lower_breaks: List[float] = field(default_factory=lambda: [0, 0.05])
    grav_abs_lower_scores: List[float] = field(default_factory=lambda: [0.65, 0.55, 0.40])

    # C4b/C5b — Contextual z-score thresholds (gravity and magnetics)
    contextual_zscore_breaks: List[float] = field(default_factory=lambda: [-1.5, -0.75, -0.25, 0.0, 0.5, 1.0])
    contextual_zscore_scores: List[float] = field(default_factory=lambda: [1.00, 0.90, 0.75, 0.60, 0.45, 0.30, 0.15])

    # C5a — Magnetics absolute thresholds (uSI)
    mag_abs_breaks: List[float] = field(default_factory=lambda: [-10, -5, 0, 10, 30, 60])
    mag_abs_scores: List[float] = field(default_factory=lambda: [1.00, 0.90, 0.75, 0.60, 0.40, 0.25, 0.12])

    # C7 — Plunge proximity breaks (m)
    plunge_breaks: List[float] = field(default_factory=lambda: [75, 150, 300, 600])
    plunge_scores: List[float] = field(default_factory=lambda: [1.00, 0.80, 0.55, 0.30, 0.10])

    # C7b — Gravity gradient percentile multipliers
    grav_grad_p40_mult: float = 0.15
    grav_grad_p80_mult: float = 0.95
    grav_grad_p90_mult: float = 1.40
    grav_grad_scores: List[float] = field(default_factory=lambda: [0.90, 0.70, 0.55, 0.35, 0.25])
    grav_grad_bonus: float = 0.10

    # C8 — Mag gradient median multipliers
    mag_grad_mults: List[float] = field(default_factory=lambda: [1.5, 1.0, 0.5])
    mag_grad_scores: List[float] = field(default_factory=lambda: [0.85, 0.70, 0.50, 0.25])
    mag_grad_bonus: float = 0.10

    # C9 — Laplacian z-score thresholds
    laplacian_breaks: List[float] = field(default_factory=lambda: [-1.5, -0.75, -0.25, 0.0, 0.5])
    laplacian_scores: List[float] = field(default_factory=lambda: [1.00, 0.85, 0.65, 0.50, 0.35, 0.20])

    # C10 — Ore envelope distance/radius ratio breaks
    ore_envelope_breaks: List[float] = field(default_factory=lambda: [0.5, 1.0, 2.0, 3.5])
    ore_envelope_scores: List[float] = field(default_factory=lambda: [1.0, 0.8, 0.5, 0.3, 0.1])
    ore_envelope_min_radius: float = 50.0

    # Drill processor thresholds
    structural_marker_code: int = 3
    footwall_code: int = 4
    coarse_grid_factor: int = 6
    max_nearest_holes: int = 5

    # Display names
    litho_names: Dict[int, str] = field(default_factory=lambda: {
        0: 'Unknown', 1: 'QMS', 2: 'Amphibolite', 3: 'Pegmatite', 4: 'CSR', 5: 'Quartzite'
    })
    regime_names: Dict[int, str] = field(default_factory=lambda: {
        0: 'Lower mine', 1: 'Transition', 2: 'Upper mine'
    })
    class_names: Dict[int, str] = field(default_factory=lambda: {
        0: 'Very Low', 1: 'Low', 2: 'Moderate', 3: 'High', 4: 'Very High'
    })


@dataclass
class ScoringWeightsConfig:
    """
    Criterion weights for both prospectivity models.
    Change weights, add/remove criteria for your deposit type.
    """
    # ── Proximity model weights ────────────────────────────────────────────
    proximity: Dict[str, float] = field(default_factory=lambda: {
        "c1_lithology":          2.0,
        "c2_pg_halo":            1.5,
        "c3_csr_standoff":       1.5,
        "c4_gravity":            0.8,
        "c5_magnetics":          1.0,
        "c6_structural_corridor":1.5,
        "c7_plunge_proximity":   1.0,
        "c9_grade_model":        0.7,
        "c10_ore_envelope":      1.0,
    })
    # ── Blind model weights ────────────────────────────────────────────────
    blind: Dict[str, float] = field(default_factory=lambda: {
        "c1_lithology":          2.0,
        "c2_pg_halo":            1.5,
        "c3_csr_standoff":       1.5,
        "c4_contextual_gravity": 1.2,
        "c5_contextual_mag":     1.2,
        "c6_structural_corridor":1.5,
        "c7b_grav_gradient":     0.9,
        "c8_mag_gradient":       0.9,
        "c9_laplacian":          0.8,
        "c10_novelty":           0.5,
    })
    # ── Score classification thresholds (0-100) ────────────────────────────
    thresholds: Dict[str, float] = field(default_factory=lambda: {
        "Very High": 75.0,
        "High":      60.0,
        "Moderate":  45.0,
        "Low":       30.0,
    })
    # Distance from known ore for "novel" cells (m)
    novelty_distance_m: float = 500.0


@dataclass
class OutputConfig:
    """Output paths and formats."""
    output_dir: str = "./outputs"
    project_name: str = "MyProject"
    # Which outputs to generate
    generate_gpkg_per_level: bool = True
    generate_voxel_npz: bool = True
    generate_voxel_gpkg: bool = True
    # GPKG export: levels to include (empty = all)
    gpkg_levels: List[float] = field(default_factory=list)
    # Voxel: export only cells above this score
    voxel_min_score: float = 0.0
    # Voxel slab size (levels per archive)
    voxel_slab_size: int = 10
    log_level: str = "INFO"


@dataclass
class ProjectConfig:
    """Master project configuration — top-level container."""
    project_name: str = "Unnamed Project"
    project_description: str = ""
    deposit_type: str = "SEDEX Pb-Zn"
    location: str = ""
    crs_epsg: int = 32643
    created_by: str = ""
    created_date: str = ""
    version: str = "1.0"

    # ── Two-engine architecture (Session 3, 2026-04-17) ──────────────────────
    # scoring_engine: 'kayad' = Kayad c-criterion engine (brownfields, Engine 1)
    #                 'json_model' = shared-repo JSON WLC engine (recon, Engine 2)
    scoring_engine: str = "kayad"
    # deposit_type for the JSON engine (shared-repo machine identifier)
    # e.g., 'orogenic_au', 'ni_sulphide'. Empty = use deposit_type field above.
    json_model_deposit_type: str = ""
    # Optional: override shared repo path (leave empty for auto-resolve)
    shared_repo_path: str = ""
    # Allow scoring even when evidence coverage < 25% (JSON engine only)
    override_low_coverage: bool = False

    grid:         GridConfig         = field(default_factory=GridConfig)
    drill:        DrillDataConfig     = field(default_factory=DrillDataConfig)
    lithology:    LithologyConfig     = field(default_factory=LithologyConfig)
    structure:    StructuralConfig    = field(default_factory=StructuralConfig)
    regimes:      DepthRegimeConfig   = field(default_factory=DepthRegimeConfig)
    geophysics:   GeophysicsConfig    = field(default_factory=GeophysicsConfig)
    ore_polygons: OrePolygonConfig    = field(default_factory=OrePolygonConfig)
    block_model:  BlockModelConfig    = field(default_factory=BlockModelConfig)
    scoring:      ScoringWeightsConfig = field(default_factory=ScoringWeightsConfig)
    criterion_thresholds: ScoringThresholdsConfig = field(default_factory=ScoringThresholdsConfig)
    outputs:      OutputConfig        = field(default_factory=OutputConfig)

    def to_json(self, path: str):
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)
        print(f"Config saved to {path}")

    @classmethod
    def from_json(cls, path: str) -> 'ProjectConfig':
        with open(path) as f:
            d = json.load(f)
        cfg = cls()
        cfg.grid         = GridConfig(**d.get('grid', {}))
        cfg.drill        = DrillDataConfig(**d.get('drill', {}))
        cfg.lithology    = LithologyConfig(**d.get('lithology', {}))
        cfg.structure    = StructuralConfig(**d.get('structure', {}))
        cfg.regimes      = DepthRegimeConfig(**d.get('regimes', {}))
        cfg.geophysics   = GeophysicsConfig(**d.get('geophysics', {}))
        cfg.ore_polygons = OrePolygonConfig(**d.get('ore_polygons', {}))
        cfg.block_model  = BlockModelConfig(**d.get('block_model', {}))
        cfg.scoring      = ScoringWeightsConfig(**d.get('scoring', {}))
        cfg.criterion_thresholds = ScoringThresholdsConfig(**d.get('criterion_thresholds', {}))
        cfg.outputs      = OutputConfig(**d.get('outputs', {}))
        for k in ['project_name','project_description','deposit_type',
                  'location','crs_epsg','created_by','created_date','version']:
            if k in d: setattr(cfg, k, d[k])
        return cfg


# ── Convenience: write a template config ──────────────────────────────────────
if __name__ == "__main__":
    cfg = ProjectConfig(
        project_name="Kayad Pb-Zn Mine",
        deposit_type="SEDEX Pb-Zn",
        location="Ajmer, Rajasthan, India",
    )
    cfg.to_json("./configs/kayad_config.json")
    print("Template config written to ./configs/kayad_config.json")
