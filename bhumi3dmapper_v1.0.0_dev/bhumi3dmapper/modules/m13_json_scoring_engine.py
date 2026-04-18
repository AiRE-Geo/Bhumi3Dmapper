# -*- coding: utf-8 -*-
"""
Bhumi3DMapper — JSON-Driven Scoring Engine (Part B)
====================================================
Engine 2 of the two-engine architecture:
  Engine 1 — Kayad c-criterion engine (m04_scoring_engine.py) — brownfields
  Engine 2 — JSON-driven WLC engine (THIS FILE)             — reconnaissance

Reads any deposit model from the AiRE shared repository via the Evidence Key
Bridge (core/evidence_key_bridge.py). Performs WLC (Weighted Linear Combination)
fusion using only the evidence layers Bhumi can supply.

Coverage Enforcement
--------------------
Every score call returns a LayerReport documenting which weights contributed,
which were skipped (bridge MISSING), and what fraction of weight mass was
covered. Low-coverage scores generate warnings; critically low (<25%) block
scoring unless override_low_coverage=True.

3D Additive Field Support
-------------------------
The engine reads schema v2 additive fields from each EvidenceWeight:
  depth_extent    — restrict layer contribution to a depth range
  z_attenuation   — attenuate weight with depth (linear / exponential)
  3d_variant_key  — prefer this alternative key if present in bhumi_evidence

No QGIS imports permitted. Pure Python + numpy (optional fallback for numpy-free
contexts via math.exp).

Two-engine decision: Session 3 Orogenic Gold brainstorming 2026-04-17.
"""
from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    import numpy as _np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

# Import bridge and shared-repo loader with fallback for test contexts
try:
    from ..core.evidence_key_bridge import get_bridge_entry, get_bhumi_value, get_coverage_report
    from ..core.shared_repo_loader import (
        load_deposit_model, get_model_entry, get_repo_root, SharedRepoNotFoundError,
    )
except ImportError:
    from core.evidence_key_bridge import get_bridge_entry, get_bhumi_value, get_coverage_report
    from core.shared_repo_loader import (
        load_deposit_model, get_model_entry, get_repo_root, SharedRepoNotFoundError,
    )


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class LayerContribution:
    """Per-weight contribution record for one evidence layer."""
    shared_key: str          # shared-repo layer_key
    bhumi_key: str           # Bhumi evidence key used (or '' if MISSING)
    bridge_type: str         # 'NATIVE', 'PARTIAL', 'MISSING'
    model_weight: float      # weight from DepositModel (0–1)
    confidence: float        # bridge confidence (0–1)
    evidence_value: float    # raw Bhumi evidence value (0–1), or NaN if missing
    effective_weight: float  # model_weight × confidence × depth_factor
    weighted_score: float    # effective_weight × evidence_value (0 if missing)
    depth_factor: float      # attenuation from depth_extent / z_attenuation (1.0 = no attenuation)
    skipped: bool            # True if not contributed to score
    skip_reason: str         # '' or 'MISSING_BRIDGE', 'NO_VALUE', 'DEPTH_EXCLUDED'


@dataclass
class LayerReport:
    """
    Full scoring report for one voxel or one model run.

    Produced by JsonScoringEngine.score_voxel().
    """
    deposit_type: str
    score: float                              # final prospectivity score [0, 1]
    coverage_fraction: float                  # fraction of weight mass contributed
    total_weight_mass: float
    matched_weight_mass: float

    contributions: List[LayerContribution]    # one per model weight
    skipped_keys: List[str]                   # shared_keys that were skipped
    native_count: int
    partial_count: int
    missing_count: int

    warnings: List[str]
    blocked: bool                             # True if coverage < 25% and override not set
    model_notes: dict = field(default_factory=dict)   # propagated from DepositModel

    def summary(self) -> str:
        lines = [
            f"JsonScoringEngine | {self.deposit_type}",
            f"  Score:    {self.score:.4f}",
            f"  Coverage: {self.coverage_fraction:.1%} "
            f"({self.matched_weight_mass:.3f} / {self.total_weight_mass:.3f})",
            f"  Bridges:  {self.native_count} NATIVE, {self.partial_count} PARTIAL, "
            f"{self.missing_count} MISSING",
        ]
        if self.warnings:
            for w in self.warnings:
                lines.append(f"  WARNING: {w}")
        if self.blocked:
            lines.append("  *** BLOCKED: coverage too low — use override_low_coverage=True ***")
        return "\n".join(lines)


