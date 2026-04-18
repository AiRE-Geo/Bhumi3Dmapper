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
        For PARTIAL composite entries that are computed products, this field uses
        the synthetic form 'keyA*keyB' to signal the computation required.
    shared_key : str
        AiRE shared-repo layer_key (e.g., 'grav_residual').
    bridge_type : str
        'NATIVE', 'PARTIAL', or 'MISSING'.
    confidence : float
        0.0–1.0 semantic equivalence score. Applied as a weight multiplier
        when computing coverage_fraction. 1.0 = perfect match.
        For composite PARTIAL entries, confidence = min(confidence of all factors).
    prithvi_approved : bool
        True only after Dr. Prithvi has confirmed geological equivalence.
        PARTIAL bridges with prithvi_approved=False trigger an extra warning.
    notes : str
        Geological explanation of the mapping, the mismatch, or the gap.
    requires_cage_in_export : bool
        True if this evidence can only be provided via CAGE-IN's
        JC-TBD-EVIDENCESTACK-EXPORT API.
    deposit_family_restriction : list[str] or None
        If set, this bridge is only valid for models whose deposit family is in
        this list. When the model family is NOT in the list, the bridge is treated
        as MISSING for coverage and scoring purposes.
        None means the bridge applies to all deposit families.
        Example: ['hydrothermal_sedex', 'sedimentary'] restricts to SEDEX models.
    """
    bhumi_key: str
    shared_key: str
    bridge_type: str          # 'NATIVE', 'PARTIAL', 'MISSING'
    confidence: float         # 0.0–1.0
    prithvi_approved: bool
    notes: str
    requires_cage_in_export: bool = False
    deposit_family_restriction: Optional[List[str]] = None


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
        shared_key="mag_gradient",
        bridge_type="NATIVE",
        confidence=0.90,
        prithvi_approved=True,
        notes=(
            "Bhumi c8_mag_gradient computes lateral magnetic gradient magnitude "
            "sqrt(dTMI/dx^2 + dTMI/dy^2) — this IS mag_gradient. Amplitude-dependent "
            "edge detector that marks density-susceptibility contact boundaries. "
            "Used in sedex_pbzn (0.55) and ni_sulphide contexts. "
            "[Dr. Prithvi ruling 2026-04-18: c8 computation is identical to mag_gradient. "
            "NATIVE bridge confirmed. Previous NATIVE bridge to mag_tilt was imprecise — "
            "mag_tilt is a distinct normalised operator (see PARTIAL entry below).]"
        ),
    ),

    BridgeEntry(
        bhumi_key="c8_mag_gradient",
        shared_key="mag_tilt",
        bridge_type="PARTIAL",
        confidence=0.70,
        prithvi_approved=True,
        notes=(
            "Bhumi c8_mag_gradient computes lateral gradient magnitude (amplitude-dependent); "
            "shared-repo mag_tilt is arctan(Vz/sqrt(Vx^2+Vy^2)) — amplitude-normalised. "
            "Both are edge-detection operators but with different amplitude behaviour: "
            "gradient magnitude emphasises strong anomalies; tilt derivative equally highlights "
            "edges of both strong and weak bodies, making it better for under-covered terranes. "
            "PARTIAL at 0.70 because the normalisation difference is geologically meaningful "
            "for orogenic_au targets where subtle weak-body edges matter (Birimian, West Nile). "
            "Confidence 0.70 (not 0.80 as previously): amplitude normalisation is not implicit. "
            "[Dr. Prithvi ruling 2026-04-18: downgraded from NATIVE 0.80 to PARTIAL 0.70. "
            "Use c8 as mag_gradient (NATIVE 0.90) for SEDEX/Ni-sulphide. "
            "Use c8 as mag_tilt (PARTIAL 0.70) for orogenic/graphite edge detection.]"
        ),
    ),

    # ══ PARTIAL BRIDGES ═══════════════════════════════════════════════════════
    # Approximate equivalence. Warn user. Pending Dr. Prithvi sign-off.

    BridgeEntry(
        bhumi_key="c1_lithology",
        shared_key="litho_favourability",
        bridge_type="PARTIAL",
        confidence=0.65,
        prithvi_approved=True,
        notes=(
            "DR. PRITHVI APPROVED 2026-04-17 (BH-REM-P1 addendum), CONDITIONAL on "
            "deposit_family_restriction enforcement. Bhumi c1_lithology scores host-rock "
            "favourability from Kayad SEDEX rock codes (QMS=1.0, AM=0.0, CSR=0.50, etc.). "
            "Shared-repo litho_favourability is generic geological host-rock favourability. "
            "Mapping is valid for SEDEX Pb-Zn targets where Kayad calibration applies. "
            "Confidence degrades significantly for non-SEDEX deposit types: the rock code "
            "scheme must be recalibrated to match greenstone/BIF/ultramafic/carbonaceous "
            "shale hosts. ENGINEERING GUARD: deposit_family_restriction=['hydrothermal_sedex', "
            "'sedimentary'] is set — for orogenic, magmatic, and supergene models this bridge "
            "is treated as MISSING in get_coverage_report() and score_voxel()."
        ),
        deposit_family_restriction=["hydrothermal_sedex", "sedimentary"],
    ),

    BridgeEntry(
        bhumi_key="c6_structural_corridor",
        shared_key="fault_proximity",
        bridge_type="PARTIAL",
        confidence=0.60,
        prithvi_approved=True,
        notes=(
            "DR. PRITHVI APPROVED 2026-04-17 (BH-REM-P1 addendum), CONDITIONAL on "
            "runtime StructuralConfig.corridors_defined() check. Bhumi c6_structural_corridor "
            "models proximity to pre-defined structural corridors (Kayad N28E/N315E shear "
            "geometry with plunge-corrected lateral shift per 100m depth). Shared-repo "
            "fault_proximity is a simpler distance to any mapped fault. Bhumi's signal is "
            "richer (models the known structural regime) but less general (geometry must be "
            "pre-defined per project). For greenfields targets without known corridor "
            "geometry, the Bhumi signal degrades to 'proximity to the nearest assumed "
            "structure'. Confidence 0.60. ENGINEERING GUARD: in JsonScoringEngine, if "
            "StructuralConfig.corridors_defined() returns False, this bridge is demoted to "
            "MISSING at runtime and a UI warning is emitted. Coverage report assumes corridors "
            "are defined; score_voxel() applies the runtime check."
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

    # ══ ENTRIES FOR LATERITE-NI AND NI-SULPHIDE ═══════════════════════════════
    # Added BH-REM-P1 Gap 1 sprint (2026-04-17). These complete coverage of all
    # 3 brainstorm-complete models (orogenic_au + laterite_ni + ni_sulphide).
    # Each entry is model-agnostic — a single shared_key appears once regardless
    # of how many deposit models use it.

    # -- EMIT hyperspectral mineral abundance (both laterite_ni + ni_sulphide) --

    BridgeEntry(
        bhumi_key="",
        shared_key="emit_chlorite",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "EMIT L2B chlorite fractional abundance (ISS EMIT, ±52° latitude, ~60m). "
            "Hyperspectral — 285 VSWIR bands. No 2D spectral inputs in Bhumi. "
            "Used in laterite_ni (proxy for serpentine/chlorite in ultramafic saprolite, "
            "weight 0.55) and ni_sulphide (ultramafic host ID, weight 0.55). "
            "Import from CAGE-IN EMIT engine via JC-TBD-EVIDENCESTACK-EXPORT."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="emit_fe_oxide",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "EMIT L2B iron oxide fractional abundance. Hyperspectral — directly maps "
            "goethite/hematite mineralogy of laterite cap or gossan at 60m. "
            "Used in laterite_ni (weight 0.55) and ni_sulphide (weight 0.55). "
            "Import from CAGE-IN EMIT engine. Note: more specific than broadband "
            "FERRIC/GOSSAN spectral ratios — identifies mineralogy not just spectral ratio."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="emit_vermiculite",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "EMIT L2B vermiculite fractional abundance. Diagnostic of ultramafic "
            "weathering profile development — vermiculite is a direct weathering product "
            "of biotite and phlogopite in ultramafic rocks. Used in laterite_ni only "
            "(weight 0.50). Hyperspectral — no 2D spectral inputs in Bhumi. "
            "Import from CAGE-IN EMIT engine."
        ),
        requires_cage_in_export=True,
    ),

    # -- ASTER / multispectral indices (laterite_ni + ni_sulphide) --

    BridgeEntry(
        bhumi_key="",
        shared_key="NDVI_ANOMALY",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Vegetation suppression index from multispectral NDVI. Captures barren "
            "ferricrete duricrust and Ni/Cr phytotoxicity over ultramafic soils. "
            "Used in laterite_ni (weight 0.70, primary geobotanical discriminant) and "
            "ni_sulphide (weight 0.45, weaker phytotoxicity signal over gossan). "
            "No multispectral inputs in Bhumi. Import from CAGE-IN optical engine."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="VIGS",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Vegetation Interference in Geological Spectra — captures transition zone "
            "between barren laterite and surrounding vegetation. Secondary geobotanical "
            "discriminant complementing NDVI_ANOMALY. Used in laterite_ni (weight 0.50) "
            "and ni_sulphide (weight 0.40). No multispectral inputs in Bhumi. "
            "Import from CAGE-IN optical engine."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="CI_REDEDGE",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Sentinel-2 red-edge chlorophyll index (705/740 nm). Detects Ni phytotoxicity-"
            "induced chlorophyll reduction in tropical vegetation over laterite soils. "
            "Highest spectral contrast for phytotoxicity signal among vegetation stress "
            "indices. Used in laterite_ni (weight 0.50) and ni_sulphide (weight 0.35, "
            "weaker signal). No multispectral inputs in Bhumi. "
            "Import from CAGE-IN optical engine."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="GOETHITE",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "ASTER SWIR goethite index (B4/B2). Discriminates goethite (FeOOH, Ni-hosting "
            "in limonite zone) from hematite (Fe2O3, barren duricrust). Key mineralogical "
            "discriminant for laterite Ni deposit type. Used in laterite_ni (weight 0.70, "
            "primary Ni-zone indicator) and ni_sulphide (weight 0.55, gossanous cap). "
            "No multispectral inputs in Bhumi. Import from CAGE-IN ASTER engine."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="HEMATITE",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "ASTER hematite index (B2/B1). Pisolitic hematite duricrust caps mature "
            "laterite profiles — indicates advanced laterite development but low ore grade "
            "(<0.5% Ni in duricrust itself). Used in laterite_ni only (weight 0.40). "
            "No multispectral inputs in Bhumi. Import from CAGE-IN ASTER engine."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="FERROUS",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Fe2+ absorption from fresh mafic-ultramafic minerals (olivine, pyroxene, "
            "amphibole) at VNIR wavelengths. Identifies host lithology where not deeply "
            "weathered. Used in ni_sulphide only (weight 0.50) — excluded from laterite_ni "
            "because tropical laterite terrain rarely exposes fresh mafic rock. "
            "Multispectral — no 2D spectral inputs in Bhumi. "
            "Import from CAGE-IN optical/ASTER engine."
        ),
        requires_cage_in_export=True,
    ),

    # -- DEM derivatives / geomorphic (laterite_ni only) --

    BridgeEntry(
        bhumi_key="",
        shared_key="slope_inv",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Inverted slope: 1 - normalise(slope_degrees). Low gradient favourable for "
            "laterite profile preservation — laterite Ni deposits develop on peneplain "
            "remnants and gentle interfluves (<5° optimal, <15° marginal). "
            "DEM derivative — no DEM input in Bhumi. Used in laterite_ni only (weight 0.60). "
            "Future BH-REM-Px: could be derived from publicly available SRTM/Copernicus DEM "
            "if DEM import is added to Bhumi inputs. Note: slope_degrees appears as a "
            "laterite_ni VETO layer (V6_steep_slope) but inverted slope is a positive weight."
        ),
        requires_cage_in_export=False,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="height_above_drainage",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Relative elevation above local drainage base level — higher values indicate "
            "surfaces less subject to erosion and better preserved laterite profiles. "
            "DEM + drainage network derivative. No DEM input in Bhumi. "
            "Used in laterite_ni only (weight 0.55). Requires flow-routing analysis "
            "(D8/D-infinity) from a DEM — not computable from drill or geophysics data."
        ),
        requires_cage_in_export=False,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="terrain_roughness_inv",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Inverted topographic roughness: 1 - normalise(std_dev_elevation_window). "
            "Smooth peneplain surfaces indicate preserved laterite profile; rough, "
            "dissected terrain indicates active erosion and profile truncation. "
            "DEM derivative — no DEM input in Bhumi. Used in laterite_ni only (weight 0.45). "
            "Future BH-REM-Px: derive from public DEM if DEM module added to Bhumi."
        ),
        requires_cage_in_export=False,
    ),

    # -- Composite keys: laterite_ni primaries --

    BridgeEntry(
        bhumi_key="",
        shared_key="FERRIC_x_MG_OH",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "FERRIC * MG_OH co-occurrence composite. Both factors MISSING in Bhumi "
            "(no multispectral inputs). The single most diagnostic spectral signature "
            "for laterite Ni — Fe-oxide laterite cap over Mg-OH ultramafic saprolite. "
            "Used in laterite_ni (weight 0.90, top composite) and ni_sulphide (weight 0.65). "
            "Import both factors from CAGE-IN ASTER engine."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="mag_rtp_as_div_radio_k_pct",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Ratio composite: mag_rtp_as / radio_k_pct (AS/K ratio — mafic-ultramafic "
            "discriminant). One factor is NATIVE (mag_rtp_as via c5_magnetics), but "
            "radio_k_pct is MISSING (radiometrics not in Bhumi). Cannot compute the ratio "
            "without both factors. Used in laterite_ni (weight 0.80) and ni_sulphide "
            "(weight 0.75). Import radio_k_pct from CAGE-IN radiometrics engine to enable. "
            "Note: not a PARTIAL upgrade because ratio with a missing denominator is "
            "mathematically undefined — not just confidence-reduced."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="NDVI_ANOMALY_x_MG_OH",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "NDVI_ANOMALY * MG_OH composite: vegetation stress over ultramafic substrate. "
            "Both factors MISSING (no multispectral inputs in Bhumi). "
            "Used in laterite_ni only (weight 0.75). Import from CAGE-IN optical/ASTER engine."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="FERRIC_x_NDVI_ANOMALY",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "FERRIC * NDVI_ANOMALY composite: barren/stressed ferruginous laterite. "
            "Both factors MISSING (no multispectral inputs in Bhumi). "
            "Used in laterite_ni only (weight 0.65). Import from CAGE-IN ASTER engine."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="emit_chlorite_x_emit_fe_oxide",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "EMIT mineral-level product: chlorite * fe_oxide co-occurrence. "
            "Hyperspectral equivalent of FERRIC_x_MG_OH at higher spectral fidelity. "
            "Both factors MISSING (no hyperspectral inputs in Bhumi). "
            "Used in laterite_ni only (weight 0.60). Import from CAGE-IN EMIT engine."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="GOETHITE_x_MG_OH",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "GOETHITE * MG_OH composite: goethite limonite cap over Mg-OH ultramafic saprolite. "
            "More specific than FERRIC_x_MG_OH — goethite (not hematite) is the primary "
            "Ni-hosting Fe-oxyhydroxide in the limonite zone. Both factors MISSING (no "
            "multispectral inputs in Bhumi). Used in laterite_ni only (weight 0.80). "
            "Import from CAGE-IN ASTER engine."
        ),
        requires_cage_in_export=True,
    ),

    # -- Composite keys: ni_sulphide primaries --

    BridgeEntry(
        bhumi_key="",
        shared_key="GOSSAN_x_mag_rtp_as",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "GOSSAN * mag_rtp_as composite: sulphide gossan at surface + pyrrhotite "
            "magnetic anomaly at depth. Bull's-eye target for Ni-sulphide. GOSSAN is "
            "MISSING (no multispectral inputs); mag_rtp_as is NATIVE via c5_magnetics. "
            "Cannot form composite without GOSSAN factor. Used in ni_sulphide only "
            "(weight 0.90, top composite). Import GOSSAN from CAGE-IN ASTER engine."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="MG_OH_x_mag_rtp_as",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "MG_OH * mag_rtp_as composite: ultramafic host rock (MG_OH) coincident with "
            "magnetic anomaly (pyrrhotite). MG_OH is MISSING (no multispectral inputs); "
            "mag_rtp_as is NATIVE via c5_magnetics. Cannot form composite without MG_OH. "
            "Used in ni_sulphide only (weight 0.80). Import MG_OH from CAGE-IN ASTER engine."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="c4_gravity*c5_magnetics",
        shared_key="grav_residual_x_mag_rtp_as",
        bridge_type="PARTIAL",
        confidence=0.85,
        prithvi_approved=True,
        notes=(
            "UPGRADE OPPORTUNITY: grav_residual * mag_rtp_as. Both factors are NATIVE-bridged "
            "in Bhumi (c4_gravity→grav_residual at 0.90, c5_magnetics→mag_rtp_as at 0.85). "
            "Confidence = min(0.90, 0.85) = 0.85 (Amendment 2: min-of-factors rule). "
            "Compute at score time as bhumi_evidence['c4_gravity'] * bhumi_evidence['c5_magnetics']. "
            "Classic dual-geophysical bull's-eye for Ni-sulphide: dense ultramafic body "
            "(gravity) with sulphide accumulation (magnetics). Used in ni_sulphide only "
            "(weight 0.75). [Dr. Prithvi approved 2026-04-18: Kambalda/Raglan paradigm — "
            "textbook dual-geophysical signature. Composite geologically valid.] "
            "Phase 1: scoring engine skips this (bhumi_key is synthetic composite notation). "
            "Phase 2: enable composite computation in score_voxel()."
        ),
    ),

    BridgeEntry(
        bhumi_key="c6_structural_corridor*c5_magnetics",
        shared_key="fault_proximity_x_mag_rtp_as",
        bridge_type="PARTIAL",
        confidence=0.60,
        prithvi_approved=True,
        notes=(
            "UPGRADE OPPORTUNITY: fault_proximity * mag_rtp_as. c5_magnetics→mag_rtp_as "
            "is NATIVE at 0.85; c6_structural_corridor→fault_proximity is PARTIAL at 0.60. "
            "Confidence = min(0.85, 0.60) = 0.60 (Amendment 2: min-of-factors rule). "
            "Targets the conduit geometry: magnetic anomaly on a major structure = "
            "conduit-hosted sulphide. Used in ni_sulphide only (weight 0.70). "
            "[Dr. Prithvi approved 2026-04-18: conduit-hosted sulphide scenario valid for "
            "komatiite-hosted Ni (Cosmos, Mariners precedent). corridors_defined() guard "
            "at runtime still applies — this composite inherits the c6 demotion rule.] "
            "Phase 1: scoring engine skips (synthetic bhumi_key). Phase 2: enable composite."
        ),
    ),

    # ══ ENTRIES FOR GRAPHITE_FLAKE ════════════════════════════════════════════
    # Added BH-REM-P1 Gap 1 sprint (2026-04-17). graphite_flake was brainstorm-
    # completed in Session 4 (2026-04-17) simultaneously with this sprint.
    # 13 new unique layer_keys not previously documented in BRIDGE_TABLE.

    # -- EM / IP geophysical (graphite_flake only) --

    BridgeEntry(
        bhumi_key="",
        shared_key="em_conductivity",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Airborne time-domain or frequency-domain EM conductivity. THE PRIMARY "
            "discovery tool for flake graphite — graphite conductivity 10³–10⁵ S/m "
            "versus silicate host ~10⁻⁸ S/m (11–13 orders of magnitude contrast). "
            "Balama (Mozambique) and Molo (Madagascar) both discovered by EM survey. "
            "NOT in CAGE-IN EvidenceStack — Engineering ticket JC-TBD-EM-CONDUCTIVITY. "
            "No Bhumi source: Bhumi has gravity, magnetics, and seismic — not EM. "
            "graphite_flake model degrades gracefully (required: false) to radiometric/ "
            "structural/spectral proxies when EM is absent."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="em_chargeability",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Induced polarisation (IP) chargeability. Graphite is an electronic "
            "semiconductor generating IP chargeability anomalies in DCIP or TDEM "
            "surveys. Complements em_conductivity: graphite is both conductive AND "
            "chargeable. More relevant for ground-follow-up IP surveys than airborne "
            "reconnaissance. NOT in CAGE-IN EvidenceStack and not in Bhumi. "
            "graphite_flake only (weight 0.35). Ticket JC-TBD-EM-CONDUCTIVITY covers both."
        ),
        requires_cage_in_export=True,
    ),

    # -- Geological capability gaps (graphite_flake only) --

    BridgeEntry(
        bhumi_key="",
        shared_key="metamorphic_grade",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Metamorphic grade eligibility filter. Flake graphite requires upper "
            "amphibolite to granulite facies (Tmax ≥ 580 °C by RSCM geothermometry). "
            "Greenschist-facies carbonaceous matter is turbostratic carbon, not graphite. "
            "NOT in CAGE-IN EvidenceStack — Engineering ticket JC-TBD-METAMORPHIC-GRADE. "
            "No Bhumi source. graphite_flake only (weight 0.80, highest-confidence "
            "geological pre-condition). Interim proxy: litho_favourability trained on "
            "published metamorphic terrane polygons (PARTIAL bridge, family-restricted)."
        ),
        requires_cage_in_export=True,
    ),

    # -- Radiometric primaries (graphite_flake only) --

    BridgeEntry(
        bhumi_key="",
        shared_key="radio_th",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Thorium radiometric channel (ppm Th). Elevated Th in aluminous "
            "high-grade metapelites from accessory monazite/xenotime/zircon. "
            "Th is more immobile than U through upper amphibolite metamorphism "
            "and is retained even in granulite residues. Preferred radiometric "
            "discriminator for graphite_flake hosts. No airborne radiometrics in Bhumi. "
            "graphite_flake only (weight 0.55). Distinct from radio_th_k (ratio): "
            "radio_th is the raw Th channel. Import from CAGE-IN radiometrics engine."
        ),
        requires_cage_in_export=True,
    ),

    # -- Spectral primaries (graphite_flake only) --

    BridgeEntry(
        bhumi_key="",
        shared_key="albedo_suppression",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Low surface albedo proxy for graphite-bearing outcrop. Graphite "
            "reflectance < 0.05 across 0.4–2.5 µm darkens host rock surface. "
            "Pre-computed as 1 − normalised_albedo (S2 Band 4 or Landsat OLI Band 4). "
            "NOT equivalent to graphite mineral identification: EMIT L2B cannot identify "
            "graphite (no VNIR-SWIR absorption features — flat, dark reflectance; "
            "see graphite_flake model_notes.emit_graphite_capability_gap). "
            "Requires multispectral optical input — not in Bhumi. "
            "graphite_flake only (weight 0.60). Import from CAGE-IN optical engine."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="aster_tir_emissivity",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "ASTER TIR emissivity at B11 (8.625 µm). Graphite emissivity 0.97–0.98 "
            "vs quartz-rich host 0.80–0.87 in reststrahlen region — contrast +0.07 to "
            "+0.15 emissivity units. Detection threshold ~15 wt% TGC. NOT in CAGE-IN "
            "EvidenceStack — Engineering ticket JC-TBD-ASTER-TIR-EMISSIVITY. "
            "No Bhumi source. graphite_flake only (weight 0.55)."
        ),
        requires_cage_in_export=True,
    ),

    # -- Geophysical primaries (graphite_flake only) --

    BridgeEntry(
        bhumi_key="",
        shared_key="mag_1vd",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Magnetic first vertical derivative (1VD). Used INVERTED in graphite_flake: "
            "diamagnetic graphite produces low 1VD within host metapelite/gneiss. "
            "Note: c8_mag_gradient is already NATIVE-bridged to mag_tilt (tilt derivative). "
            "mag_1vd (vertical derivative of Vz or TMI) and mag_tilt are related but "
            "mathematically distinct operators — cannot substitute one for the other. "
            "Bhumi computes lateral gradient magnitude, not 1VD. MISSING for now. "
            "graphite_flake only (weight 0.25 standalone; preferred in composite 0.45)."
        ),
        requires_cage_in_export=False,
    ),

    # -- Composite keys (graphite_flake only) --

    BridgeEntry(
        bhumi_key="",
        shared_key="em_conductivity_x_litho_favourability",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "TOP COMPOSITE for graphite_flake (weight 0.88). EM conductivity × litho "
            "favourability — graphite conductivity signal confined to favourable "
            "carbonaceous metapelite host. em_conductivity is MISSING (JC-TBD-EM-CONDUCTIVITY); "
            "litho_favourability is PARTIAL (family-restricted). Cannot form composite "
            "without em_conductivity. When EM is implemented, this will dominate the scorer. "
            "graphite_flake only."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="radio_th_x_litho_favourability",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "radio_th × litho_favourability composite (graphite_flake, weight 0.68). "
            "Elevated Th from aluminous metapelite accessory minerals co-located with "
            "favourable carbonaceous host. radio_th is MISSING (no radiometrics in Bhumi). "
            "Cannot form composite. Import radio_th from CAGE-IN radiometrics engine."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="geochem_pathfinder_x_litho_favourability",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "geochem_pathfinder × litho_favourability composite (graphite_flake, weight 0.62). "
            "Graphite geochemical pathfinder suite (C_graphitic, V, Mo, S) co-located with "
            "carbonaceous metapelite host. geochem_pathfinder is MISSING; litho_favourability "
            "is PARTIAL. Cannot form composite. Import geochem from CAGE-IN geochemical engine."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="radio_th_k_x_fold_hinge_proximity",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "radio_th_k × fold_hinge_proximity composite (graphite_flake, weight 0.60). "
            "Aluminous metapelite Th/K ratio coincident with fold hinge structural control. "
            "Both factors MISSING (radio_th_k: radiometrics not in Bhumi; fold_hinge_proximity: "
            "requires geological mapping input). Cannot form composite. Import from CAGE-IN."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="aster_tir_emissivity_x_albedo_suppression",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "aster_tir_emissivity × albedo_suppression composite (graphite_flake, weight 0.58). "
            "Dual-physical graphite surface detection: TIR emissivity elevation × low visible "
            "albedo. Both factors MISSING (aster_tir_emissivity: JC-TBD-ASTER-TIR-EMISSIVITY; "
            "albedo_suppression: no multispectral in Bhumi). Import both from CAGE-IN."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="mag_1vd_x_litho_favourability",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "mag_1vd × litho_favourability composite (graphite_flake, weight 0.45). "
            "Low magnetic 1VD (diamagnetic graphite body) filtered to lithologically "
            "favourable positions. mag_1vd is MISSING (see standalone mag_1vd entry); "
            "litho_favourability is PARTIAL (family-restricted). Cannot form composite "
            "until mag_1vd is implemented in Bhumi (future DEM-free computation from "
            "existing magnetic grid if 1VD filter is added to m10_depth_corrector)."
        ),
        requires_cage_in_export=False,
    ),

    # ══ ENTRIES FOR GRAPHITE_CARBONATE_HOSTED ═════════════════════════════════
    # Added BH-REM-P1 (2026-04-17). Lac-des-Îles-type marble-hosted flake graphite
    # (Grenville Province). 1 new composite key not present in graphite_flake.

    BridgeEntry(
        bhumi_key="",
        shared_key="emit_carbonate_x_fold_hinge_proximity",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "EMIT carbonate mineral abundance × fold hinge proximity composite "
            "(graphite_carbonate_hosted, weight 0.82). Ankerite/calcite EMIT signal "
            "co-located with fold hinge geometry — diagnostic of the carbonate platform "
            "protolith deformed by amphibolite-facies metamorphism (Lac-des-Îles "
            "paradigm). Both factors individually MISSING in Bhumi: emit_carbonate "
            "requires CAGE-IN EMIT engine; fold_hinge_proximity requires structural "
            "mapping or aeromag derivative. Cannot form composite without both factors. "
            "Import from CAGE-IN via JC-TBD-EVIDENCESTACK-EXPORT."
        ),
        requires_cage_in_export=True,
    ),

    # ══ ENTRIES FOR GRAPHITE_PELITIC_HOSTED ═══════════════════════════════════
    # Added BH-REM-P1 (2026-04-17). Balama/Molo/Epanko-type carbonaceous metapelite-
    # hosted flake graphite (East Africa paradigm). 3 new keys vs graphite_flake:
    # radio_u_ppm, radio_u_over_th (U-enrichment in black shale protolith), and the
    # composite em_conductivity_x_radio_u_over_th.

    BridgeEntry(
        bhumi_key="",
        shared_key="radio_u_ppm",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Uranium radiometric channel (ppm U). Elevated U in carbonaceous black "
            "shale protoliths (organic carbon sorbs U from seawater during deposition). "
            "Used positively in graphite_pelitic_hosted to flag carbonaceous metapelite "
            "hosts (weight 0.55) and at low weight in sedex_pbzn (0.20: anoxic basin "
            "floor U enrichment co-incident with SEDEX feeder zones). NOTE: radio_th_over_u "
            "(Th/U ratio) and radio_u_over_th (U/Th ratio) are separate keys — both "
            "derived from the same airborne radiometric survey but serve different "
            "geological discriminant roles. No radiometrics in Bhumi. "
            "Import from CAGE-IN radiometrics engine via JC-TBD-EVIDENCESTACK-EXPORT."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="radio_u_over_th",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "U/Th ratio radiometric channel. Elevated U/Th flags carbonaceous pelitic "
            "protoliths (anoxic sediments sorb U but not Th). Used in graphite_pelitic_hosted "
            "(weight 0.55) as a positive discriminant for black shale / carbonaceous "
            "metapelite hosts. Inverse of radio_th_over_u: high U/Th favours pelitic "
            "graphite hosts; high Th/U favours aluminous metapelite (granulite). "
            "Both ratios derived from the same airborne radiometric survey but encode "
            "different protolith signals. No radiometrics in Bhumi. "
            "Import from CAGE-IN radiometrics engine."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="em_conductivity_x_radio_u_over_th",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "EM conductivity × U/Th ratio composite (graphite_pelitic_hosted, weight 0.80). "
            "Graphite conductivity anomaly co-located with high U/Th (carbonaceous "
            "metapelite host signature). Both factors individually MISSING: em_conductivity "
            "requires EM survey data (JC-TBD-EM-CONDUCTIVITY); radio_u_over_th requires "
            "airborne radiometrics. This composite is the highest-specificity discriminant "
            "for pelitic-hosted vs. carbonate-hosted graphite: EM confirms graphite "
            "conductor, U/Th confirms black-shale protolith. Import both from CAGE-IN."
        ),
        requires_cage_in_export=True,
    ),

    # ══ ENTRIES FOR SEDEX_PBZN ════════════════════════════════════════════════
    # Added BH-REM-P1 (2026-04-17). SEDEX Pb-Zn (Kayad, HYC, Sullivan, Gamsberg).
    # deposit_family: hydrothermal_sedex.
    # 17 new primary + 7 new composite keys. Several composites are PARTIAL
    # because both c4_gravity and c6_structural_corridor are bridged.

    # -- Radiometric primaries (sedex_pbzn) --

    BridgeEntry(
        bhumi_key="",
        shared_key="radio_th_over_u",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Th/U ratio radiometric channel. High Th/U indicates granulite-facies "
            "or oxidised basement lacking carbonaceous matter (unfavourable SEDEX host); "
            "low Th/U indicates U retention in reduced / carbonaceous sediments "
            "(favourable for SEDEX basin floor). Used in sedex_pbzn at low weight (0.30) "
            "as a basin-floor anoxia proxy. Inverse of radio_u_over_th. "
            "No radiometrics in Bhumi. Import from CAGE-IN radiometrics engine."
        ),
        requires_cage_in_export=True,
    ),

    # -- Geophysical primaries (sedex_pbzn) --

    BridgeEntry(
        bhumi_key="",
        shared_key="mag_susc",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Magnetic susceptibility model (3D inversion). Used in sedex_pbzn at weight "
            "0.80 — pyrrhotite in SEDEX ore zones elevates susceptibility, while "
            "carbonate-dominant host rocks are typically non-magnetic. Distinct from "
            "mag_rtp_as (analytic signal computed from susceptibility or TMI) and mag_tilt: "
            "mag_susc is the volumetric susceptibility model from 3D inversion, not a "
            "filter/derivative. Bhumi c5_magnetics uses analytic signal magnitude (bridged "
            "to mag_rtp_as as NATIVE) — raw susceptibility model is not computed by Bhumi. "
            "MISSING: requires 3D inversion of TMI data, which is not part of Bhumi's "
            "current processing chain. Future BH-REM-Px: integrate 3D mag inversion output "
            "as an optional supplementary grid."
        ),
        requires_cage_in_export=False,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="grav_laplacian",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Gravity Laplacian (second vertical derivative of Bouguer anomaly). Enhances "
            "shallow causative bodies by sharpening anomaly boundaries — identifies dense "
            "ore-body contacts within host stratigraphy. Used in sedex_pbzn (weight 0.75). "
            "Distinct from grav_residual (first-order anomaly) and grav_gradient (horizontal "
            "gradient). Bhumi does not compute the Laplacian from its gravity grid. "
            "MISSING: would require adding a ∂²g/∂z² filter to m10_depth_corrector or a "
            "dedicated gravity derivative module. Engineering ticket: BH-REM-Px-GRAV-LAPLACIAN."
        ),
        requires_cage_in_export=False,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="grav_gradient",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Horizontal gravity gradient magnitude (sqrt(∂g/∂x² + ∂g/∂y²)). Delineates "
            "density contrasts and structural contacts — in SEDEX context, marks the "
            "boundary between dense ore-hosting stratigraphy and lighter hanging-wall "
            "rocks. Used in sedex_pbzn (weight 0.65). Distinct from grav_residual "
            "(anomaly value) and grav_laplacian (curvature). Bhumi c4_gravity is bridged "
            "to grav_residual (anomaly value) — the horizontal gradient is not currently "
            "computed. MISSING: add horizontal gradient filter to Bhumi gravity module. "
            "Engineering ticket: BH-REM-Px-GRAV-GRADIENT."
        ),
        requires_cage_in_export=False,
    ),

    # mag_gradient — PROMOTED TO NATIVE (BH-02, 2026-04-18)
    # Dr. Prithvi ruling: c8_mag_gradient IS mag_gradient (same computation).
    # NATIVE bridge entry is in the NATIVE BRIDGES section above (confidence 0.90).
    # This MISSING placeholder has been removed.

    BridgeEntry(
        bhumi_key="",
        shared_key="ip_chargeability",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Induced polarisation (IP) chargeability (ms). Sulphide minerals (pyrite, "
            "pyrrhotite, sphalerite, galena) are electronic semiconductors generating "
            "strong IP responses. For SEDEX Pb-Zn, IP chargeability directly maps the "
            "sulphide ore column (weight 0.70 in sedex_pbzn). NOT the same as "
            "em_chargeability (which is from EM data) — ip_chargeability here is from "
            "DCIP or gradient array IP surveys (ground geophysics). "
            "Not in CAGE-IN EvidenceStack. No IP inputs in Bhumi (Bhumi uses gravity, "
            "magnetics, seismic — not IP). Engineering ticket: JC-TBD-IP-CHARGEABILITY "
            "(separate from JC-TBD-EM-CONDUCTIVITY)."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="grav_3d_inversion_proximity",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Proximity to dense body from 3D gravity inversion (UBC-GIF or equivalent). "
            "3D inversion recovers volumetric density model; proximity to high-density "
            "body isolines identifies buried dense ore zones at depth. Used in sedex_pbzn "
            "(weight 0.55). Distinct from grav_residual (surface anomaly value): proximity "
            "to 3D inversion body is a depth-resolved signal, not a surface measurement. "
            "Bhumi does not currently perform 3D gravity inversion. MISSING. "
            "Engineering ticket: BH-REM-Px-GRAV-3D-INVERSION."
        ),
        requires_cage_in_export=False,
    ),

    # -- Geological / stratigraphic primaries (sedex_pbzn) --

    BridgeEntry(
        bhumi_key="",
        shared_key="stratigraphic_position",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Stratigraphic position favourability — proximity to the SEDEX exhalite "
            "horizon within a mapped stratigraphy column. SEDEX ore is stratabound within "
            "a specific stratigraphic interval (e.g., HYC Black Star Shale, Kayad QMS "
            "horizon). Used in sedex_pbzn (weight 0.55). Requires: (a) a measured "
            "stratigraphic column, and (b) a lithostratigraphic interpolation across the "
            "3D volume. Not directly computable from geophysics alone. Bhumi's c1_lithology "
            "captures host-rock code but not stratigraphic position within that rock. "
            "MISSING: requires dedicated stratigraphy interpolation module or geological "
            "model import. Engineering ticket: BH-REM-Px-STRAT-POSITION."
        ),
        requires_cage_in_export=False,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="basin_margin_proximity",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Proximity to a syn-sedimentary basin margin fault or continental margin "
            "hinge zone. SEDEX ore systems localise at basin-margin fault escarpments "
            "controlling sub-seafloor hydrothermal circulation cells (e.g., HYC and "
            "Kayad both on reactivated Proterozoic basin-bounding faults). Used in "
            "sedex_pbzn (weight 0.45). Requires basin-architecture interpretation from "
            "regional geology — not derivable from local geophysics without basin-scale "
            "structural mapping. MISSING: requires regional geological framework input. "
            "Partially captured by c6_structural_corridor → fault_proximity (PARTIAL), "
            "but basin-margin proximity is a regional context layer, not a local fault "
            "proximity metric. Engineering ticket: BH-REM-Px-BASIN-MARGIN."
        ),
        requires_cage_in_export=True,
    ),

    # -- Geochemical anomaly intensity suite (sedex_pbzn) --
    # These are voxel-interpolated downhole assay concentrations (not surface geochem).
    # Bhumi's drill processor (m02) handles Zn/Pb/Ag assays but does not produce
    # anomaly_intensity layers. m09_column_mapper.py maps assay columns.
    # MISSING for now — engineering feasibility for BH-REM-Px.

    BridgeEntry(
        bhumi_key="",
        shared_key="anomaly_intensity_zn",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Voxel-interpolated Zn assay concentration (normalised anomaly intensity). "
            "Direct ore-grade signal for SEDEX Pb-Zn — highest weight primary in "
            "sedex_pbzn (weight 0.75). Bhumi's m02_drill_processor.py ingests downhole "
            "assay data and m09_column_mapper.py identifies Zn columns (aliases: 'Zn', "
            "'ZN_ppm', 'Zinc_pct', etc.). HOWEVER, Bhumi currently does not interpolate "
            "assay data into the voxel grid as a prospectivity layer — assays are used "
            "for grade model calibration (c9_grade_model), not as a standalone WLC layer. "
            "UPGRADE OPPORTUNITY: extend m02 to produce anomaly_intensity_zn grid via "
            "OK/IDW interpolation of Zn assays. Engineering ticket: BH-REM-Px-GEOCHEM-VOXEL."
        ),
        requires_cage_in_export=False,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="anomaly_intensity_pb",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Voxel-interpolated Pb assay concentration (normalised anomaly intensity). "
            "SEDEX Pb-Zn co-pathfinder (weight 0.70 in sedex_pbzn). Same engineering "
            "gap as anomaly_intensity_zn: Bhumi ingests Pb assays but does not produce "
            "a voxel interpolation layer. m09_column_mapper.py aliases: 'Pb', 'PB_ppm', "
            "'Lead_pct', etc. Engineering ticket: BH-REM-Px-GEOCHEM-VOXEL (same ticket)."
        ),
        requires_cage_in_export=False,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="anomaly_intensity_ag",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Voxel-interpolated Ag assay concentration (normalised anomaly intensity). "
            "Silver is a consistent SEDEX co-product and pathfinder for the high-grade "
            "core (weight 0.50 in sedex_pbzn). Same engineering gap as anomaly_intensity_zn. "
            "m09_column_mapper.py aliases: 'Ag', 'AG_ppm', 'Silver_ppm', etc. "
            "Engineering ticket: BH-REM-Px-GEOCHEM-VOXEL."
        ),
        requires_cage_in_export=False,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="anomaly_intensity_ba",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Voxel-interpolated Ba assay concentration (normalised anomaly intensity). "
            "Barite (BaSO₄) is a diagnostic exhalite mineral in SEDEX systems — Ba "
            "anomalies in drill core indicate proximity to exhalative vent zone "
            "(weight 0.45 in sedex_pbzn). Same engineering gap as anomaly_intensity_zn. "
            "Note: Ba is a key SEDEX indicator even at sub-economic concentrations — "
            "it marks the exhalite horizon irrespective of Pb-Zn grade. "
            "m09_column_mapper.py likely needs Ba alias addition. "
            "Engineering ticket: BH-REM-Px-GEOCHEM-VOXEL."
        ),
        requires_cage_in_export=False,
    ),

    # -- Composite keys: sedex_pbzn --

    BridgeEntry(
        bhumi_key="c6_structural_corridor*c1_lithology",
        shared_key="fault_proximity_x_litho_favourability",
        bridge_type="PARTIAL",
        confidence=0.60,
        prithvi_approved=True,
        notes=(
            "UPGRADE OPPORTUNITY: fault_proximity × litho_favourability composite "
            "(sedex_pbzn, weight 0.85). Both factors are PARTIAL-bridged in Bhumi when "
            "model is hydrothermal_sedex family: c6_structural_corridor → fault_proximity "
            "(PARTIAL, conf=0.60, corridors_defined() guard); c1_lithology → litho_favourability "
            "(PARTIAL, conf=0.65, deposit_family_restriction=['hydrothermal_sedex','sedimentary']). "
            "Confidence = min(0.60, 0.65) = 0.60 (Amendment 2: min-of-factors rule). "
            "This composite is the top discriminant for SEDEX: fault (feeder conduit) "
            "within favourable host stratigraphy. [Dr. Prithvi approved 2026-04-18: "
            "feeder fault within favourable stratigraphy is the fundamental SEDEX architectural "
            "control — Kayad, HYC, Sullivan all validate this. Family restriction enforced.] "
            "deposit_family_restriction=['hydrothermal_sedex'] enforced at coverage report level."
        ),
        deposit_family_restriction=["hydrothermal_sedex"],
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="grav_laplacian_x_mag_susc",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Gravity Laplacian × mag_susc composite (sedex_pbzn, weight 0.85). "
            "Dense ore body (Laplacian) co-located with pyrrhotite susceptibility — "
            "the dual-geophysical bull's-eye for SEDEX sulphide ore column. Both factors "
            "MISSING: grav_laplacian requires 2nd-derivative gravity filter (not in Bhumi); "
            "mag_susc requires 3D magnetic inversion (not in Bhumi). Cannot form composite."
        ),
        requires_cage_in_export=False,
    ),

    BridgeEntry(
        bhumi_key="c6_structural_corridor*c4_gravity",
        shared_key="fault_proximity_x_grav_residual",
        bridge_type="PARTIAL",
        confidence=0.60,
        prithvi_approved=True,
        notes=(
            "UPGRADE OPPORTUNITY: fault_proximity × grav_residual composite "
            "(sedex_pbzn, weight 0.80). c4_gravity → grav_residual is NATIVE (conf=0.90); "
            "c6_structural_corridor → fault_proximity is PARTIAL (conf=0.60, corridors_defined() "
            "guard applies). Confidence = min(0.90, 0.60) = 0.60 (Amendment 2). "
            "Geological meaning: dense sulphide ore column co-located with fault conduit — "
            "feeder fault + ore gravity signature. Classic SEDEX exploration target. "
            "[Dr. Prithvi approved 2026-04-18: fault conduit + dense sulphide gravity "
            "signature validated by Mount Isa corridor and Kayad brownfields data. "
            "corridors_defined() guard inherited from c6 component — applies at runtime.] "
            "Runtime: corridors_defined() demotion logic in score_voxel() applies to "
            "this composite (inherited from c6 component)."
        ),
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="grav_gradient_x_mag_gradient",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "Horizontal gravity gradient × horizontal magnetic gradient composite "
            "(sedex_pbzn, weight 0.70). Dual-gradient product marks density-susceptibility "
            "contact edges — used to isolate SEDEX ore columns that show both density "
            "contrast (dense sulphides) and susceptibility contrast (pyrrhotite). "
            "Both factors MISSING: grav_gradient not computed by Bhumi; mag_gradient "
            "pending Dr. Prithvi ruling on c8_mag_gradient dual-role (see mag_gradient entry). "
            "Cannot form composite."
        ),
        requires_cage_in_export=False,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="grav_residual_x_mag_susc",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "grav_residual × mag_susc composite (sedex_pbzn, weight 0.70). Dense "
            "sulphide body (gravity) co-located with pyrrhotite susceptibility (mag_susc). "
            "grav_residual is NATIVE-bridged via c4_gravity; mag_susc is MISSING (3D "
            "inversion not in Bhumi). Cannot form composite without mag_susc factor."
        ),
        requires_cage_in_export=False,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="ip_chargeability_x_em_conductivity",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "IP chargeability × EM conductivity composite (sedex_pbzn, weight 0.70). "
            "Sulphide ore column is both chargeable (IP) and conductive (EM). The co-"
            "location product is the most selective downhole-equivalent geophysical "
            "discriminant for massive sulphide. Both factors MISSING: ip_chargeability "
            "is from ground DCIP surveys (not in Bhumi); em_conductivity is from airborne "
            "TDEM (not in Bhumi). Cannot form composite. Engineering tickets: "
            "JC-TBD-IP-CHARGEABILITY, JC-TBD-EM-CONDUCTIVITY."
        ),
        requires_cage_in_export=True,
    ),

    BridgeEntry(
        bhumi_key="",
        shared_key="GOSSAN_x_grav_residual",
        bridge_type="MISSING",
        confidence=0.0,
        prithvi_approved=False,
        notes=(
            "GOSSAN × grav_residual composite (sedex_pbzn, weight 0.60). Surface gossan "
            "(ASTER Fe-oxide) co-located with positive gravity anomaly (dense sulphide "
            "at depth) — gossan as surface expression of buried massive sulphide. "
            "GOSSAN is MISSING (no multispectral inputs in Bhumi); grav_residual is "
            "NATIVE via c4_gravity. Cannot form composite without GOSSAN factor. "
            "Import GOSSAN from CAGE-IN ASTER engine."
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


def _is_bridge_active_for_family(entry: BridgeEntry, deposit_family: Optional[str]) -> bool:
    """
    Return True if the bridge applies to the given deposit family.

    If the entry has no deposit_family_restriction, it always applies.
    If deposit_family is None (caller did not specify), restriction is not enforced
    (backwards compatibility).
    """
    if entry.deposit_family_restriction is None:
        return True
    if deposit_family is None:
        return True  # No family specified — do not enforce (backwards compat)
    return deposit_family in entry.deposit_family_restriction


def get_coverage_report(model_weights: list, deposit_family: Optional[str] = None) -> dict:
    """
    Compute bridge coverage metrics for a list of EvidenceWeight objects.

    Coverage is weighted by confidence: NATIVE entries with confidence 0.90
    contribute more to matched_weight_mass than PARTIAL entries at 0.60.

    Parameters
    ----------
    model_weights : list[EvidenceWeight]
        All weight entries from a loaded DepositModel.
    deposit_family : str, optional
        The deposit family of the model being scored (e.g., 'orogenic',
        'magmatic', 'supergene', 'hydrothermal_sedex', 'sedimentary').
        When provided, PARTIAL bridges with deposit_family_restriction set are
        treated as MISSING if the family is not in the restriction list.
        If None, family restriction is not enforced (backwards compatibility).

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

        # Apply deposit_family_restriction: demote out-of-family PARTIAL to MISSING
        if entry is not None and not _is_bridge_active_for_family(entry, deposit_family):
            entry = None  # Treat as MISSING for this deposit family

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
