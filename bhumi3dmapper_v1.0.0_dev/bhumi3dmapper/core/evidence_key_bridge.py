# -*- coding: utf-8 -*-
"""
Bhumi3DMapper — Evidence Key Bridge (BH-REM-P1)
================================================
Maps Bhumi3D voxel evidence keys to AiRE shared-repo layer_key vocabulary.

BRIDGE_TABLE is the geological authority for this mapping. Every NATIVE or
PARTIAL row requires Dr. Prithvi geological sign-off — these are geological
decisions about equivalence, not engineering renames. WRONG BRIDGES = WRONG SCORES.

Bridge statuses
---------------
NATIVE  — 1:1 semantic equivalent. Confidence ≥ 0.80.
PARTIAL — Approximate equivalence with documented semantic mismatch. Confidence
          typically 0.60–0.79. User sees a warning in the LayerReport.
MISSING — Bhumi has no current source for this layer_key. Weight is skipped in
          WLC; contributes to coverage penalty. May require CAGE-IN import.

Coverage thresholds (get_coverage_report)
-----------------------------------------
≥ 50%  — OK (warn if close to 50%)
25–50% — LOW: warn user
< 25%  — CRITICAL: block scoring, require explicit override flag

No QGIS imports permitted. Pure Python / no external dependencies.

Session 3 context: BH-REM-P1 sprint card, 2026-04-17.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class BridgeEntry:
    """
    A single row in the Evidence Key Bridge Table.

    Attributes
    ----------
    bhumi_key : str
        Bhumi3D voxel evidence key (e.g., 'c4_gravity'). Empty string for MISSING.
    shared_key : str
        AiRE shared-repo layer_key (e.g., 'grav_residual').
    bridge_type : str
        'NATIVE', 'PARTIAL', or 'MISSING'.
    confidence : float
        0.0–1.0 semantic equivalence score. Applied as a weight multiplier
        when computing coverage_fraction. 1.0 = perfect match.
    prithvi_approved : bool
        True only after Dr. Prithvi has confirmed geological equivalence.
        PARTIAL bridges with prithvi_approved=False trigger an extra warning.
    notes : str
        Geological explanation of the mapping, the mismatch, or the gap.
    requires_cage_in_export : bool
        True if this evidence can only be provided via CAGE-IN's
        JC-TBD-EVIDENCESTACK-EXPORT API.
    """
    bhumi_key: str
    shared_key: str
    bridge_type: str          # 'NATIVE', 'PARTIAL', 'MISSING'
    confidence: float         # 0.0–1.0
    prithvi_approved: bool
    notes: str
    requires_cage_in_export: bool = False


# ── Bridge Table ──────────────────────────────────────────────────────────────
# GEOLOGICAL AUTHORITY: each NATIVE/PARTIAL row requires Dr. Prithvi sign-off.
# prithvi_approved=True rows have been reviewed; False rows are PENDING.

BRIDGE_TABLE: List[BridgeEntry] = [

    # ══ NATIVE BRIDGES ════════════════════════════════════════════════════════
    # Confirmed by Dr. Prithvi — direct geological equivalent.

    BridgeEntry(
        bhumi_key="c4_gravity",
        shared_key="grav_residual",
        bridge_type="NATIVE",
        confidence=0.90,
        prithvi_approved=True,
        notes=(
            "Bhumi c4_gravity uses residual gravity (Bouguer anomaly with regional "
            "trend removed) — semantically equivalent to grav_residual. Confidence "
            "0.90 (not 1.0) because Bhumi's regional removal is project-specific; "
            "the resulting anomaly is grav_residual-class for scoring purposes. "
            "[Dr. Prithvi approved 2026-04-17 BH-REM-P1]"
        ),
    ),

    BridgeEntry(
        bhumi_key="c5_magnetics",
        shared_key="mag_rtp_as",
        bridge_type="NATIVE",
        confidence=0.85,
        prithvi_approved=True,
        notes=(
            "Bhumi c5_magnetics uses magnetic analytic signal computed from "
            "susceptibility grids — equivalent to mag_rtp_as (reduced-to-pole "
            "analytic signal). Confidence 0.85: Bhumi's input is susceptibility "
            "(not TMI), so RTP correction is implicit rather than explicit. "
            "Signal character is equivalent for prospectivity scoring. "
            "[Dr. Prithvi approved 2026-04-17 BH-REM-P1]"
        ),
    ),

    BridgeEntry(
        bhumi_key="c8_mag_gradient",
        shared_key="mag_tilt",
        bridge_type="NATIVE",
        confidence=0.80,
        prithvi_approved=True,
        notes=(
            "Bhumi c8_mag_gradient computes lateral magnetic gradient magnitude; "
            "shared-repo mag_tilt is the tilt derivative (arctan(Vz/sqrt(Vx^2+Vy^2))). "
            "Both are edge-detection operators: gradient magnitude localises body "
            "edges by amplitude, tilt derivative normalises amplitude to highlight "
            "edges of both strong and weak bodies. Functionally equivalent for "
            "delineating alteration boundaries and structural contacts. "
            "[Dr. Prithvi approved 2026-04-17 BH-REM-P1]"
        ),
    ),

    # ══ PARTIAL BRIDGES ═══════════════════════════════════════════════════════
    # Approximate equivalence. Warn user. Pending Dr. Prithvi sign-off.

    BridgeEntry(
        bhumi_key="c1_lithology",
        shared_key="litho_favourability",
        bridge_type="PARTIAL",
        confidence=0.65,
        prithvi_approved=False,
        notes=(
            "PENDING DR. PRITHVI REVIEW. Bhumi c1_lithology scores host-rock "
            "favourability from Kayad SEDEX rock codes (QMS=1.0, AM=0.0, CSR=0.50, etc.). "
            "Shared-repo litho_favourability is generic geological host-rock favourability. "
            "Mapping is valid for SEDEX Pb-Zn targets where Kayad calibration applies. "
            "Confidence degrades significantly for non-SEDEX deposit types: for orogenic_au "
            "the rock code scheme must be recalibrated to greenstone/BIF/carbonaceous shale "
            "hosts. USE WITH CAUTION for non-SEDEX scoring. Confidence 0.65 reflects "
            "the SEDEX-specific calibration bias."
        ),
    ),

    BridgeEntry(
        bhumi_key="c6_structural_corridor",
        shared_key="fault_proximity",
        bridge_type="PARTIAL",
        confidence=0.60,
        prithvi_approved=False,
        notes=(
            "PENDING DR. PRITHVI REVIEW. SEMANTIC MISMATCH documented here. "
            "Bhumi c6_structural_corridor models proximity to pre-defined structural "
            "corridors (Kayad N28E/N315E shear geometry with plunge-corrected lateral "
            "shift per 100m depth). Shared-repo fault_proximity is a simpler distance "
            "to any mapped fault. Bhumi's signal is richer (models the known structural "
            "regime) but less general (geometry must be pre-defined per project). For "
            "greenfields targets without known corridor geometry, the Bhumi signal "
            "degrades to 'proximity to the nearest assumed structure'. Confidence 0.60. "
            "WARN user when this bridge fires for orogenic_au reconnaissance targets "
            "where the structural corridor geometry is unknown."
        ),
    ),

    # ══ MISSING ENTRIES ═══════════════════════════════════════════════════════
    # No Bhumi source exists. Weight skipped in WLC. Coverage penalty applies.

    # -- Structural --
    BridgeEntry(
        bhumi_key="",
        shared_key="fault_intersection_density",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Bhumi has no fault intersection density layer. Requires either "
            "vector fault network analysis (not in Bhumi inputs) or import from "
            "CAGE-IN structural engine via JC-TBD-EVIDENCESTACK-EXPORT. "
            "Critical gap for orogenic_au (weight 0.75)."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="LINEAMENT_DENSITY",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Bhumi has no lineament density layer. Requires optical/SAR lineament "
            "extraction — import from CAGE-IN via JC-TBD-EVIDENCESTACK-EXPORT. "
            "Important for orogenic_au (weight 0.65). Note: must be canopy-penetrating "
            "provenance (SAR/aeromag) for humid-tropical targets — see orogenic_au "
            "model_notes.lineament_density_provenance_caveat."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="fold_hinge_proximity",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Bhumi has no fold hinge proximity layer. Requires fold axial trace "
            "data from geological mapping or aeromagnetic derivatives. Import from "
            "CAGE-IN or dedicated structural geology input. Important for orogenic_au "
            "(weight 0.65) and for BIF-hosted / turbidite-hosted subtypes."
        ),
        requires_cage_in_export=True,
    ),

    # -- Geochemical --
    BridgeEntry(
        bhumi_key="",
        shared_key="geochem_pathfinder",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Bhumi has no geochemical pathfinder layer (As-Sb-Te-Bi-W-Hg suite). "
            "Geochemistry is not in Bhumi's current input stack (drill assays cover "
            "Zn, Pb, Ag — not the structural pathfinder suite). Requires import from "
            "CAGE-IN geochemical engine or dedicated geochem CSV input module. "
            "Highest-weight primary for orogenic_au (0.80 tied with fault_proximity)."
        ),
        requires_cage_in_export=True,
    ),

    # -- Radiometrics --
    BridgeEntry(
        bhumi_key="",
        shared_key="radio_k_pct",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Bhumi has no radiometric K% layer. Airborne radiometrics not in Bhumi's "
            "input stack. Import from CAGE-IN radiometrics engine. Relevant to "
            "orogenic_au (positive: sericite alteration enriches K), ni_sulphide "
            "(inverted: ultramafic hosts are K-depleted), laterite_ni (inverted). "
            "Direction varies per deposit type — bridge cannot be model-agnostic."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="radio_th_k",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Bhumi has no radiometric Th/K ratio layer. Same gap as radio_k_pct. "
            "radio_th_k is INVERTED in orogenic_au (low Th/K flags potassic alteration). "
            "Requires airborne radiometric grid import."
        ),
        requires_cage_in_export=True,
    ),

    # -- Geological --
    BridgeEntry(
        bhumi_key="",
        shared_key="intrusive_proximity",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Bhumi has no intrusive proximity layer. Requires geological map input "
            "(intrusive contacts) from CAGE-IN geology engine or a dedicated polygon "
            "input. Relevant to orogenic_au (moderate weight 0.40 for IROG subtype) "
            "and porphyry/skarn models."
        ),
        requires_cage_in_export=False,
    ),

    # -- Spectral / ASTER / EMIT indices --
    BridgeEntry(
        bhumi_key="",
        shared_key="emit_carbonate",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "EMIT L2B direct Fe-carbonate (ankerite/siderite) mineral ID. "
            "Requires CAGE-IN EMIT engine. Primary carbonate signal for orogenic_au "
            "(weight 0.75). Cannot be approximated from Bhumi's drill or geophysics data."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="emit_muscovite",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "EMIT L2B direct muscovite/sericite mineral ID. "
            "Requires CAGE-IN EMIT engine. Orogenic_au weight 0.65."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="CARBONATE",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "ASTER SWIR broadband carbonate ratio (B7/B8). "
            "Requires CAGE-IN ASTER engine. Orogenic_au weight 0.60 (conservative; "
            "raises post-JC-REM-P2B to ~0.70 with improved formula)."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="AL_B5",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes="ASTER phyllic index (B5/B7). Requires CAGE-IN ASTER engine. Orogenic_au 0.55.",
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="CHLORITE_EP",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "ASTER chlorite-epidote propylitic halo index. "
            "Requires CAGE-IN ASTER engine. Orogenic_au 0.55."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="GOSSAN",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes="ASTER Fe-oxide gossan. Requires CAGE-IN ASTER engine. Orogenic_au 0.50.",
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="FERRIC",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes="Generic ASTER Fe-oxide index. Requires CAGE-IN ASTER engine. Orogenic_au 0.45.",
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="MG_OH",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "ASTER Mg-OH (komatiite alteration). Requires CAGE-IN ASTER engine. "
            "Low-specificity for most orogenic_au targets (komatiite-hosted subtype only)."
        ),
        requires_cage_in_export=True,
    ),

    # -- Composite keys (pre-computed products of two primaries) ───────────────
    # Most are MISSING because at least one factor is missing.
    # mag_tilt_x_fault_proximity is a special case: both factors are bridgeable
    # (c8→mag_tilt NATIVE, c6→fault_proximity PARTIAL) — UPGRADE OPPORTUNITY.

    BridgeEntry(
        bhumi_key="",
        shared_key="fault_proximity_x_emit_carbonate",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "TOP COMPOSITE (orogenic_au 0.88). MISSING because emit_carbonate "
            "is missing. Even if fault_proximity were bridged via c6, "
            "emit_carbonate requires CAGE-IN EMIT coverage."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="fault_proximity_x_geochem_pathfinder",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes="Composite (0.85). geochem_pathfinder is missing.",
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="emit_muscovite_x_emit_carbonate",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes="EMIT-only composite (0.78). Both factors require CAGE-IN EMIT.",
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="fault_proximity_x_CARBONATE",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes="ASTER fallback composite (0.75). Both factors require CAGE-IN.",
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="fault_intersection_density_x_emit_muscovite",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes="Composite (0.75). Both factors missing.",
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="mag_tilt_x_fault_proximity",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Composite (0.65). UPGRADE OPPORTUNITY: mag_tilt has NATIVE bridge "
            "(c8_mag_gradient), fault_proximity has PARTIAL bridge (c6_structural_corridor). "
            "This composite CAN be computed at score time as c8 * c6. "
            "Promote to PARTIAL once Dr. Prithvi approves both component bridges "
            "and confirms the product is geologically valid as a composite proxy."
        ),
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="radio_k_pct_x_fault_proximity",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes="Composite (0.65). radio_k_pct is missing.",
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="fault_proximity_div_radio_th_k",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes="Ratio composite (0.60). radio_th_k is missing.",
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="CHLORITE_EP_x_fault_proximity",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes="Composite (0.55). CHLORITE_EP requires CAGE-IN.",
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="fold_hinge_proximity_x_litho_favourability",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Composite (0.55). fold_hinge_proximity is missing; "
            "litho_favourability has only PARTIAL bridge via c1_lithology."
        ),
        requires_cage_in_export=True,
    ),
]


# ── Index and lookup helpers ───────────────────────────────────────────────────

def _build_shared_key_index() -> Dict[str, BridgeEntry]:
    """Return {shared_key: BridgeEntry} for NATIVE and PARTIAL entries only."""
    idx: Dict[str, BridgeEntry] = {}
    for entry in BRIDGE_TABLE:
        if entry.bridge_type in ("NATIVE", "PARTIAL") and entry.shared_key:
            # If multiple entries for same shared_key (shouldn't happen), last wins
            idx[entry.shared_key] = entry
    return idx


_SHARED_KEY_INDEX: Dict[str, BridgeEntry] = _build_shared_key_index()


def _build_missing_index() -> Dict[str, BridgeEntry]:
    """Return {shared_key: BridgeEntry} for MISSING entries (for cage_in_export flag)."""
    idx: Dict[str, BridgeEntry] = {}
    for entry in BRIDGE_TABLE:
        if entry.bridge_type == "MISSING" and entry.shared_key:
            idx[entry.shared_key] = entry
    return idx


_MISSING_INDEX: Dict[str, BridgeEntry] = _build_missing_index()


def get_bridge_entry(shared_key: str) -> Optional[BridgeEntry]:
    """
    Return the NATIVE or PARTIAL BridgeEntry for a shared-repo layer_key.

    Parameters
    ----------
    shared_key : str
        A layer_key from a shared-repo DepositModel weight.

    Returns
    -------
    BridgeEntry or None
        NATIVE/PARTIAL entry if Bhumi can supply evidence for this key;
        None if the key is MISSING (no Bhumi source).
    """
    return _SHARED_KEY_INDEX.get(shared_key)


def get_bhumi_value(
    shared_key: str,
    bhumi_evidence: Dict[str, float],
) -> Optional[float]:
    """
    Retrieve the Bhumi evidence value for a shared-repo layer_key.

    Parameters
    ----------
    shared_key : str
        Shared-repo layer_key.
    bhumi_evidence : dict
        {bhumi_key: float} — the voxel's available evidence values.

    Returns
    -------
    float or None
        Evidence value [0, 1] if bridged and present; None if MISSING or absent.
    """
    entry = get_bridge_entry(shared_key)
    if entry is None:
        return None
    return bhumi_evidence.get(entry.bhumi_key)


def get_coverage_report(model_weights: list) -> dict:
    """
    Compute bridge coverage metrics for a list of EvidenceWeight objects.

    Coverage is weighted by confidence: NATIVE entries with confidence 0.90
    contribute more to matched_weight_mass than PARTIAL entries at 0.60.

    Parameters
    ----------
    model_weights : list[EvidenceWeight]
        All weight entries from a loaded DepositModel.

    Returns
    -------
    dict
        Keys:
          total_weight_mass        float — sum of all model weights
          matched_weight_mass      float — sum of bridged weights × confidence
          coverage_fraction        float — matched / total
          native_keys              list[str]
          partial_keys             list[str]
          missing_keys             list[str]
          cage_in_required_keys    list[str]
          pending_prithvi_review   list[str]  — bridged but not yet approved
          warning                  str or None
          block                    bool — True if coverage < 25% (must override)
    """
    total = 0.0
    matched = 0.0
    native_keys: List[str] = []
    partial_keys: List[str] = []
    missing_keys: List[str] = []
    cage_in_keys: List[str] = []
    pending_review: List[str] = []

    for w in model_weights:
        total += w.weight
        entry = get_bridge_entry(w.layer_key)
        if entry is None:
            missing_keys.append(w.layer_key)
            miss_entry = _MISSING_INDEX.get(w.layer_key)
            if miss_entry and miss_entry.requires_cage_in_export:
                cage_in_keys.append(w.layer_key)
        elif entry.bridge_type == "NATIVE":
            native_keys.append(w.layer_key)
            matched += w.weight * entry.confidence
            if not entry.prithvi_approved:
                pending_review.append(w.layer_key)
        elif entry.bridge_type == "PARTIAL":
            partial_keys.append(w.layer_key)
            matched += w.weight * entry.confidence
            if not entry.prithvi_approved:
                pending_review.append(w.layer_key)

    coverage = matched / total if total > 0 else 0.0

    warning: Optional[str] = None
    block = False

    if coverage < 0.25:
        block = True
        warning = (
            f"CRITICAL: Only {coverage:.0%} of model weight mass is bridged "
            f"({matched:.3f} of {total:.3f}). Scores would be scientifically "
            "invalid. You must either: (a) provide additional data via CAGE-IN "
            "EvidenceStack export (JC-TBD-EVIDENCESTACK-EXPORT), or (b) explicitly "
            "acknowledge this limitation with override_low_coverage=True."
        )
    elif coverage < 0.50:
        warning = (
            f"LOW COVERAGE: Only {coverage:.0%} of model weight mass is bridged "
            f"({matched:.3f} of {total:.3f}). Scores reflect limited evidence. "
            "Consider importing additional data layers from CAGE-IN before "
            "drawing geological conclusions from these scores."
        )

    if pending_review:
        pr_note = (
            f"PENDING DR. PRITHVI REVIEW on {len(pending_review)} bridge(s): "
            f"{pending_review}. These bridges have not yet been geologically "
            "validated. Use results with caution."
        )
        warning = pr_note if warning is None else f"{warning}\n{pr_note}"

    return {
        "total_weight_mass": round(total, 4),
        "matched_weight_mass": round(matched, 4),
        "coverage_fraction": round(coverage, 4),
        "native_keys": native_keys,
        "partial_keys": partial_keys,
        "missing_keys": missing_keys,
        "cage_in_required_keys": cage_in_keys,
        "pending_prithvi_review": pending_review,
        "warning": warning,
        "block": block,
    }
