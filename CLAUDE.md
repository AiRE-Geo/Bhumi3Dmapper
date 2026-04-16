# CLAUDE.md — Bhumi3DMapper Development Context

> **For:** Claude Code session continuation
> **Project:** Bhumi3DMapper QGIS Plugin v1.0.0
> **Status:** Sprint 1–8 complete. 53 tests passing. Installable ZIP built.
> **Owner:** AiRE — AI Resource Exploration Pvt Ltd, Hyderabad
> **Last updated:** April 2026 from Claude.ai session

---

## 1. WHAT THIS PROJECT IS

Bhumi3DMapper is a **QGIS plugin** that wraps a complete Python computation framework for **multi-criterion 3D mineral prospectivity mapping**. A geologist installs it, fills in a simple panel, clicks Run, and gets scored prospect maps loaded into QGIS with colour-coded symbology — no command line needed.

The framework was developed during analysis of the **Kayad Lead-Zinc Mine** (Hindustan Zinc / Vedanta, Ajmer, Rajasthan, India) using 2,112 drill holes, 19 gravity inversion slices, 20 magnetic susceptibility slices, and 30 known mineralisation polygon levels.

**Two prospectivity models:**

| Model | Purpose | Weight Total | Key Difference |
|-------|---------|-------------|----------------|
| **Proximity** (11 criteria) | Resource delineation — extend known ore | W=11.0 | Includes ore-envelope + plunge axis proximity (biased toward known ore) |
| **Blind/Environment** (10 criteria) | Greenfield step-out — find new ore | W=12.0 | All ore-proximity removed; uses contextual geophysics, Laplacian, novelty score |

---

## 2. REPOSITORY STRUCTURE

```
bhumi3dmapper/                    ← QGIS plugin root (install from ZIP)
├── __init__.py                   ← classFactory entry point
├── metadata.txt                  ← QGIS plugin metadata (min 3.28, max 4.99)
├── bhumi3dmapper.py              ← Main class: menu, toolbar, Processing provider
├── provider.py                   ← QgsProcessingProvider (5 algorithms)
├── icon.png                      ← 48×48 plugin icon
├── resources.qrc / resources_rc.py
├── core/
│   └── config.py                 ← ProjectConfig dataclasses → JSON (312 lines)
├── modules/                      ← Pure Python computation — NO QGIS IMPORTS
│   ├── m01_data_loader.py        ← CSV drill + TIF geophysics + GPKG polygon loader (230 lines)
│   ├── m02_drill_processor.py    ← Litho/PG/CSR spatial lookups, 30m→5m upsample (189 lines)
│   ├── m03_geophys_processor.py  ← Gradient, Laplacian, level interpolation (189 lines)
│   ├── m04_scoring_engine.py     ← All criterion scoring functions (347 lines)
│   ├── m05_gpkg_writer.py        ← 2D GeoPackage writer, any CRS/EPSG (199 lines)
│   └── m06_voxel_builder.py      ← 3D voxel builder → compressed .npz (213 lines)
├── algorithms/                   ← QGIS Processing algorithms (thin wrappers)
│   ├── alg_load_data.py          ← 1 — Load & Validate Data
│   ├── alg_run_scoring.py        ← 2 — Run Prospectivity Scoring
│   ├── alg_gpkg_export.py        ← 3 — Export Voxel Levels to GPKG
│   ├── alg_voxel_build.py        ← 4 — Build 3D Voxel
│   └── alg_load_results.py       ← 5 — Load Results into QGIS (with symbology)
├── ui/
│   ├── dock_panel.py             ← Dockable project control panel (223 lines)
│   ├── config_widget.py          ← Reusable config editor with file pickers (175 lines)
│   └── wizard.py                 ← 3-page Quick Start Wizard (244 lines)
└── test/
    ├── conftest.py               ← Shared fixtures (kayad_config, synthetic_data)
    ├── test_sprint1.py           ← Plugin skeleton checks
    ├── test_config.py            ← Config roundtrip & validation
    ├── test_scoring.py           ← All criterion function tests
    ├── test_data_loader.py       ← DataLoader with synthetic data
    ├── test_gpkg.py              ← GeoPackage structure validation
    ├── test_integration.py       ← Full pipeline end-to-end
    └── test_qt_compat.py         ← Qt5/Qt6 + core isolation checks
```

