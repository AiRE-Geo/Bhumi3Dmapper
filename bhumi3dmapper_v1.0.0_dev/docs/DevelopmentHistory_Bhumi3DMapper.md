# Development History — Bhumi3DMapper

**Append-only log. Never delete or edit past entries.**
**Maintainer:** Scrummy AI (AiRE dev team)
**Rule:** Every session with architectural significance gets an entry before the session closes.

---

## v1.0.0 — Initial Release
**Date:** 2026-04 (exact: commit `e70006c`)
**Author:** AiRE dev team

First production release of Bhumi3DMapper as a QGIS plugin for 3D mineral prospectivity mapping.

**Architecture:** Single-engine Kayad c-criterion scoring.
- Discretises a 3D model space into voxels
- Computes prospectivity score per voxel using geophysical, geological, and drillhole evidence
- Calibrated on Kayad Lead-Zinc Mine (Hindustan Zinc / Vedanta, Rajasthan): 2,112 drill holes + gravity + magnetic inversion slices

**Core modules delivered:**
- `m01–m04`: data loader, grid builder, desurvey, scoring engine
- `m04_scoring_engine.py`: 11-criterion WLC engine (Proximity model) + 10-criterion (Blind model)
- Criteria: `c1_lithology`, `c2_pg_halo`, `c3_csr_standoff`, `c4_gravity`, `c5_magnetics`, `c6_structural_corridor`, `c7_plunge_proximity`, `c8_mag_gradient`, `c9_grade_model`, `c10_ore_envelope`
- Config-driven thresholds: `ProjectConfig.criterion_thresholds` (47 thresholds via `ScoringThresholdsConfig`)

---

## v1.1.0 — Critical Scoring Bug Fix
**Date:** 2026-04 (commit `376eccd`)
**Sprint:** 9

Fixed critical scoring bug. Corrected z_levels handling. Resolved phantom test failures. Import structure stabilised.

---

## v1.2.0 — Spatial Accuracy
**Date:** 2026-04 (commit `02f530f`)
**Sprint:** 10

Added polygon area computation, GDAL integration, drillhole desurvey (minimum curvature method). Proven +674 VH cells on 80-hole complex testbed.

---

## v1.3.0 — Deposit-Agnostic Scoring
**Date:** 2026-04 (commit `28db032`)
**Sprint:** 11–12

All thresholds made configurable — engine no longer hardcoded to Kayad geometry. Test coverage extended across deposit types.

---

## v1.4.0 — Deposit Presets, Extended Test Coverage, Release Prep
**Date:** 2026-04 (commit `8c4f546`)
**Sprint:** 13–15

Added `core/presets/`: 4 JSON deposit presets (`sedex_pbzn`, `vms_cuzn`, `epithermal_au`, `porphyry_cumo`). These are independent of the shared repo; to be superseded by BH-REM-P1 bridge once shared-repo coverage is complete.

**Decision logged:** Presets are a transitional mechanism. They must not diverge from `AiRE-DepositModels/` once shared-repo models are brainstorm-complete for those deposit types.

---

## v2.0 — UX Sprint + S16 Kayad Fixes
**Date:** 2026-04 (commits `9e50910`, `b6f4137`, `ab656cf`)
**Sprint:** 16

**Deliverables:**
- Full UX sprint: field geologist usability — 8 job cards
- 217 tests passing (baseline at v2.0)
- Minimum curvature desurvey wired (`m07_desurvey.py → m02_drill_processor.py`)
- DQ hard gate (`m12_data_quality.py`): 12 checks, 3 block conditions, user-acknowledges before scoring
- Fuzzy column mapping (`m09_column_mapper.py`): 13+ aliases per field, catches lat/long-as-UTM
- Installable ZIP produced

**Architectural note:** Kayad c-criterion engine (`m04_scoring_engine.py`) designated as Engine 1. **PERMANENT RULE: Engine 1 is never replaced, disabled, or deprecated.** It is the primary production engine for Kayad-geometry targets.

---

## v2.1 — Two-Engine Architecture + Evidence Key Bridge (BH-REM-P1)
**Date:** 2026-04-17
**Sprint:** BH-REM-P1 (4 gaps)
**Commits:** `6ee63f5` (skeleton) → `debc3f0` → `32c9736` → `2e0e84a` → `c18aa9c`
**Decision authority:** Amit Tripathi (G4), Dr. Prithvi geological sign-offs

**Architectural pivot:** Added Engine 2 (JSON-driven WLC reconnaissance) alongside Engine 1. Two-engine pattern is permanent — additive, never replacing.

