# Bhumi3DMapper v2.0 Development Plan

> **Objective:** Mineral Discovery is the Primary Objective  
> **Lead:** Satya  
> **Date:** 2026-04-17  
> **Status:** Draft for Team Review  
> **Review required by:** Full AiRE Team

---

## Executive Summary

Bhumi3DMapper v1.0.0 is a working QGIS plugin with 53 passing tests, covering the full pipeline from data loading to scored GeoPackage output. However, the code review reveals **4 critical issues** that directly compromise mineral discovery accuracy, **6 high-priority issues** that limit the tool to Kayad-only use, and several medium-priority improvements needed for production readiness.

**The biggest risk to mineral discovery:** The scoring engine and drill processor contain Kayad-specific hardcoded values throughout. Any user running this on a different deposit will get silently wrong results. The drill hole desurvey is missing entirely, meaning all subsurface geology is vertically projected from collar -- potentially hundreds of meters off at depth.

---

## Current State Assessment

| Area | Status | Verdict |
|------|--------|---------|
| Plugin skeleton & QGIS integration | Complete | Working |
| Config system (JSON roundtrip) | Complete | Good, but defaults are Kayad-specific |
| Scoring engine (13 criteria) | Complete | **Has bugs + hardcoded thresholds** |
| Data loader | Complete | **PIL instead of GDAL; no spatial validation** |
| Drill processor | Complete | **No desurvey; hardcoded rock codes** |
| Geophysics processor | Complete | Minor issues |
| GPKG writer | Complete | Slow; no spatial index |
| Voxel builder | Complete | **Zero tests** |
| UI (dock, config, wizard) | Complete | **Import bugs; blocking UI; incomplete config editing** |
| Test suite (53 tests) | Passing | Significant gaps in regime/assay/voxel coverage |

---

## Phase 1 -- Critical Fixes (Mineral Discovery Accuracy)

These issues directly produce **wrong prospectivity maps**. Must be fixed before any field use.

### JC-1.1: Implement Drill Hole Desurvey
- **File:** `modules/m02_drill_processor.py`
- **Problem:** Survey data is loaded by `m01_data_loader.py` but **never used**. All subsurface positions are computed as `z_collar - from_depth` (vertical projection). For deviated holes, the actual XYZ position depends on azimuth and dip. At 500m depth with 10-degree deviation, geology is assigned ~87m from its true position.
- **Fix:** Implement minimum-curvature desurvey using survey (BHID, DEPTH, AZI, DIP). Compute true XYZ for each interval midpoint. Update `geology_at_level()` to use desurveyed coordinates.
- **Impact:** HIGH -- affects every criterion that depends on spatial position of drill data (C1 lithology, C2 PG halo, C3 CSR standoff, C9 grade model)
- **Effort:** 3-5 days
- **Tests needed:** Desurvey of known vertical hole (identity), 45-degree hole, S-curved hole

### JC-1.2: Fix Gravity Gradient Scoring Dead Code
- **File:** `modules/m04_scoring_engine.py`, `score_gravity_gradient()` 
- **Problem:** The conditions are evaluated in wrong order. The `grav_grad > g80` branch catches everything above the 80th percentile, making the `grav_grad > g90` branch **unreachable dead code**. Cells with very high gradient (above 90th percentile) score 0.55 instead of the intended 0.35.
- **Fix:** Reorder conditions: check g90 before g80, or use `elif` chain from highest to lowest.
- **Impact:** MEDIUM-HIGH -- inflates blind model scores in high-gradient zones, potentially masking true anomalies
- **Effort:** 1 hour
- **Tests needed:** Add test with values above g90 and verify correct score (0.35)

### JC-1.3: Fix Ore Polygon Area Calculation
- **File:** `modules/m01_data_loader.py`, line ~150
- **Problem:** `'area': len(xs) * 25` counts vertices and multiplies by 25 sq.m. This is not a valid area calculation. A polygon with 100 vertices gets area=2500 regardless of its actual shape. This corrupts the ore-envelope equivalent radius used in C10 scoring.
- **Fix:** Implement Shoelace formula: `0.5 * abs(sum(x[i]*y[i+1] - x[i+1]*y[i]))` or use `shapely.Polygon.area`.
- **Impact:** HIGH -- directly affects ore_envelope proximity scoring (C10) and novelty classification
- **Effort:** 2 hours
- **Tests needed:** Known polygon area (rectangle, triangle, irregular)