# ── Depth attenuation helpers ──────────────────────────────────────────────────

def _parse_attenuation_fn(fn_name: str) -> str:
    """
    Parse a z_attenuation function name from schema v2.
    Recognised: 'constant', 'linear_to_zero_at_Nm', 'exponential_decay_tauNm',
                'inverse_square_from_surface'.
    Returns the canonical name or 'constant' if unrecognised.
    """
    if not fn_name:
        return "constant"
    fn = fn_name.lower()
    if "linear" in fn:
        return "linear"
    if "exponential" in fn or "exp" in fn:
        return "exponential"
    if "inverse_square" in fn:
        return "inverse_square"
    return "constant"


def _extract_param(fn_name: str) -> float:
    """Extract numeric parameter from e.g. 'linear_to_zero_at_500m' → 500.0."""
    import re
    nums = re.findall(r"[\d.]+", fn_name)
    if nums:
        return float(nums[-1])
    return 500.0  # default


def compute_depth_factor(weight_dict: dict, z_mrl: float) -> float:
    """
    Compute the depth attenuation factor for a weight at a given elevation.

    Parameters
    ----------
    weight_dict : dict
        Raw weight dict from model JSON (may have 'depth_extent', '3d_variant_key').
    z_mrl : float
        Current voxel elevation in mRL.

    Returns
    -------
    float
        Attenuation factor in [0, 1]. 1.0 = no attenuation.
    """
    depth_ext = weight_dict.get("depth_extent")
    if not depth_ext:
        return 1.0

    # Check depth range exclusion
    subsurface = depth_ext.get("subsurface_depth_m")
    if subsurface and len(subsurface) == 2:
        # BH-05: subsurface_depth_m specifies a [min_depth, max_depth] window below
        # the surface. We cannot evaluate this without knowing the surface elevation
        # (z_mrl of the topographic surface at each voxel column). That value is not
        # yet passed to compute_depth_factor(). Emit a warning rather than silently
        # returning 1.0 — a silent pass would produce unreported scoring errors for
        # any model weight that defines a depth window.
        # Engineering ticket: BH-REM-Px-SURFACE-ELEVATION-WIRE
        # (pass surface_z_mrl to score_voxel() and propagate here)
        warnings.warn(
            "compute_depth_factor: 'subsurface_depth_m' depth window is defined "
            f"({subsurface}) but surface elevation (z_mrl of topographic surface) "
            "is not available. Depth-range exclusion SKIPPED — returning 1.0. "
            "Wire surface_z_mrl through score_voxel() to enable this feature. "
            "Ticket: BH-REM-Px-SURFACE-ELEVATION-WIRE.",
            stacklevel=3,
        )

    # Attenuation function
    atten_fn = depth_ext.get("z_attenuation", "constant")
    if not atten_fn or atten_fn == "constant":
        return 1.0

    fn_type = _parse_attenuation_fn(atten_fn)
    param = _extract_param(atten_fn)

    # Depth below surface (use negative mRL as proxy for depth)
    depth_m = max(0.0, -z_mrl)  # 0 at surface, increases downward

    if fn_type == "linear":
        # linear_to_zero_at_Nm: factor = max(0, 1 - depth/param)
        return max(0.0, 1.0 - depth_m / param)
    elif fn_type == "exponential":
        # exponential_decay_tauNm: factor = exp(-depth/tau)
        tau = param if param > 0 else 500.0
        return math.exp(-depth_m / tau)
    elif fn_type == "inverse_square":
        # inverse_square_from_surface: factor = 1 / (1 + (depth/param)^2)
        return 1.0 / (1.0 + (depth_m / param) ** 2)
    else:
        return 1.0