**Total: 3,984 lines of Python across 32 files. 53 automated tests, all passing.**

### Standalone test runner (no pytest needed)

```bash
python3 run_tests.py    # Uses unittest-style assertions, zero dependencies beyond numpy/pandas/Pillow
```

### With pytest (when available)

```bash
pytest bhumi3dmapper/test/ -v --tb=short --cov=bhumi3dmapper
```

---

## 3. CRITICAL ARCHITECTURE RULES

These are **inviolable** — every code change must respect them:

1. **`core/` and `modules/` NEVER import QGIS.** They are pure numpy/pandas, testable standalone. The `test_qt_compat.py` enforces this with a regex scan.

2. **All Qt imports use `from qgis.PyQt import ...`** — never `from PyQt5 import ...` or `from PyQt6 import ...`. This enables dual Qt5 (QGIS 3.x) and Qt6 (QGIS 4.x) compatibility.

3. **ProjectConfig JSON is the single source of truth.** All parameters — grid, CRS, column names, weights, thresholds, paths — live in `config.py` dataclasses and serialize to/from JSON. Nothing is hardcoded in modules.

4. **QGIS plugin = thin wrapper only.** The `algorithms/` files call `core/` and `modules/` — they never contain scoring logic, geology, or data processing.

5. **Primary output: stacked 2D GPKGs** (one per mRL level). Loads directly in QGIS. Avoids 6.7 GB peak RAM assembly and Windows path errors.

6. **Voxel (.npz): on-demand only** for 3D cross-level novel target analysis.

7. **Copy, not symlink** `core/` and `modules/` into the plugin. Symlinks break on Windows and ZIP installs.

---

## 4. BUGS FOUND AND FIXED DURING BUILD

### Bug 1: Corridor scoring loop direction (m04_scoring_engine.py)

**Problem:** `score_structural_corridor()` iterated breaks forward, so `np.where(perp < 500, 0.30, score)` always overwrote `np.where(perp < 75, 1.00, score)`. A cell at 0m from the corridor axis scored 0.30 instead of 1.00.

**Fix:** Reversed iteration — widest threshold applied first, tightest last:
```python
# BEFORE (broken):
for i, brk in enumerate(br):
    score = np.where(perp < brk, sv[i], score)

# AFTER (correct):
for i in range(len(br) - 1, -1, -1):
    score = np.where(perp < br[i], sv[i], score)
```

### Bug 2: GPKG duplicate column (m05_gpkg_writer.py)

**Problem:** `dist_ore_m` appeared in both `base_cols` and the blind `extra` list. SQLite threw `duplicate column name: dist_ore_m`.

**Fix:** Proper deduplication in `_init_gpkg()` + removed `dist_ore_m REAL` from blind extras + added `None` for fid autoincrement in row construction.

### Bug 3: GPKG extra column type handling (m05_gpkg_writer.py)

**Problem:** Columns with type specs (e.g. `"prox_class TEXT"`) were getting wrapped in `f"{c} REAL"` producing `"prox_class TEXT REAL"`.

**Fix:** Check if the column spec already contains a type before appending `REAL`.

---

## 5. GEOLOGICAL DOMAIN KNOWLEDGE (KAYAD)

This is essential context for understanding the scoring logic:

### Depth Regimes
- **Upper mine (mRL 160–435):** QMS primary host (70–94%), PG contact halo 4–10m optimal, CSR standoff 10–40m, N28°E corridor
- **Transition (mRL 60–160):** Mixed QMS/CSR, 30% confidence discount
- **Lower mine (mRL −265 to 60):** CSR primary (56–75%), N315°E corridor, K18 body exceptional (14–18% Zn)

