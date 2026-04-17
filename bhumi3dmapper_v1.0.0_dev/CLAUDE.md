# Bhumi3DMapper — Session Start Instructions (CLAUDE.md)

**Plugin:** Bhumi3DMapper v2.0  
**Repository:** AiRE-Geo/Bhumi3Dmapper (GitHub)  
**Language:** Python 3.x, QGIS Plugin API  
**Last updated:** 2026-04-17 (BH-REM-P1 completion sprint)

Read this file at the start of every Bhumi development session.
It records all standing architectural decisions, permanent rules, and pending items.
Do not re-derive decisions recorded here — they required geological sign-off.

---

## 1. Project Identity

Bhumi3DMapper is a QGIS plugin for 3D mineral prospectivity mapping.
It discretises a 3D model space into voxels and computes a prospectivity score per voxel
using geophysical, geological, and spectral evidence layers provided by the user.

**Version 2.0 (two-engine architecture, Session 3, 2026-04-17):**  
Engine 1 — Kayad c-criterion brownfields engine  
Engine 2 — JSON-driven WLC reconnaissance engine (reads AiRE shared deposit model repo)

---

## 2. Architecture — Two-Engine Design (Session 3, 2026-04-17, permanent)

### Engine 1 — Kayad c-criterion engine
- **File:** `bhumi3dmapper/modules/m04_scoring_engine.py`
- **Type:** Brownfields, calibrated on Kayad Pb-Zn mine data
- **Use:** Where the user has Bhumi's full geophysical + geological input stack
- **CRITICAL:** **NEVER replace, disable, or deprecate Engine 1.** It is the primary production engine for Kayad-geometry targets. Any changes to m04 require explicit approval from Amit Tripathi.

### Engine 2 — JSON-driven WLC engine
- **File:** `bhumi3dmapper/modules/m13_json_scoring_engine.py`
- **Type:** Reconnaissance — reads any deposit model from the AiRE shared repo
- **Source of truth:** `AiRE-DepositModels/` shared repository (path resolved via `core/shared_repo_loader.py`)
- **Bridge:** `core/evidence_key_bridge.py` — maps Bhumi voxel vocabulary (c4_gravity, c5_magnetics, etc.) to shared-repo layer_key vocabulary (grav_residual, mag_rtp_as, etc.)

### How the user picks the engine
Wizard page 2: user selects "Brownfields (Kayad geometry)" → Engine 1, or
"Deposit-type reconnaissance (JSON model)" → Engine 2 + `ui/model_selector.py`.

### Shared repo path resolution (`core/shared_repo_loader.py`)
1. Env var `AIRE_DEPOSIT_MODELS` (highest priority)
2. Sibling-directory walk from plugin root
3. Hardcoded Dropbox fallback: `E:\MPXG Exploration Dropbox\...\AiRE-DepositModels`
4. `SharedRepoNotFoundError` (fail loud)

**Never hardcode the shared repo path anywhere else.** Always use `get_repo_root()`.

---

## 3. Module Structure (m01–m13)

| Module | Purpose |
|---|---|
| `m01_data_loader.py` | Input data ingest — geophysics, geology, drillhole CSVs |
| `m02_grid_builder.py` | 3D voxel grid construction from bounding box + cell size |
| `m03_desurvey.py` | Drillhole desurvey (minimum curvature); DQ gate, fuzzy column mapping |
| `m04_scoring_engine.py` | **Engine 1** — Kayad c-criterion WLC scoring. NEVER REPLACE. |
| `m05_voxel_writer.py` | Write scored voxel grids to GeoTIFF / CSV / VTK |
| `m06_visualiser.py` | QGIS 3D scene wiring for voxel layer display |
| `m07_report_generator.py` | HTML + PDF run report generation |
| `m08_threshold_classifier.py` | Prospectivity → target classification (high/med/low) |
| `m09_uncertainty_estimator.py` | Bootstrap confidence intervals on voxel scores |
| `m10_depth_corrector.py` | Depth-to-target corrections for geophysical layers |
| `m11_structural_analyser.py` | Structural corridor geometry (N28E/N315E Kayad defaults) |
| `m12_litho_classifier.py` | Rock code → litho_favourability mapping (SEDEX calibration) |
| `m13_json_scoring_engine.py` | **Engine 2** — JSON-driven WLC reconnaissance engine |

---

## 4. Evidence Key Bridge (`core/evidence_key_bridge.py`)

### BRIDGE_TABLE
Maps Bhumi voxel vocabulary → AiRE shared-repo `layer_key` vocabulary.
Three statuses:

| Status | Meaning | Confidence |
|---|---|---|
| NATIVE | 1:1 semantic equivalent | ≥ 0.80 |
| PARTIAL | Approximate equivalence, documented mismatch | 0.30–0.79 |
| MISSING | No Bhumi source — weight skipped, coverage penalty | 0.0 |

**Rules for BRIDGE_TABLE:**
- Every NATIVE or PARTIAL entry requires Dr. Prithvi geological sign-off (`prithvi_approved=True`)
- PARTIAL bridges with `prithvi_approved=False` generate a warning in every `LayerReport`
- MISSING entries are acceptable — they document the gap with geological notes
- Composite PARTIAL entries use `confidence = min(confidence of all factors)` (Amendment 2)
- `deposit_family_restriction` on a PARTIAL entry causes it to be treated as MISSING for families outside the restriction list

### Coverage thresholds
- ≥ 75% — green (good)
- 50–75% — yellow (adequate, minor warning)
- 25–50% — orange (LOW, prominent warn in UI)
- < 25% — red (CRITICAL, block scoring unless `override_low_coverage=True`)

### Approved PARTIAL bridges (as of 2026-04-17)
1. `c1_lithology → litho_favourability` at 0.65 — **APPROVED by Dr. Prithvi**, CONDITIONAL on `deposit_family_restriction=['hydrothermal_sedex', 'sedimentary']`. Treated as MISSING for orogenic, magmatic, supergene families.
2. `c6_structural_corridor → fault_proximity` at 0.60 — **APPROVED by Dr. Prithvi**, CONDITIONAL on runtime `StructuralConfig.corridors_defined()` returning True. If False, demoted to MISSING at score time; UI warning emitted.

### CI gate
`test/test_evidence_key_bridge.py::TestEveryModelWeightHasASource::test_all_brainstorm_complete_models_documented` — must pass for ALL brainstorm-complete models before any model addition is merged. Zero undocumented keys permitted.

---

## 5. Permanent Rules (never override without explicit team decision)

### Architecture
- **No QGIS imports in `core/` or `modules/`** — pure Python only. QGIS API (incl. `qgis.PyQt`) permitted only in `ui/` and `bhumi3dmapper.py`. Enforced by `test/test_ui_no_qgis_core.py`.
- **No weight without a citation** — shared-repo rule, applies to any locally calibrated weight too. `EvidenceWeight.citation` is a required non-empty field; `__post_init__` rejects empty strings.
- **Structural proximity is weight-only, NEVER veto** (Session 1 + Session 3 standing rule). Faults are preferential loci, not binary gatekeepers. Do not add a veto on structural proximity in any deposit model.
- **`model_notes` must propagate to `LayerReport` output** — never strip silently. `LayerReport.model_notes` is always populated from `DepositModel.model_notes`.
- **`invert` flag is per-weight, per-model** — no universal layer polarity. Whether a layer is inverted is a geological decision recorded in each model's weight entry.
- **Never bridge radiometric from potential fields** — radio_k_pct, radio_th_k cannot be approximated from gravity or magnetics. They are MISSING until airborne radiometric data is imported.
- **`fault_intersection_density` is BH-REM-P2 scope** — do not attempt to compute it in Phase 1 from Bhumi's structural inputs.

### Scoring
- **WLC formula:** `score = Σ(model_weight × bridge_confidence × depth_factor × evidence_value) / Σ(effective_weights)` for all non-skipped layers
- **Depth factor** computed from raw JSON `depth_extent` dict via `compute_depth_factor()` — already wired in `m13` (BH-REM-P1 Gap 2, Option A). Phase 3: extend `EvidenceWeight` dataclass natively.
- **Coverage is pre-computed** at `JsonScoringEngine.__init__` time, not recalculated per voxel
- **`deposit_family`** is passed from the manifest entry to `get_coverage_report()` — do not hardcode family strings in the engine

### Testing
- **Test-first (Gandalf rule):** for CI gate additions, write the failing test first, observe the failure with exact key list, then add table entries to satisfy it
- **263 tests passing** at BH-REM-P1 close (Gap 1 + Gap 2 add ~20 more)
- **No commits with failing tests** — all new code must have tests before commit

---

## 6. Shared Repository (`AiRE-DepositModels/`)

**Single source of truth for deposit model weights.** Both CAGE-IN and Bhumi3DMapper read from this repo.  
"It is scientifically indefensible to maintain two divergent weight sets for the same deposit type across these two tools." — Amit Tripathi (Session 3 decision)