# ── Lightweight coverage pre-check (BH-06) ────────────────────────────────────

def get_coverage_report_for_model(
    deposit_type: str,
    deposit_family: str = "",
) -> dict:
    """
    Return a coverage report for a deposit model without constructing a full
    JsonScoringEngine. Suitable for UI pre-checks (e.g., ModelSelectorWidget
    progress bar) where schema validation and dataclass construction overhead
    is unnecessary.

    Does: manifest lookup → raw JSON parse → weight extraction →
          get_coverage_report(). No schema validation, no EvidenceWeight
          dataclass construction, no raw_weights dict build.

    Parameters
    ----------
    deposit_type : str
        Machine identifier matching a model in manifest.json.
    deposit_family : str, optional
        Deposit family for deposit_family_restriction enforcement.
        If empty, resolved from the manifest entry automatically.

    Returns
    -------
    dict
        Same structure as get_coverage_report() from evidence_key_bridge.

    Raises
    ------
    SharedRepoNotFoundError
        If the shared repo or model file cannot be located.
    """
    entry = get_model_entry(deposit_type)
    family = deposit_family or entry.get("family", "")

    raw_model_path = get_repo_root() / "models" / entry["file"]
    if not raw_model_path.exists():
        raise SharedRepoNotFoundError(
            f"Model file not found: {raw_model_path} (deposit_type='{deposit_type}')"
        )

    with open(raw_model_path, encoding="utf-8") as _fh:
        raw_model = json.load(_fh)

    # Build minimal weight objects compatible with get_coverage_report().
    # get_coverage_report() only accesses w.layer_key and w.weight — we use
    # a lightweight namedtuple rather than the full EvidenceWeight dataclass.
    from collections import namedtuple
    _W = namedtuple("_W", ["layer_key", "weight"])
    weights = [
        _W(layer_key=w["layer_key"], weight=float(w.get("weight", 0.0)))
        for w in raw_model.get("weights", [])
        if "layer_key" in w
    ]

    return get_coverage_report(weights, deposit_family=family)


# ── Main engine ────────────────────────────────────────────────────────────────