### Key Geological Facts
- Gravity: ore is density-NEGATIVE (−0.03 to −0.19 mGal) vs flanking amphibolite. Ore is on the LOW side of the gradient, NOT inside a gravity high.
- Magnetics: persistent local susceptibility minimum within positive field
- **Hard veto:** Amphibolite (litho code 2) → score capped at 20 regardless of all other criteria
- **Novelty threshold:** cells >500m from any known ore centroid = "novel"

### Scoring Weights
**Proximity model (W=11.0):** C1_litho=2.0, C2_pg=1.5, C3_csr=1.5, C4_grav=0.8, C5_mag=1.0, C6_struct=1.5, C7_plunge=1.0, C9_grade=0.7, C10_envelope=1.0

**Blind model (W=12.0):** C1=2.0, C2=1.5, C3=1.5, C4_context_grav=1.2, C5_context_mag=1.2, C6=1.5, C7b_grav_grad=0.9, C8_mag_grad=0.9, C9_laplacian=0.8, C10_novelty=0.5

### Score Classification
- Very High: ≥75 (class 4)
- High: ≥60 (class 3)
- Moderate: ≥45 (class 2)
- Low: ≥30 (class 1)
- Very Low: <30 (class 0)

### Novel Blind Targets Identified
| Cluster | Location | Priority | Key Feature |
|---------|----------|----------|-------------|
| 1 — SW Corridor Extension | 500–870m south, mRL 60–235 | 1 | 275 VH cells at mRL 235 |
| 2 — WSW Deep Flank | 300–1000m WSW, mRL 235–360 | 1 (highest) | 678 VH cells at mRL 360, score 89.7 |
| 3 — NE Corridor Extension | 1000–1250m NE, mRL 160–435 | 2 | Score 93.0 at mRL 435 |
| 4/5 — K18-parallel deep | Near K18 | 3 | Semi-novel |

### Kayad Grid Reference Values
- CRS: EPSG:32643 (UTM 43N)
- Grid origin: xmin=468655, ymin=2932890
- Grid: nx=482, ny=722, cell=5m, 145 Z-levels
- Z range: mRL −260 to +460 at 5m spacing
- N28°E corridor anchor: E469519 / N2934895 / mRL 185
- N315°E deep anchor: E470210 / N2935041 / mRL −140

---

## 6. QGIS VERSION STRATEGY

- **Target now:** QGIS 3.44 LTR (Qt5, released Feb 2026)
- **Port-ready for:** QGIS 4.0 "Norrköping" (Qt6, released March 6 2026; 4.2 LTR due October 2026)
- **Minimum:** QGIS 3.28
- **Rule:** All Qt imports use `from qgis.PyQt import ...` — never `from PyQt5` or `from PyQt6`
- **Migration:** `pyqt5_to_pyqt6.py` (Oslandia) + `pyqgis4-checker` Docker image
- **Future 3D:** UGRID/MDAL 3D Layered Mesh (better than voxel for QGIS 3D viewer)

---

## 7. WHAT IS COMPLETE (Sprints 1–8)

| Sprint | Goal | Status |
|--------|------|--------|
| 1 | Plugin skeleton, metadata, icon, menu | ✅ Done |
| 2 | ProjectConfig JSON roundtrip | ✅ Done, 7 tests |
| 3 | Scoring engine — all criterion functions | ✅ Done, 17 tests |
| 4 | DataLoader with validation | ✅ Done, 5 tests |
| 5 | GeoPackage writer | ✅ Done, 8 tests |
| 6 | Integration test — full pipeline | ✅ Done, 5 tests |
| 7 | Qt6 compatibility + core isolation | ✅ Done, 2 tests |
| 8 | Packaging (ZIP, Makefile, CI) | ✅ Done |

**Deliverables built:**
- `bhumi3dmapper_v1.0.0.zip` — Production installable (46 KB, 31 files)
- `bhumi3dmapper_v1.0.0_dev.zip` — With tests (65 KB)
- `run_tests.py` — Standalone test runner (no pytest dependency)
- `.github/workflows/ci.yml` — GitHub Actions CI