**Current state (2026-04-17):**
- `manifest.json` v1.0, `repo_version phase2-2026-04-17`
- 3 brainstorm-complete models: `laterite_ni` (23 weights), `ni_sulphide` (26 weights), `orogenic_au` (30 weights)
- `irog` superseded by `orogenic_au`
- 8 `pre_brainstorm_scaffold` models (architecture placeholders)
- 1 `not_yet_brainstormed` model (`graphite_flake`)

**Adding a new model:**
1. Run brainstorming session with Dr. Prithvi (geological peer review)
2. Add JSON to `AiRE-DepositModels/models/` with all required fields + citations
3. Register in `manifest.json` with `review_status: "brainstorm_complete_vX"`
4. Run CI gate — `test_all_brainstorm_complete_models_documented` will fail if BRIDGE_TABLE is incomplete
5. Add missing BRIDGE_TABLE entries (NATIVE, PARTIAL, or MISSING — all must be documented)
6. Get Dr. Prithvi sign-off on any PARTIAL bridges before setting `prithvi_approved=True`

---

## 7. Pending Items (update as completed)

### BH-REM-P1 completion sprint gaps (as of 2026-04-17)
- [x] Gap 1: BRIDGE_TABLE laterite_ni + ni_sulphide coverage (22 new entries)
- [x] Gap 2: depth_extent Option A wiring in `m13_json_scoring_engine.py`
- [x] Gap 3: `ui/model_selector.py` — 4-band coverage indicator
- [x] Gap 4: This file (CLAUDE.md) — remove from pending when committed

### Dr. Prithvi pending sign-offs
- [ ] `grav_residual_x_mag_rtp_as` composite PARTIAL (ni_sulphide) — prithvi_approved=False pending geological confirmation that the product is a valid composite proxy
- [ ] `fault_proximity_x_mag_rtp_as` composite PARTIAL (ni_sulphide) — same pending

### CAGE-IN integration
- [ ] File CAGE-IN ticket `JC-TBD-EVIDENCESTACK-EXPORT` — API for exporting CAGE-IN evidence layers (emit_carbonate, geochem_pathfinder, fault_intersection_density etc.) to Bhumi Engine 2 input format
- [ ] Wire `StructuralConfig.corridors_defined()` runtime check in `JsonScoringEngine.score_voxel()` — demote `c6→fault_proximity` to MISSING when no corridors defined (Dr. Prithvi ruling 2 engineering guard)

### Phase 3 (coordinate with CAGE-IN)
- [ ] Extend `EvidenceWeight` dataclass (in `AiRE-DepositModels/python/deposit_model.py`) to carry `depth_extent: Optional[dict]` and `variant_key_3d: Optional[str]` natively. Document in `AiRE-DepositModels/docs/SCHEMA_ROADMAP.md` as Option B.
- [ ] Enable composite PARTIAL bridge computation in `score_voxel()` for `grav_residual_x_mag_rtp_as` and `fault_proximity_x_mag_rtp_as` (currently skipped with synthetic bhumi_key notation)

### Shared repo maintenance
- [ ] Add "Consumer engines" section to `AiRE-DepositModels/README.md` listing CAGE-IN and Bhumi3DMapper as consumers (addendum Amendment 13)
- [ ] Update CAGE-IN memory `project_bhumi3d_integration_state.md` marking BH-REM-P1 complete (after all 4 gaps committed)

---

## 8. Commit Discipline (addendum Amendment 11)

One commit per gap. Do not batch all gaps into a single commit.

```
git commit -m "feat(bridge): add laterite_ni + ni_sulphide BRIDGE_TABLE entries, extend CI gate (BH-REM-P1 Gap 1)"
git commit -m "feat(engine): wire depth_extent Option A + deposit_family to coverage report (BH-REM-P1 Gap 2)"
git commit -m "feat(ui): add model_selector.py with 4-band coverage indicator (BH-REM-P1 Gap 3)"
git commit -m "docs: add CLAUDE.md session instructions (BH-REM-P1 Gap 4)"
```

---

## 9. Session Pre-flight Checklist

Before starting any new Bhumi development session:

1. `git status` — confirm on `main`, commit `6ee63f5` or later, no uncommitted changes
2. `python -m pytest bhumi3dmapper/test/ -q` — confirm all tests pass (263+ at BH-REM-P1 close)
3. Confirm shared repo accessible: `python -c "from bhumi3dmapper.core.shared_repo_loader import get_repo_root; print(get_repo_root())"`
4. Read pending items section above — check if any Dr. Prithvi sign-offs arrived

---

*This file is the session-start canonical reference. When in doubt, check here first.*  
*Do not derive architecture decisions from code comments alone — the comments may lag the decisions recorded here.*