### JC-1.4: Replace PIL with Rasterio/GDAL for TIF Loading
- **File:** `modules/m01_data_loader.py`
- **Problem:** PIL/Pillow loads TIF pixels but has **no CRS awareness, no geotransform, no nodata handling**. If a gravity TIF has a different origin or pixel size than expected, values are silently assigned to wrong grid cells. There is no validation that the TIF spatial extent matches the project grid.
- **Fix:** Replace `Image.open()` with `rasterio.open()`. Read CRS, transform, and nodata from the file. Validate against `ProjectConfig.grid`. Resample to project grid if needed.
- **Impact:** HIGH -- spatial misregistration of geophysics invalidates C4 (gravity), C5 (magnetics), C7b/C8 (gradients), C9 (Laplacian)
- **Effort:** 2-3 days
- **Tests needed:** TIF with known geotransform; mismatched CRS detection; nodata handling
- **Note:** This adds `rasterio` as a dependency (usually available in QGIS Python)

---

## Phase 2 -- Deposit-Agnostic Generalisation

These issues mean the plugin **only works correctly for Kayad**. Fixing them enables mineral discovery at any deposit.

### JC-2.1: Move All Hardcoded Thresholds to Config
- **Files:** `m04_scoring_engine.py`, `m02_drill_processor.py`, `m05_gpkg_writer.py`
- **Problem:** The following are hardcoded with Kayad-specific values:
  - PG halo distance thresholds (2, 4, 10, 15, 20, 30, 50m)
  - CSR standoff distance thresholds (5, 10, 15, 30, 40, 60, 100m)
  - Gravity absolute thresholds (mGal values, depth boundaries at z=160/310)
  - Magnetic absolute thresholds (uSI values)
  - Plunge proximity distances (75, 150, 300, 600m)
  - Structural/footwall rock codes (hardcoded 3 and 4 in drill processor)
  - Litho score tables per regime
  - Litho/regime/class name dicts in GPKG writer
- **Fix:** Add `ScoringThresholds` dataclass to `core/config.py` with all threshold arrays. Pass through to scoring functions. Kayad values become the default preset.
- **Impact:** HIGH -- without this, any non-Kayad project gets meaningless scores
- **Effort:** 3-4 days
- **Tests needed:** Scoring with non-default thresholds; config roundtrip with custom thresholds

### JC-2.2: Config Preset System (Deposit Templates)
- **File:** `core/config.py` (new: `core/presets/`)
- **Problem:** Setting up a new deposit requires knowing all threshold values, weight tuning, rock codes, corridor definitions, and depth regime boundaries. This is expert-only.
- **Fix:** Create preset configs for common deposit types:
  - **SEDEX Pb-Zn** (current Kayad model)
  - **VMS Cu-Zn** (replace PG halo with footwall alteration pipe, add chargeability)
  - **Epithermal Au** (fault-zone proximity instead of corridor, resistivity high)
  - **Porphyry Cu-Mo** (concentric ring model around intrusive, IP chargeability)
- **Impact:** HIGH -- makes the tool usable for the deposits that matter most for discovery
- **Effort:** 5-7 days (requires geological input per deposit type)
- **Tests needed:** Each preset loads, validates, and produces scores in [0,100]

### JC-2.3: Complete Config Widget for All Geological Parameters
- **File:** `ui/config_widget.py`
- **Problem:** The UI only exposes project name, CRS, drill paths, geophysics paths, grid dimensions, and output folder. **Missing from UI:** scoring weights, lithology codes, structural corridors, depth regime boundaries, threshold arrays, deposit type selector. Users must hand-edit JSON for the most important parameters.
- **Fix:** Add tabbed config editor:
  - Tab 1: Project & Grid (existing)
  - Tab 2: Deposit Type & Lithology Codes
  - Tab 3: Scoring Weights (with graphical sliders)
  - Tab 4: Structural Corridors (with map picker)
  - Tab 5: Depth Regimes
- **Impact:** MEDIUM-HIGH -- without this, only expert users can configure for new deposits
- **Effort:** 5-7 days