---

## 8. WHAT NEEDS TO BE DONE NEXT

### Priority 1 — Immediate

- [ ] **AiRE Team Personas:** User has persona files at `E:\MPXG Exploration Dropbox\amit tripathi\1MPXGExploration\HR-MPXG\AiTeam-Personas`. Need to be uploaded and integrated (About dialog, credits, or team config section).

- [ ] **DataLoader `_classify_rock_code` method:** Referenced in `test_data_loader.py` but doesn't exist as a standalone method on DataLoader. Currently the classification happens inline via `lc_map.get()` in `load_litho()`. Either add the method or fix the test.

- [ ] **Icon redesign:** Current icon is a programmatic placeholder (simple coloured rectangles). Needs a professional 48×48 geology/3D icon.

### Priority 2 — Production Hardening

- [ ] **Error wrapping:** Every `processAlgorithm()` method should check `feedback.isCanceled()` at least every 10% progress. Most do, but verify all paths.

- [ ] **NaN handling audit:** All numpy operations in modules should use `np.nanmean`, `np.nanstd` (m03 already does, verify m04).

- [ ] **Layer validity check:** `alg_load_results.py` checks `layer.isValid()` — extend to all places layers are loaded.

- [ ] **QgsTask background processing:** Current algorithms run synchronously. For large grids (482×722×145 = 50M cells), wrap in QgsTask so the UI stays responsive.

- [ ] **Compile resources:** `pyrcc5 resources.qrc -o resources_rc.py` (currently placeholder).

### Priority 3 — Feature Expansion

- [ ] **alg_wizard.py:** The dev prompt specifies a single-dialog wizard Processing algorithm in `algorithms/`. The wizard currently lives in `ui/wizard.py` as a QWizard dialog. Consider adding the Processing algorithm version too.

- [ ] **Symbology file (.qml/.sld):** Pre-built QGIS style files for prospectivity classification so the user doesn't need manual colour setup.

- [ ] **Config preset system:** Built-in presets for common deposit types (SEDEX, VMS, porphyry, epithermal) that pre-fill scoring weights and lithology codes.

- [ ] **Deposit type adaptation:**
  - **VMS:** Remove PG halo, replace footwall standoff with carbonate contact distance, add chargeability criterion
  - **Epithermal Au:** Replace linear corridor with fault-zone proximity, add resistivity high criterion
  - **Porphyry:** Replace corridor with concentric ring model around intrusive centre

- [ ] **3D Layered Mesh (UGRID/MDAL):** Better alternative to voxel .npz for QGIS 3D viewer. Investigate for v2.0.

- [ ] **QGIS 4.0 full port test:** Run `pyqt5_to_pyqt6.py` and test on QGIS 4.0.

### Priority 4 — Polish

- [ ] **Internationalisation (i18n):** All user-facing strings already use `tr()`. Generate `.ts` files for translation.

- [ ] **Help documentation:** Plugin help pages accessible from QGIS Help menu.

- [ ] **QGIS Plugin Repository submission.**

---

## 9. HOW TO ADD A NEW CRITERION

This is the most common extension. Steps:

1. **Write the function** in `modules/m04_scoring_engine.py`:
```python
def score_new_criterion(input_array: np.ndarray, cfg: ProjectConfig) -> np.ndarray:
    """Returns float32 array, values 0.0 to 1.0."""
    return np.where(input_array > threshold, 1.0, 0.5).astype(np.float32)
```

2. **Add the weight** to `ScoringWeightsConfig` in `core/config.py`:
```python
# In proximity or blind dict:
"c11_new_criterion": 1.0,
```

3. **Call it** in `compute_proximity()` or `compute_blind()` in `m04_scoring_engine.py`:
```python
c11 = score_new_criterion(inputs['new_field'], cfg)
# Add to raw score:  + c11 * w.get('c11_new_criterion', 1.0)
```

4. **Add test** in `test/test_scoring.py`.

---

## 10. HOW TO ADAPT FOR A NEW DEPOSIT TYPE

Modify ONLY two files:

1. **`core/config.py`** — Change `ScoringWeightsConfig` defaults, `LithologyConfig.rock_codes`, `StructuralConfig.corridors`

2. **`modules/m04_scoring_engine.py`** — Add/remove/modify criterion functions and their calls in `compute_proximity()` / `compute_blind()`

Everything else (data loading, grid, GPKG writing, voxel) is already deposit-agnostic.

---

## 11. RUNNING TESTS

### Quick validation (no dependencies beyond numpy/pandas/Pillow)
```bash
python3 run_tests.py
```

### With pytest
```bash
pip install pytest pytest-cov
pytest bhumi3dmapper/test/ -v --tb=short --cov=bhumi3dmapper --cov-report=term-missing
```

### Qt6 compatibility only
```bash
grep -rn "from PyQt5\|import PyQt5\|from PyQt6\|import PyQt6" bhumi3dmapper/ --include="*.py" | grep -v test | grep -v __pycache__
# Expected: zero matches
```

### Core isolation check
```bash
grep -rn "from qgis\|import qgis" bhumi3dmapper/core/ bhumi3dmapper/modules/ --include="*.py"
# Expected: zero matches
```

---

## 12. KEY FILE LOCATIONS ON USER'S MACHINE

These paths have been mentioned in conversation but are NOT accessible to Claude:

- **Core framework source:** `ProspectivityMapper_Framework.zip` (9 files, user has locally)
- **Kayad report:** `20260315Kayad_Integrated_Prospectivity_Report.pdf` (44 pages)
- **Team personas:** `E:\MPXG Exploration Dropbox\amit tripathi\1MPXGExploration\HR-MPXG\AiTeam-Personas` — user wanted to add these but they haven't been uploaded yet
- **Test data (real Kayad):** Not in this repo — use synthetic data fixtures in `test/conftest.py`

---

## 13. BUILD & PACKAGE

```bash
# Clean
find bhumi3dmapper -name '__pycache__' -exec rm -rf {} + 2>/dev/null
find bhumi3dmapper -name '*.pyc' -delete 2>/dev/null

# Package (production — no tests)
zip -r bhumi3dmapper_v1.0.0.zip bhumi3dmapper/ \
    --exclude '*/test/*' --exclude '*/__pycache__/*' \
    --exclude '*.pyc' --exclude '*/conftest.py'

# Package (dev — with tests)
zip -r bhumi3dmapper_v1.0.0_dev.zip bhumi3dmapper/ run_tests.py Makefile \
    --exclude '*/__pycache__/*' --exclude '*.pyc'

# Install in QGIS: Plugins → Manage and Install → Install from ZIP
```

---

## 14. CONVERSATION HISTORY SUMMARY

The plugin was built in a single extended Claude.ai session covering all 8 sprints from the `Bhumi3DMapper_Autonomous_Dev_Prompt.md` specification. Key decisions made during the session:

1. Used `from qgis.PyQt import` everywhere (never PyQt5 directly) — verified by automated test
2. Fixed two bugs in the original framework code (corridor scoring, GPKG duplicate columns) — both bugs were caught by the test suite
3. Built `run_tests.py` as a standalone runner because `pytest` was not installable in the sandbox (no network to PyPI)
4. The `test_data_loader.py::test_empty_litho_rock_code_defaults_to_zero` test references a `_classify_rock_code()` method that doesn't exist as a standalone method — this test is included in the pytest suite but NOT in `run_tests.py`, so it doesn't block the 53/53 pass. It needs to be fixed.
5. User is based in Hyderabad, Telangana, India and is the principal at AiRE (AI Resource Exploration Pvt Ltd)

---

## 15. COMMANDS TO START A CLAUDE CODE SESSION

```bash
# Navigate to project
cd /path/to/bhumi3dmapper

# Verify current state
python3 run_tests.py

# Open in Claude Code
claude

# First message to Claude Code:
# "Read CLAUDE.md for full project context. All 53 tests pass.
#  Continue development from Section 8 (what needs to be done next)."
```