**Session 3 decisions recorded** (orogenic gold brainstorming):
1. Shared repo `AiRE-DepositModels/` is LIVE — single source of truth for deposit model weights
2. `orogenic_au.json` delivered (20 primaries + 10 composites + 2 vetoes + 4 model_notes)
3. Two-engine architecture formalised — Engine 1 (Kayad), Engine 2 (JSON-WLC)
4. Evidence Key Bridge (BH-REM-P1) required before shared-repo JSON scores are valid
5. Structural veto WITHDRAWN for `orogenic_au` — `fault_proximity=0.80` weight only
6. `radio_k_pct` is POSITIVE in `orogenic_au` (sericite enriches K), INVERTED in laterite/Ni models
7. `CARBONATE` weight conservative at 0.60 pending improved ASTER formula
8. `emit_carbonate` at 0.75 is primary carbonate signal (outranks CARBONATE)
9. `LINEAMENT_DENSITY` provenance caveat for humid tropics — SAR/aeromag provenance required
10. Single composite model absorbs full orogenic-Au continuum (pure metamorphic through IROG)
11. `irog.json` superseded by `orogenic_au`
12. `model_notes` MUST propagate to output — never strip
13. 3D additive fields must be honoured even if no current model uses them
14. Bhumi's 4 presets conflict with one-source-of-truth — to be bridged or deprecated

**Deliverables (Gap 1–4):**
- `core/evidence_key_bridge.py` — BRIDGE_TABLE with 3 NATIVE + 2 PARTIAL + MISSING entries for 4 brainstorm-complete models (laterite_ni, ni_sulphide, orogenic_au, graphite_flake)
- `modules/m13_json_scoring_engine.py` — JSON-driven WLC engine with LayerReport, depth attenuation (Option A), deposit_family wiring
- `core/shared_repo_loader.py` — path resolver: env var → sibling → Dropbox → SharedRepoNotFoundError
- `ui/model_selector.py` — 4-band coverage indicator widget (green/yellow/orange/red), block-state dialog
- `CLAUDE.md` — session instructions, permanent rules, pre-flight checklist
- 291 → 293 tests passing

**Dr. Prithvi rulings implemented:**
- `c1_lithology → litho_favourability`: `deposit_family_restriction=['hydrothermal_sedex','sedimentary']`
- `c6_structural_corridor → fault_proximity`: runtime `corridors_defined()` guard

---

## v2.2 — Post-Sprint Cleanup + 3 New Models
**Date:** 2026-04-17 (session continuation)
**Commits:** `9829b97`, `f08f56f`, `8a8f59d`, `3368cd2`, `f1bd18b`

**New brainstorm-complete models discovered via CI gate:**
Three models added to shared repo same day (`graphite_carbonate_hosted`, `graphite_pelitic_hosted`, `sedex_pbzn`) were caught by `test_all_brainstorm_complete_models_documented` when `corridors_defined()` implementation triggered a full test run.

**Deliverables:**
- 24 new BRIDGE_TABLE entries for the 3 new models (commit `9829b97`)
- `StructuralConfig.corridors_defined()` implemented (`user_defined: bool = False` field, commit `8a8f59d`)
- `ModelSelectorWidget.__init__` wired with `structural_corridors_defined` param (commit `f08f56f`)
- `SCHEMA_ROADMAP.md` Option B section authored in shared repo
- `AiRE-DepositModels/README.md` "Consumer engines" section added
- 293 tests passing, tree clean, pushed to `origin/main`

**New PARTIAL composites added (pending Dr. Prithvi sign-off at time of commit):**
- `grav_residual_x_mag_rtp_as` (ni_sulphide, conf=0.85)
- `fault_proximity_x_mag_rtp_as` (ni_sulphide, conf=0.60)
- `fault_proximity_x_litho_favourability` (sedex_pbzn, conf=0.60, family-restricted)
- `fault_proximity_x_grav_residual` (sedex_pbzn, conf=0.60)

---

## v2.3 — Team Review Sprint (BH-POST-P1)
**Date:** 2026-04-18
**Sprint:** BH-POST-P1 (cards BH-01 through BH-05)
**Authority:** Amit Tripathi G4 (team meeting 2026-04-18)

**Decisions made in team meeting:**

*Dr. Prithvi rulings (geological):*
- All 4 composite PARTIALs approved (`prithvi_approved=True`)
- `c8_mag_gradient` dual-role resolved: NATIVE to `mag_gradient` (0.90), PARTIAL to `mag_tilt` (0.70, amplitude normalisation note). Previous NATIVE 0.80 bridge to `mag_tilt` was imprecise.
- Vein-hosted graphite added to brainstorm queue (after IOCG)

*Gandalf QA findings (3 defects):*
1. `subsurface_depth_m` silently passes with no warning when surface elevation is unset — fix: `warnings.warn()` (BH-05)
2. Coverage fraction optimistic when `structural_corridors_defined=False` — documented caveat (CLAUDE.md)
3. Composite PARTIAL skip reason misleading (`NO_VALUE` vs `COMPOSITE_NOT_IMPLEMENTED`) — fix: detect `"*"` in `bhumi_key` (BH-04)

*Lala concerns (efficiency):*
- Double JSON file read in `JsonScoringEngine.__init__` — ticket BH-06
- Full engine init in UI coverage pre-check — ticket BH-06 (lightweight function)

*Rose AI (integration):*
- `JC-TBD-EVIDENCESTACK-EXPORT` must be specced jointly with CAGE-IN before Bhumi-side implementation. Ticket BH-07, blocked on CAGE-IN session.

*Vimal AI (operational):*
- Daily push discipline added to CLAUDE.md
- Shared repo Dropbox path-with-spaces caveat documented

**Deliverables this session:** BH-01 (this file) + BH-02 + BH-03 + BH-04 + BH-05

---
*Next entry: append below this line when the next architecturally significant session completes.*