class JsonScoringEngine:
    """
    JSON-driven WLC scoring engine for AiRE shared-repo deposit models.

    Reads a DepositModel from the shared repository, bridges Bhumi voxel
    evidence to shared-repo layer_keys, and performs WLC fusion.

    Parameters
    ----------
    deposit_type : str
        Machine identifier matching a model in manifest.json.
    override_low_coverage : bool
        If True, allow scoring even when coverage < 25% (produce blocked=False
        result with prominent warning). Default False.

    Examples
    --------
    >>> engine = JsonScoringEngine('orogenic_au')
    >>> bhumi_ev = {'c4_gravity': 0.72, 'c5_magnetics': 0.45, 'c8_mag_gradient': 0.60}
    >>> report = engine.score_voxel(bhumi_ev, z_mrl=150.0)
    >>> print(report.summary())
    """

    def __init__(
        self,
        deposit_type: str,
        override_low_coverage: bool = False,
        validate_schema: bool = True,
        structural_corridors_defined: bool = True,
    ):
        """
        Parameters
        ----------
        deposit_type : str
            Machine identifier matching a model in manifest.json.
        override_low_coverage : bool
            Allow scoring when coverage < 25%. Default False.
        validate_schema : bool
            Validate model JSON against schema v2 on load. Default True.
        structural_corridors_defined : bool
            True if the user has defined structural corridors for their project
            (StructuralConfig.corridors_defined() should be passed here).
            Default True for backwards compatibility.
            When False, the c6_structural_corridor → fault_proximity PARTIAL
            bridge is demoted to MISSING at score time — the built-in Kayad
            N28E/N315E geometry is not valid for greenfields reconnaissance.
            (Dr. Prithvi ruling 2, BH-REM-P1 addendum 2026-04-17.)
        """
        self.deposit_type = deposit_type
        self.override_low_coverage = override_low_coverage
        self._structural_corridors_defined = structural_corridors_defined

        # Load model from shared repo (dataclass)
        self._model = load_deposit_model(deposit_type, validate=validate_schema)

        # Option A (Gap 2, BH-REM-P1): load raw JSON alongside the dataclass to access
        # schema v2 additive 3D fields (depth_extent, 3d_variant_key) which are not
        # reflected on EvidenceWeight. Build {layer_key: raw_weight_dict} lookup.
        # SCHEMA_ROADMAP Option B (Phase 3): EvidenceWeight will carry depth_extent
        # natively as a DepthExtent dataclass field. When Option B lands, replace
        # self._raw_weights with direct w.depth_extent access in score_voxel().
        # See AiRE-DepositModels/docs/SCHEMA_ROADMAP.md "Option B" section.
        entry = get_model_entry(deposit_type)
        raw_model_path = get_repo_root() / "models" / entry["file"]
        if not raw_model_path.exists():
            raise SharedRepoNotFoundError(
                f"Model file referenced in manifest not found: {raw_model_path} "
                f"(deposit_type='{deposit_type}')"
            )
        with open(raw_model_path, encoding="utf-8") as _fh:
            _raw_model = json.load(_fh)
        self._raw_weights: Dict[str, dict] = {
            w["layer_key"]: w for w in _raw_model.get("weights", [])
        }

        # Deposit family from manifest (used for deposit_family_restriction in bridge)
        self._deposit_family: str = entry.get("family", "")

        # Pre-compute model weight list and coverage report
        self._weights = self._model.weights
        self._coverage = get_coverage_report(
            self._weights, deposit_family=self._deposit_family
        )
        self._model_notes = getattr(self._model, "model_notes", {}) or {}

    @property
    def model(self):
        """The loaded DepositModel."""
        return self._model

    @property
    def coverage_report(self) -> dict:
        """Pre-computed coverage report from the bridge table."""
        return self._coverage

    def score_voxel(
        self,
        bhumi_evidence: Dict[str, float],
        z_mrl: float = 0.0,
        return_if_blocked: float = float("nan"),
    ) -> LayerReport:
        """
        Score a single voxel using WLC fusion with the loaded DepositModel.

        Parameters
        ----------
        bhumi_evidence : dict
            {bhumi_key: float} — Bhumi voxel evidence values, normalised [0, 1].
            Keys must match Bhumi native vocabulary (e.g., 'c4_gravity', 'c5_magnetics').
        z_mrl : float
            Voxel elevation in mRL. Used for depth-extent and z_attenuation
            from schema v2 additive fields.
        return_if_blocked : float
            Value to set score to when coverage < 25% and override=False.
            Default NaN.

        Returns
        -------
        LayerReport
            Full per-layer report including score, coverage, warnings.
        """
        contributions: List[LayerContribution] = []
        warnings: List[str] = []

        # Propagate coverage warnings from pre-computed report
        if self._coverage.get("warning"):
            warnings.append(self._coverage["warning"])

        blocked = self._coverage.get("block", False) and not self.override_low_coverage

        numerator = 0.0
        denominator = 0.0
        native_count = 0
        partial_count = 0
        missing_count = 0

        for w in self._weights:
            shared_key = w.layer_key
            model_weight = w.weight

            # Check for 3d_variant_key — prefer if present in bhumi_evidence
            # (schema v2 additive field; stored in raw dict, not on EvidenceWeight directly)
            # We access via the model's raw JSON if needed; for now use layer_key directly.

            # Look up bridge
            bridge_entry = get_bridge_entry(shared_key)

            # Dr. Prithvi ruling 2 (BH-REM-P1 addendum): demote c6→fault_proximity
            # PARTIAL to MISSING when no user-defined structural corridors exist.
            # The Kayad N28E/N315E default geometry is not valid for greenfields targets.
            if (
                bridge_entry is not None
                and bridge_entry.bhumi_key == "c6_structural_corridor"
                and not self._structural_corridors_defined
            ):
                warnings.append(
                    "Bridge 'c6_structural_corridor' → 'fault_proximity' DEMOTED to "
                    "MISSING: no user-defined structural corridors found in StructuralConfig. "
                    "The built-in Kayad N28E/N315E geometry is not valid for this project's "
                    "geology. Define project-specific corridors to re-enable this bridge. "
                    "(Dr. Prithvi ruling 2, BH-REM-P1 addendum 2026-04-17)"
                )
                bridge_entry = None  # Treat as MISSING for this run

            if bridge_entry is None:
                # MISSING bridge
                contributions.append(LayerContribution(
                    shared_key=shared_key,
                    bhumi_key="",
                    bridge_type="MISSING",
                    model_weight=model_weight,
                    confidence=0.0,
                    evidence_value=float("nan"),
                    effective_weight=0.0,
                    weighted_score=0.0,
                    depth_factor=1.0,
                    skipped=True,
                    skip_reason="MISSING_BRIDGE",
                ))
                missing_count += 1
                continue

            # BH-04: detect composite PARTIAL entries (bhumi_key contains "*").
            # These are architecturally unimplemented — the synthetic key like
            # "c4_gravity*c5_magnetics" cannot be looked up in bhumi_evidence.
            # Emit a distinct skip_reason so callers can distinguish from genuine
            # missing evidence vs. unimplemented composite computation.
            if "*" in bridge_entry.bhumi_key:
                contributions.append(LayerContribution(
                    shared_key=shared_key,
                    bhumi_key=bridge_entry.bhumi_key,
                    bridge_type=bridge_entry.bridge_type,
                    model_weight=model_weight,
                    confidence=bridge_entry.confidence,
                    evidence_value=float("nan"),
                    effective_weight=0.0,
                    weighted_score=0.0,
                    depth_factor=1.0,
                    skipped=True,
                    skip_reason="COMPOSITE_NOT_IMPLEMENTED",
                ))
                missing_count += 1
                continue

            # Get raw evidence value from bhumi_evidence
            ev_value = bhumi_evidence.get(bridge_entry.bhumi_key)
            if ev_value is None:
                contributions.append(LayerContribution(
                    shared_key=shared_key,
                    bhumi_key=bridge_entry.bhumi_key,
                    bridge_type=bridge_entry.bridge_type,
                    model_weight=model_weight,
                    confidence=bridge_entry.confidence,
                    evidence_value=float("nan"),
                    effective_weight=0.0,
                    weighted_score=0.0,
                    depth_factor=1.0,
                    skipped=True,
                    skip_reason="NO_VALUE",
                ))
                if bridge_entry.bridge_type == "NATIVE":
                    native_count += 1
                else:
                    partial_count += 1
                continue

            # Apply invert flag from EvidenceWeight
            if getattr(w, "invert", False):
                ev_value = 1.0 - float(ev_value)
            else:
                ev_value = float(ev_value)

            # Clamp to [0, 1]
            ev_value = max(0.0, min(1.0, ev_value))

            # Schema v2: depth attenuation — reads depth_extent from raw weight dict
            # (Gap 2 Option A: self._raw_weights built in __init__ from raw JSON).
            # EvidenceWeight dataclass doesn't carry depth_extent natively (Phase 3 work).
            raw_w = self._raw_weights.get(shared_key, {})
            depth_factor = compute_depth_factor(raw_w, z_mrl)

            # Effective weight = model_weight × bridge_confidence × depth_factor
            eff_weight = model_weight * bridge_entry.confidence * depth_factor

            # WLC accumulation
            numerator += eff_weight * ev_value
            denominator += eff_weight

            if bridge_entry.bridge_type == "NATIVE":
                native_count += 1
            else:
                partial_count += 1

            contributions.append(LayerContribution(
                shared_key=shared_key,
                bhumi_key=bridge_entry.bhumi_key,
                bridge_type=bridge_entry.bridge_type,
                model_weight=model_weight,
                confidence=bridge_entry.confidence,
                evidence_value=ev_value,
                effective_weight=eff_weight,
                weighted_score=eff_weight * ev_value,
                depth_factor=depth_factor,
                skipped=False,
                skip_reason="",
            ))

            # Add pending-review warning for PARTIAL unapproved bridges
            if bridge_entry.bridge_type == "PARTIAL" and not bridge_entry.prithvi_approved:
                warnings.append(
                    f"Bridge '{bridge_entry.bhumi_key}' → '{shared_key}' "
                    f"(PARTIAL) has not yet been reviewed by Dr. Prithvi. "
                    f"Geological equivalence is provisional."
                )

        # Final WLC score
        if blocked:
            score = return_if_blocked
        elif denominator > 0:
            score = numerator / denominator
        else:
            score = 0.0

        skipped_keys = [c.shared_key for c in contributions if c.skipped]
        coverage_fraction = self._coverage.get("coverage_fraction", 0.0)

        return LayerReport(
            deposit_type=self.deposit_type,
            score=score,
            coverage_fraction=coverage_fraction,
            total_weight_mass=self._coverage.get("total_weight_mass", 0.0),
            matched_weight_mass=self._coverage.get("matched_weight_mass", 0.0),
            contributions=contributions,
            skipped_keys=skipped_keys,
            native_count=native_count,
            partial_count=partial_count,
            missing_count=missing_count,
            warnings=warnings,
            blocked=blocked,
            model_notes=self._model_notes,
        )

    def score_level(
        self,
        level_evidence: Dict[str, Dict[str, float]],
        z_mrl: float,
    ) -> Dict[str, LayerReport]:
        """
        Score all voxels at one level.

        Parameters
        ----------
        level_evidence : dict
            {cell_id: {bhumi_key: float}} — evidence values per voxel.
        z_mrl : float
            Elevation of this level in mRL.

        Returns
        -------
        dict
            {cell_id: LayerReport}
        """
        return {
            cell_id: self.score_voxel(ev, z_mrl=z_mrl)
            for cell_id, ev in level_evidence.items()
        }

    def score_all_levels(
        self,
        levels_evidence: Dict[float, Dict[str, Dict[str, float]]],
    ) -> Dict[float, Dict[str, LayerReport]]:
        """
        Score all voxels across all levels.

        Parameters
        ----------
        levels_evidence : dict
            {z_mrl: {cell_id: {bhumi_key: float}}}

        Returns
        -------
        dict
            {z_mrl: {cell_id: LayerReport}}
        """
        return {
            z_mrl: self.score_level(level_ev, z_mrl=z_mrl)
            for z_mrl, level_ev in levels_evidence.items()
        }

    def get_coverage_summary(self) -> str:
        """Return a human-readable coverage summary string."""
        cov = self._coverage
        family_str = f" [{self._deposit_family}]" if self._deposit_family else ""
        lines = [
            f"Coverage report — {self.deposit_type}{family_str}",
            f"  Total weight mass  : {cov.get('total_weight_mass', 0):.3f}",
            f"  Matched weight mass: {cov.get('matched_weight_mass', 0):.3f}",
            f"  Coverage fraction  : {cov.get('coverage_fraction', 0):.1%}",
            f"  NATIVE  bridges: {cov.get('native_keys', [])}",
            f"  PARTIAL bridges: {cov.get('partial_keys', [])}",
            f"  MISSING keys   : {cov.get('missing_keys', [])}",
            f"  CAGE-IN needed : {cov.get('cage_in_required_keys', [])}",
        ]
        if cov.get("warning"):
            lines.append(f"  WARNING: {cov['warning']}")
        if cov.get("block"):
            lines.append("  *** BLOCKED — coverage critically low ***")
        return "\n".join(lines)