### JC-2.4: Fix Import Bugs in UI Files
- **Files:** `ui/dock_panel.py` (lines 141, 156, 207), `ui/wizard.py` (lines 83-88, 122-125, 136-139, 224-227)
- **Problem:** `dock_panel.py` uses `from .core.config import ProjectConfig` which resolves to `ui/core/config` (doesn't exist). `wizard.py` uses `sys.path` hacking. Both will crash at runtime.
- **Fix:** Change to `from ..core.config import ProjectConfig` in both files.
- **Impact:** HIGH -- plugin UI crashes on use
- **Effort:** 1 hour
- **Tests needed:** Import smoke test

---

## Phase 3 -- Production Hardening

### JC-3.1: Non-blocking UI with QgsTask
- **Files:** `ui/wizard.py`, `ui/dock_panel.py`, `algorithms/alg_run_scoring.py`
- **Problem:** All scoring runs synchronously on the UI thread. For 145 z-levels at 348K cells each, QGIS freezes for potentially hours with no cancel option.
- **Fix:** Wrap computation in `QgsTask` subclass. Show progress bar with per-level updates. Support cancellation via `feedback.isCanceled()`.
- **Effort:** 3-4 days

### JC-3.2: GPKG Performance -- Batch Writing + Spatial Index
- **File:** `modules/m05_gpkg_writer.py`
- **Problem:** Row-by-row Python loop with float conversions. No spatial index. Very slow for 348K+ cells per level.
- **Fix:** Vectorise with numpy for data preparation, use `executemany()` for bulk insert, add RTree spatial index after write.
- **Effort:** 2-3 days

### JC-3.3: Deduplicate Scoring Pipeline
- **Files:** `algorithms/alg_run_scoring.py`, `modules/m06_voxel_builder.py`
- **Problem:** The per-level computation logic is duplicated between these two files. Bug fixes must be applied in both places.
- **Fix:** Extract shared `compute_level()` function in a shared module. Both files call it.
- **Effort:** 1-2 days

### JC-3.4: Proper Nodata Handling and Warning System
- **Files:** `m01_data_loader.py`, `m03_geophys_processor.py`
- **Problem:** Global `warnings.filterwarnings('ignore')` suppresses all warnings. Nodata detection assumes negative values. NaN propagation is undocumented.
- **Fix:** Remove global warning suppression. Use `np.nan` consistently for missing data. Add data quality report after loading (% coverage per input).
- **Effort:** 2 days

### JC-3.5: Fix Config z_levels Float Boundary Issue
- **File:** `core/config.py`
- **Problem:** `np.arange(z_bot, z_top + dz, dz)` has well-known float accumulation issues. The endpoint may or may not be included.
- **Fix:** Use `np.linspace(z_bot, z_top, num_levels)` or compute integer steps and scale.
- **Effort:** 1 hour

---

## Phase 4 -- Test Coverage for Discovery Confidence

### JC-4.1: Add Regime Transition Tests
- **Files:** `test/test_scoring.py`, `test/test_integration.py`
- **Problem:** Only regime 2 (upper mine) is tested. Regime 0 (deep) and regime 1 (transition with 30% confidence discount) have zero coverage. The transition regime is where geological uncertainty is highest and scoring errors most impactful.
- **Effort:** 2-3 days

### JC-4.2: Add Voxel Builder Tests
- **File:** `test/test_voxel.py` (new)
- **Problem:** `m06_voxel_builder.py` has zero tests. The 3D assembly that combines all levels is completely unverified.
- **Effort:** 2-3 days

### JC-4.3: Fix _classify_rock_code Phantom Test
- **File:** `test/test_data_loader.py`
- **Problem:** `test_empty_litho_rock_code_defaults_to_zero` calls `loader._classify_rock_code()` which doesn't exist as a method. Either add the method or rewrite the test to use the actual classification path.
- **Effort:** 1 hour

### JC-4.4: Add Golden-File Regression Tests
- **File:** `test/test_regression.py` (new)
- **Problem:** No test compares output against a known-good reference. For mineral prospectivity, you need to verify scoring produces the same results as the validated Kayad reference.
- **Fix:** Create a small (20x20, 3 levels) reference dataset with pre-computed expected scores. Assert exact match (within float tolerance).
- **Effort:** 2-3 days

### JC-4.5: Add Boundary Value and NaN Input Tests
- **File:** `test/test_scoring.py`
- **Problem:** No test passes NaN, inf, or zero-length arrays to scoring functions. No tests at exact threshold boundaries (4.0m, 10.0m for PG halo; 10m, 40m for CSR standoff).
- **Effort:** 1-2 days

---

## Phase 5 -- Feature Expansion for Discovery

### JC-5.1: Symbology Files (.qml/.sld)
- Pre-built QGIS style files for prospectivity classification with proper colour ramps (red=VH, orange=H, yellow=M, blue=L, grey=VL)
- **Effort:** 1-2 days

### JC-5.2: Layer Grouping in Results Loading
- **File:** `algorithms/alg_load_results.py`
- Group levels in QGIS layer tree. For 145 levels, flat listing is unmanageable.
- **Effort:** 1 day

### JC-5.3: 3D Layered Mesh (UGRID/MDAL) Export
- Alternative to .npz voxel that loads natively in QGIS 3D viewer
- **Effort:** 5-7 days (research + implementation)

### JC-5.4: QGIS 4.0 (Qt6) Full Port Test
- Run `pyqt5_to_pyqt6.py` migration script
- Test on QGIS 4.0 Norrkoping
- **Effort:** 2-3 days

### JC-5.5: Plugin Repository Submission
- Professional icon design
- Help documentation
- QGIS Plugin Repository metadata and submission
- **Effort:** 3-5 days

---

## Sprint Schedule (Proposed)

| Sprint | Duration | Job Cards | Focus |
|--------|----------|-----------|-------|
| **S9** | 1 week | JC-1.2, JC-1.3, JC-2.4, JC-3.5, JC-4.3 | Quick critical fixes |
| **S10** | 2 weeks | JC-1.1, JC-1.4 | Desurvey + GDAL migration |
| **S11** | 2 weeks | JC-2.1, JC-2.2 | Deposit-agnostic scoring |
| **S12** | 2 weeks | JC-2.3, JC-3.1 | Config UI + async processing |
| **S13** | 1 week | JC-3.2, JC-3.3, JC-3.4 | Performance + cleanup |
| **S14** | 2 weeks | JC-4.1, JC-4.2, JC-4.4, JC-4.5 | Test coverage |
| **S15** | 2 weeks | JC-5.1 - JC-5.5 | Features + release |

**Total estimated: ~12 weeks to production-ready v2.0**

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Rasterio not available in target QGIS Python | Medium | High | Fall back to GDAL bindings (always available in QGIS) |
| Desurvey implementation introduces new bugs | Medium | High | Validate against known drill hole trajectories from Kayad |
| Preset configs for non-SEDEX deposits need geological review | High | High | Engage domain experts per deposit type before release |
| Qt6 migration breaks UI | Low | Medium | Maintain Qt5 as primary target; Qt6 port in parallel branch |
| Performance insufficient for very large grids (>1M cells) | Medium | Medium | Profile and optimise hot paths; consider Cython for scoring engine |

---

## Decision Points for Team Review

1. **Do we fix desurvey (JC-1.1) before any field deployment?** Recommendation: YES -- vertical projection is fundamentally wrong for deviated holes.

2. **Which deposit types to support in v2.0 presets?** Recommendation: SEDEX (done), VMS, Epithermal, Porphyry -- covers 80% of exploration targets.

3. **Rasterio vs GDAL bindings for TIF loading?** Rasterio has a cleaner API but GDAL is guaranteed available in QGIS. Recommendation: Try rasterio with GDAL fallback.

4. **Should we invest in 3D mesh export (JC-5.3) now or defer to v3.0?** Recommendation: Defer -- stacked 2D GPKGs work well and 3D mesh is complex.

5. **Sprint 9 quick fixes -- can we ship an intermediate v1.1.0?** Recommendation: YES -- fixes the crashing UI imports and scoring bug with minimal risk.

---

*This plan to be reviewed by the full team with the lens: "Does every job card serve the primary objective of mineral discovery?"*

*Satya to lead prioritisation and assignment in the team meeting.*
