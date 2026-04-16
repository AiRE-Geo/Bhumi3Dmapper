# Bhumi3DMapper v2.0 — Detailed Job Cards

> **Objective:** Mineral Discovery is the Primary Objective  
> **Lead:** Satya  
> **Date:** 2026-04-17  
> **Status:** Draft for Team Review  
> **Quality Gates:** G1 (Hema spec) → G2 (Gandalf QA) → G2.5 (Rose integration) → G3 (Dr. Prithvi geological review) → G4 (Amit acceptance)

---

## Sequencing Rationale

The job cards below are ordered by **dependency chain**, not by phase number. The logic:

1. **Fix imports first** (JC-01) — nothing in the UI works without this. Zero risk, immediate payoff.
2. **Fix the scoring bug** (JC-02) — a one-line fix that changes prospectivity output. Must be fixed before any geological validation.
3. **Fix z_levels float boundary** (JC-03) — affects which levels get processed. Must be correct before any integration testing.
4. **Fix phantom test** (JC-04) — unblocks clean test suite. All subsequent JCs need a green baseline.
5. **Fix polygon area** (JC-05) — corrects ore envelope scoring (C10) and novelty. Precondition for regression tests.
6. **Replace PIL with GDAL** (JC-06) — corrects spatial registration of geophysics. All geophysics-dependent criteria (C4, C5, C7b, C8, C9) are wrong until this is done. Must precede desurvey because desurvey validation needs correct geophysics.
7. **Implement desurvey** (JC-07) — corrects spatial position of all drill-derived criteria (C1, C2, C3, C9). Largest single change. Must follow GDAL migration (JC-06) so test data uses proper geotransform.
8. **Move hardcoded thresholds to config** (JC-08) — depends on JC-02 (scoring bug fixed) and JC-07 (desurvey working). Refactors every scoring function signature.
9. **Deduplicate scoring pipeline** (JC-09) — depends on JC-08 (scoring functions have final signatures). Extracts shared `compute_level()`.
10. **Add regime transition tests** (JC-10) — depends on JC-08 (thresholds in config) and JC-09 (single scoring path). Tests regime 0 and 1.
11. **Add voxel builder tests** (JC-11) — depends on JC-09 (shared compute_level). Tests the 3D assembly.
12. **Add golden-file regression tests** (JC-12) — depends on JC-05 through JC-08 (all scoring corrections). Creates the reference baseline.
13. **Add boundary/NaN tests** (JC-13) — depends on JC-08 (final scoring signatures).
14. **Nodata handling cleanup** (JC-14) — depends on JC-06 (GDAL) and JC-13 (NaN tests exist to verify).
15. **GPKG performance** (JC-15) — depends on JC-09 (shared compute_level) and JC-14 (nodata clean). Independent of scoring logic.
16. **Non-blocking UI** (JC-16) — depends on JC-01 (imports fixed) and JC-09 (single scoring path).
17. **Config preset system** (JC-17) — depends on JC-08 (all thresholds in config).
18. **Complete config widget** (JC-18) — depends on JC-17 (presets exist to populate UI).
19. **Symbology files** (JC-19) — independent, but best done after JC-12 (regression tests confirm score ranges).
20. **Layer grouping** (JC-20) — independent UI improvement.
21. **QGIS 4.0 port test** (JC-21) — depends on JC-01 (imports fixed) and JC-16 (UI async). End-of-cycle.
22. **Plugin repository submission** (JC-22) — final job. Depends on everything.

---

## Sprint 9 — Foundation Fixes (Week 1)

### JC-01: Fix Import Bugs in UI Files

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2)  
**Effort:** 1 hour  
**Priority:** CRITICAL — plugin crashes on use

**Problem:**  
`ui/dock_panel.py` uses `from .core.config import ProjectConfig` at lines 141, 156, 207. The `.core` resolves to `ui/core/` which does not exist. Correct path is `..core.config` (two dots — up from `ui/` to package root, then into `core/`).

`ui/wizard.py` uses `sys.path.insert(0, plugin_dir)` + `from core.config import ProjectConfig` at four locations (lines 83–86, 120–124, 135–138, 223–226). This pollutes `sys.path` and can import the wrong module.

**Acceptance Criteria:**
1. In `ui/dock_panel.py`, replace all 3 occurrences of `from .core.config import ProjectConfig` with `from ..core.config import ProjectConfig`
2. In `ui/wizard.py`, replace all 4 `sys.path` + bare import blocks with `from ..core.config import ProjectConfig`
3. Remove unused imports:
   - `dock_panel.py` line 4: `import traceback` (unused)
   - `dock_panel.py` line 13: `QgsApplication, Qgis` (unused)
   - `wizard.py` line 11: `QFont` (unused)
   - `wizard.py` lines 7–8: `QGroupBox, QFormLayout` (unused)
   - `config_widget.py` lines 3–4: `os, json` (unused)
   - `config_widget.py` line 11: `Qt` (unused)
4. Fix same `sys.path` hacking in modules (non-QGIS files):
   - `m05_gpkg_writer.py` lines 11–14
   - `m06_voxel_builder.py` lines 12–22
   - `m03_geophys_processor.py` lines 18–21
   - `m04_scoring_engine.py` lines 16–19
   - `m02_drill_processor.py` lines 18–23
   - `m01_data_loader.py` lines 15–18
   
   Each should use: `from .core.config import ...` or `from ..core.config import ...` depending on package structure. For standalone `if __name__ == '__main__'` blocks, keep the `sys.path` fallback but only inside the `__main__` guard.
5. All 53 existing tests still pass after changes
6. `grep -rn "from .core.config\|sys.path.insert" bhumi3dmapper/ --include="*.py" | grep -v __main__ | grep -v test` returns zero matches outside `__main__` guards

**Files changed:**
- `ui/dock_panel.py` — lines 4, 13, 141, 156, 207
- `ui/wizard.py` — lines 7–8, 11, 83–86, 120–124, 135–138, 223–226
- `ui/config_widget.py` — lines 3, 4, 11
- `modules/m01_data_loader.py` — lines 15–18
- `modules/m02_drill_processor.py` — lines 18–23
- `modules/m03_geophys_processor.py` — lines 18–21
- `modules/m04_scoring_engine.py` — lines 16–19
- `modules/m05_gpkg_writer.py` — lines 11–14
- `modules/m06_voxel_builder.py` — lines 12–22
- `algorithms/alg_run_scoring.py` — line 14 (remove unused `Qgis` import)

---

### JC-02: Fix Gravity Gradient Scoring Dead Code Branch

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2), Dr. Prithvi (G3 — geological correctness of score values)  
**Effort:** 1 hour  
**Priority:** CRITICAL — produces wrong blind model scores

**Problem:**  
In `m04_scoring_engine.py` lines 179–182, the `np.where` nesting evaluates `grav_grad > g80` (score 0.55) before `grav_grad > g90` (score 0.35). Since g90 > g80, any value above g90 hits the g80 branch first. The 0.35 score for extremely high gradients is **unreachable dead code**. This inflates blind model scores in high-gradient zones.

**Current code (lines 179–182):**
```python
c7b = np.where((grav_grad >= g40) & (grav_grad <= g80), 0.90,
      np.where((grav_grad >= gg_mean) & (grav_grad < g40), 0.70,
      np.where(grav_grad > g80, 0.55,
      np.where(grav_grad > g90, 0.35, 0.25)))).astype(np.float32)
```

**Intended score mapping (Dr. Prithvi to confirm):**
| Condition | Score | Geological meaning |
|-----------|-------|-------------------|
| g40 ≤ grad ≤ g80 | 0.90 | Moderate gradient — highest prospectivity |
| mean ≤ grad < g40 | 0.70 | Low gradient — good |
| g80 < grad ≤ g90 | 0.55 | High gradient — less prospective |
| grad > g90 | 0.35 | Extreme gradient — likely edge of intrusive, low prospect |
| grad < mean | 0.25 | Below average — poor |

**Fix:** Reorder the `np.where` chain so g90 is checked before g80:
```python
c7b = np.where(grav_grad > g90, 0.35,
      np.where(grav_grad > g80, 0.55,
      np.where((grav_grad >= g40) & (grav_grad <= g80), 0.90,
      np.where(grav_grad >= gg_mean, 0.70, 0.25)))).astype(np.float32)
```

**Acceptance Criteria:**
1. Score for `grav_grad = gg_mean + 2.0 * gg_std` (well above g90) returns `0.35`, not `0.55`
2. Score for `grav_grad = gg_mean + 1.0 * gg_std` (between g80 and g90) returns `0.55`
3. Score for `grav_grad = gg_mean + 0.5 * gg_std` (between g40 and g80) returns `0.90`
4. Score for `grav_grad = gg_mean + 0.05 * gg_std` (between mean and g40) returns `0.70`
5. Score for `grav_grad = gg_mean - 0.5 * gg_std` (below mean) returns `0.25`
6. New test `test_gravity_gradient_g90_branch` added to `test_scoring.py`
7. All 53 existing tests still pass (existing `test_gravity_gradient_returns_valid` checks range only)

**Dr. Prithvi review question:** Are the score values (0.90, 0.70, 0.55, 0.35, 0.25) geologically correct for the blind model gravity gradient criterion? The geological reasoning is: moderate gradients indicate the transition from density-negative ore to surrounding rock, which is the most prospective zone. Extreme gradients suggest the edge of a dense intrusive body.

**Files changed:** `modules/m04_scoring_engine.py` lines 179–182, `test/test_scoring.py` (new test)

---

### JC-03: Fix Config z_levels Float Boundary Issue

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2)  
**Effort:** 1 hour  
**Priority:** HIGH — may silently drop the top z-level

**Problem:**  
`core/config.py` line 25 uses `np.arange(z_bot, z_top + dz, dz)`. For `z_bot=-260`, `z_top=460`, `dz=5`, this should produce 145 levels. But `np.arange` has well-documented float accumulation issues — the endpoint `460` may or may not be included depending on float rounding.

**Current code (line 25):**
```python
return np.arange(self.z_bot_mrl, self.z_top_mrl + self.dz_m, self.dz_m)
```

**Fix:**
```python
n = int(round((self.z_top_mrl - self.z_bot_mrl) / self.dz_m)) + 1
return np.linspace(self.z_bot_mrl, self.z_top_mrl, n)
```

**Acceptance Criteria:**
1. `z_levels` for default config returns exactly 145 levels
2. `z_levels[0] == -260.0` and `z_levels[-1] == 460.0` (exact)
3. All level spacings are exactly 5.0m (within float64 precision)
4. Non-standard configs (e.g., z_bot=0, z_top=100, dz=7) produce correct results — levels 0, 7, 14, ..., 98 (15 levels, not 16)
5. Existing `test_config.py::test_z_levels_step_consistent` still passes

**Files changed:** `core/config.py` line 25

**Note:** The non-evenly-divisible case (dz doesn't divide the range) needs a decision. Current `np.arange` would produce partial steps. `np.linspace` would space evenly but change the dz. Recommendation: use `np.arange` with integer-round step count and assert divisibility, or warn if not evenly divisible.

---

### JC-04: Fix _classify_rock_code Phantom Test

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2)  
**Effort:** 1 hour  
**Priority:** MEDIUM — test suite has a known failure path

**Problem:**  
`test/test_data_loader.py` line 67 calls `loader._classify_rock_code('UNKNOWN_ROCK')`. This method does not exist on `DataLoader`. Classification happens inline in `load_litho()` via `lc_map.get(code, 0)` using the `rock_codes` dict from config.

**Options:**
- **Option A (preferred):** Add `_classify_rock_code(self, code: str) -> int` method to `DataLoader` that wraps `self.cfg.lithology.rock_codes.get(code.upper(), 0)`. Then the test is valid.
- **Option B:** Rewrite the test to call `cfg.lithology.rock_codes.get('UNKNOWN_ROCK', 0)` directly, testing the config lookup. Simpler but less encapsulated.

**Acceptance Criteria:**
1. `test_empty_litho_rock_code_defaults_to_zero` passes
2. Unknown rock codes return `0`
3. Known rock codes return correct values: `'QMS' → 1`, `'AM' → 2`, `'PG' → 3`, `'CSR' → 4`
4. Case-insensitive: `'qms'` → `1`
5. Full test suite (53 tests + this fix = 54) passes

**Files changed:** `modules/m01_data_loader.py` (add method), `test/test_data_loader.py` line 67 (verify test now passes)

---

## Sprint 10 — Spatial Accuracy (Weeks 2–3)

### JC-05: Fix Ore Polygon Area Calculation

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2), Dr. Prithvi (G3 — ore envelope implications)  
**Effort:** 3 hours  
**Priority:** CRITICAL — corrupts ore envelope scoring (C10)  
**Depends on:** JC-01 (imports fixed)

**Problem:**  
`m01_data_loader.py` line 150: `'area': len(xs) * 25`. This counts polygon vertices and multiplies by 25 (assuming 5×5m cells). A polygon with 100 vertices gets area=2500 regardless of actual shape. This flows into `score_ore_envelope()` (`m04` line 225) which computes `r_eq = sqrt(ore_area / pi)` — the equivalent radius is wrong, so the distance-to-radius ratio used for scoring is wrong.

**Fix:** Implement the Shoelace formula:
```python
def _polygon_area(xs, ys):
    """Shoelace formula for polygon area from coordinate arrays."""
    xs = np.asarray(xs, dtype=np.float64)
    ys = np.asarray(ys, dtype=np.float64)
    return 0.5 * abs(np.dot(xs, np.roll(ys, -1)) - np.dot(ys, np.roll(xs, -1)))
```

Replace line 150 with: `'area': _polygon_area(xs, ys)`

**Acceptance Criteria:**
1. Unit rectangle (0,0)→(100,0)→(100,50)→(0,50): area = 5000.0 m²
2. Unit triangle (0,0)→(100,0)→(50,86.6): area ≈ 4330 m²
3. Degenerate polygon (all points collinear): area = 0.0
4. Real Kayad ore polygon shape (if available): area matches GIS calculation
5. `score_ore_envelope` receives correct area and returns geologically sensible scores
6. All existing tests pass (synthetic data in conftest uses no polygons, so no regression expected)

**Files changed:** `modules/m01_data_loader.py` (add `_polygon_area`, modify line 150), `test/test_data_loader.py` (new test)

---

### JC-06: Replace PIL with GDAL for GeoTIF Loading

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2), Rose AI (G2.5 — data registration), Dr. Prithvi (G3 — geophysics spatial integrity)  
**Effort:** 3 days  
**Priority:** CRITICAL — geophysics may be spatially misregistered  
**Depends on:** JC-01 (imports fixed)

**Problem:**  
`m01_data_loader.py` line 11: `from PIL import Image`. PIL reads TIF pixel arrays but has **no CRS, no geotransform, no nodata metadata**. If a gravity TIF has origin (468000, 2932000) but the project config says (468655, 2932890), every cell is offset by 655m east and 890m north. There is no warning. All geophysics criteria (C4, C5, C7b, C8, C9) use wrong values.

**Fix:** Replace PIL with GDAL (guaranteed in QGIS Python) or rasterio (preferred API but may not be available). Use GDAL as primary since it is always available in QGIS environments.

**Implementation:**
```python
# Replace: from PIL import Image
# With:
from osgeo import gdal
gdal.UseExceptions()

def _load_tif_folder(self, folder, scale=1.0, nodata=-9999.0):
    grids = {}
    for f in sorted(glob.glob(os.path.join(folder, '*.tif'))):
        ds = gdal.Open(f, gdal.GA_ReadOnly)
        if ds is None:
            self.log(f"WARNING: Cannot open {f}")
            continue
        band = ds.GetRasterBand(1)
        arr = band.ReadAsArray().astype(np.float32) * scale
        gt = ds.GetGeoTransform()  # (origin_x, pixel_w, 0, origin_y, 0, pixel_h)
        crs = ds.GetProjection()
        nd = band.GetNoDataValue()
        if nd is not None:
            arr[arr == nd] = np.nan
        elif nodata != 0:
            arr[np.isclose(arr, nodata * scale)] = np.nan
        # Extract mRL from filename
        m = re.search(r'(-?\d+)', os.path.basename(f))
        if m:
            grids[int(m.group(1))] = arr
        ds = None  # close
    return grids
```

**Acceptance Criteria:**
1. PIL (`from PIL import Image`) is removed from `m01_data_loader.py`
2. GDAL reads CRS and geotransform from every TIF
3. If TIF CRS does not match `cfg.grid.epsg`, a warning is logged (not a silent pass)
4. If TIF pixel size does not match expected (gravity=5m, magnetics=30m), a warning is logged
5. Nodata values are read from TIF metadata (band.GetNoDataValue()), not hardcoded to -9999
6. The broken nodata filter (`arr[arr < nodata * 0.9]` line 85) is replaced with `arr[arr == nd] = np.nan`
7. Update conftest synthetic data creation to use GDAL-compatible TIFs (or keep PIL for writing test TIFs only)
8. All existing tests pass
9. New test: load a TIF with known geotransform, verify pixel values map to correct coordinates

**Dr. Prithvi review question:** For the Kayad dataset, are the gravity TIFs (5m pixel) and magnetics TIFs (30m pixel) both in EPSG:32643 with their geotransform matching the project grid origin? Or are they offset?

**Files changed:** `modules/m01_data_loader.py` (major refactor of `_load_tif_folder`), `test/conftest.py` (update TIF creation), `test/test_data_loader.py` (new spatial tests)

---

### JC-07: Implement Drill Hole Desurvey (Minimum Curvature)

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2), Rose AI (G2.5 — integration with drill processor), Dr. Prithvi (G3 — geological correctness)  
**Effort:** 5 days  
**Priority:** CRITICAL — all subsurface positions are wrong for deviated holes  
**Depends on:** JC-06 (GDAL migration, so integration tests have correct geophysics)

**Problem:**  
`m02_drill_processor.py` stores collar coordinates in `self.hole_coords` (lines 67–68) and uses them for all spatial lookups. The `geology_at_level()` method (lines 117–165) checks `if zb <= z_mrl <= zt` — a purely 1D depth check against collar XY. Survey data is loaded by `DataLoader.load_survey()` but **never consumed** by `DrillProcessor`.

For a hole inclined at 70° (typical at Kayad), at 500m down-hole depth, the true XY is offset by ~170m from collar. This means:
- Lithology (C1) is assigned to the wrong grid cells
- PG halo distances (C2) are measured from the wrong points
- CSR standoff (C3) is measured from the wrong footwall contacts
- Grade model endorsement (C9) references wrong spatial locations

**Implementation — Minimum Curvature Desurvey:**

Add `modules/m07_desurvey.py`:
```python
def minimum_curvature(survey_df, collar_df, col_bhid, col_depth, col_azi, col_dip,
                       col_x, col_y, col_z) -> pd.DataFrame:
    """
    Returns DataFrame with columns: BHID, DEPTH, X, Y, Z
    for every survey station, using minimum curvature method.
    """
    results = []
    for bhid, grp in survey_df.groupby(col_bhid):
        collar = collar_df[collar_df[col_bhid] == bhid].iloc[0]
        x0, y0, z0 = collar[col_x], collar[col_y], collar[col_z]
        grp = grp.sort_values(col_depth)
        
        x, y, z = x0, y0, z0
        prev_azi = np.radians(grp.iloc[0][col_azi])
        prev_dip = np.radians(grp.iloc[0][col_dip])
        results.append({'BHID': bhid, 'DEPTH': 0.0, 'X': x, 'Y': y, 'Z': z})
        
        for i in range(1, len(grp)):
            row = grp.iloc[i]
            md = row[col_depth] - grp.iloc[i-1][col_depth]
            azi = np.radians(row[col_azi])
            dip = np.radians(row[col_dip])
            
            # Minimum curvature
            cos_dl = (np.cos(prev_dip - dip) - 
                      np.sin(prev_dip) * np.sin(dip) * (1 - np.cos(azi - prev_azi)))
            dl = np.arccos(np.clip(cos_dl, -1, 1))
            rf = 2 / dl * np.tan(dl / 2) if abs(dl) > 1e-6 else 1.0
            
            dx = 0.5 * md * (np.sin(prev_dip)*np.sin(prev_azi) + np.sin(dip)*np.sin(azi)) * rf
            dy = 0.5 * md * (np.sin(prev_dip)*np.cos(prev_azi) + np.sin(dip)*np.cos(azi)) * rf
            dz = -0.5 * md * (np.cos(prev_dip) + np.cos(dip)) * rf
            
            x += dx; y += dy; z += dz
            results.append({'BHID': bhid, 'DEPTH': row[col_depth], 'X': x, 'Y': y, 'Z': z})
            prev_azi, prev_dip = azi, dip
    
    return pd.DataFrame(results)
```

Modify `m02_drill_processor.py`:
- `build_lookups()` accepts `survey_df` parameter
- Calls `minimum_curvature()` to get true XYZ per station
- Interpolates to get XYZ at each litho/assay interval midpoint
- Stores `hole_coords_at_depth` dict: `{bhid: [(depth, x, y, z), ...]}` instead of just collar coords
- `geology_at_level()` uses desurveyed XY for each interval, not collar XY

**Acceptance Criteria:**
1. Vertical hole (azi=0, dip=-90 at all stations): desurveyed XY = collar XY at all depths. Z decreases linearly.
2. 45° inclined hole (dip=-45, azi=0): at 100m depth, X offset ≈ 0m, Y offset ≈ 70.7m, Z ≈ collar_z - 70.7m
3. S-curved hole: two survey stations with different azimuths produce smoothly curved trajectory
4. `geology_at_level()` returns different lithology for a deviated hole vs. what the vertical projection would return (construct a test case where the deviation is large enough to cross a grid cell boundary)
5. Survey CSV with missing stations gracefully handled (interpolate between available stations)
6. Holes with no survey data default to vertical projection (backwards compatible)
7. All existing tests pass (synthetic data uses vertical holes, so results should be unchanged)
8. New module `m07_desurvey.py` follows architecture rule: NO QGIS imports

**Dr. Prithvi review questions:**
- At Kayad, what is the typical hole deviation? Are holes mostly vertical, or do many have significant inclination?
- Should desurvey use collar azimuth/dip as the first survey station, or is there always a survey measurement at 0m depth?
- Are there Kayad holes with known trajectories we can validate against?

**Files changed:** `modules/m07_desurvey.py` (new), `modules/m02_drill_processor.py` (major refactor), `test/test_desurvey.py` (new), `test/test_integration.py` (add deviated hole case)

---

## Sprint 11 — Deposit-Agnostic Scoring (Weeks 4–5)

### JC-08: Move All Hardcoded Thresholds to Config

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2), Dr. Prithvi (G3 — threshold values), Dr. Riya (G3 — deposit type literature)  
**Effort:** 4 days  
**Priority:** HIGH — plugin only works for Kayad without this  
**Depends on:** JC-02 (scoring bug fixed), JC-07 (desurvey working — final scoring function signatures)

**Problem:**  
Across `m04_scoring_engine.py`, `m02_drill_processor.py`, and `m05_gpkg_writer.py`, there are **47 hardcoded threshold values** that are Kayad-specific. A user running this on a VMS deposit will get meaningless scores with no warning.

**Inventory of hardcoded values to move to config:**

**In `m04_scoring_engine.py`:**
| Lines | What | Current Kayad Value |
|-------|------|-------------------|
| 36–38 | Litho score tables per regime (3 dicts) | `{1:1.0, 2:0.0, 3:0.30, 4:0.25, ...}` etc. |
| 48–54 | PG halo distance breaks + scores | `[2,4,10,15,20,30,50]` / `[0.50,0.80,1.00,...]` |
| 60–67 | CSR standoff breaks + scores (per regime) | `[5,15,30]` / `[5,10,40,60,100]` |
| 72–84 | Gravity absolute mGal thresholds + depth cuts | z=310/160 boundaries, 5 break arrays |
| 101–106 | Mag absolute uSI thresholds | `[-10,-5,0,10,30,60]` |
| 166–169 | Plunge proximity distance breaks | `[75,150,300,600]` |
| 176–178 | Gravity gradient percentile multipliers | 0.15/0.95/1.40 for g40/g80/g90 |
| 190–192 | Mag gradient multipliers | 1.5/1.0/0.5 of median |
| 200–204 | Laplacian z-score thresholds | `[-1.5,-0.75,-0.25,0,0.5]` |
| 229–232 | Ore envelope ratio breaks | `[0.5,1.0,2.0,3.5]` |

**In `m02_drill_processor.py`:**
| Line | What | Current Value |
|------|------|--------------|
| 34 | structural_marker_code | 3 (Pegmatite) |
| 36 | footwall_code | 4 (CSR) |
| 98 | coarse grid multiplier | 6 (→30m) |
| 112, 132 | max nearest holes | 5 |

**In `m05_gpkg_writer.py`:**
| Line | What | Current Value |
|------|------|--------------|
| 17 | LITHO_NAMES dict | `{0:'Unknown',1:'QMS',...}` |
| 18 | REGIME_NAMES dict | `{0:'Lower mine',...}` |
| 19 | CLASS_NAMES dict | `{0:'Very Low',...}` |
| 191 | date in gpkg_contents | `'2026-01-01'` |

**In `alg_run_scoring.py` and `m06_voxel_builder.py`:**
| Lines | What | Current Value |
|-------|------|--------------|
| Various | fallback ore area | 50000 m² |
| Various | VH threshold | 75 |
| Various | fallback distances | 9999.0, 200.0 |

**Fix:** Add `ScoringThresholdsConfig` dataclass to `core/config.py`:
```python
@dataclass
class ScoringThresholdsConfig:
    # PG halo
    pg_distance_breaks: List[float] = field(default_factory=lambda: [2,4,10,15,20,30,50])
    pg_score_values: List[float] = field(default_factory=lambda: [0.50,0.80,1.00,0.70,0.50,0.35,0.25,0.15])
    # CSR standoff (per regime)
    csr_upper_breaks: List[float] = ...
    csr_lower_breaks: List[float] = ...
    # Gravity absolute (per depth regime)
    grav_abs_breaks_upper: List[float] = ...
    # ... etc for all thresholds
    
    # Drill processor
    structural_marker_code: int = 3
    footwall_code: int = 4
    coarse_grid_factor: int = 6
    max_nearest_holes: int = 5
    
    # Display
    litho_names: Dict[int, str] = ...
    regime_names: Dict[int, str] = ...
    class_names: Dict[int, str] = ...
```

Then pass `cfg.thresholds` into every scoring function.

**Acceptance Criteria:**
1. All 47 hardcoded values are now in `ScoringThresholdsConfig` with Kayad defaults
2. Default config produces **identical output** to current code (regression test)
3. Custom thresholds can be set via JSON and produce different scores
4. Config JSON roundtrip preserves all threshold values
5. All existing tests pass unchanged (they use default config which has Kayad values)
6. `grep -rn "0\.90\|0\.80\|0\.70\|0\.55\|0\.35\|0\.25" modules/m04_scoring_engine.py` returns zero matches (all values come from config)

**Dr. Prithvi / Dr. Riya review:** Are the Kayad threshold values documented in the Kayad report? Are there published threshold ranges for VMS, epithermal, and porphyry systems that we can use as starting points for presets?

**Files changed:** `core/config.py` (add `ScoringThresholdsConfig`), `modules/m04_scoring_engine.py` (all 14 functions), `modules/m02_drill_processor.py` (4 constants), `modules/m05_gpkg_writer.py` (3 dicts + date), `algorithms/alg_run_scoring.py`, `modules/m06_voxel_builder.py`

---

### JC-09: Deduplicate Scoring Pipeline — Extract `compute_level()`

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2), Rose AI (G2.5 — both paths produce identical output)  
**Effort:** 2 days  
**Priority:** HIGH — bug fixes must be applied in two places currently  
**Depends on:** JC-08 (scoring functions have final signatures)

**Problem:**  
`alg_run_scoring.py` lines 89–163 and `m06_voxel_builder.py` lines 56–186 contain duplicated logic:
- Cell coordinate grid construction
- Ore distance computation
- Ore area lookup via nearest polygon level
- Regime ID determination
- Inputs dict assembly (keys: `lv`, `pg`, `csr`, `grav`, `grav_raw`, `grav_gradient`, etc.)
- Scoring calls (`compute_proximity`, `compute_blind`)
- VH threshold counting

**Fix:** Extract shared function into `modules/m04_scoring_engine.py` (or new `modules/m_pipeline.py`):
```python
def compute_level(z_mrl, cfg, drill_proc, geophys_proc, cell_E, cell_N, 
                  dist_ore, poly_lu, block_model_df=None):
    """Process a single z-level: geology + geophysics + scoring. 
    Returns (prox_results, blind_results, geo_fields)."""
    ...
```

Both `alg_run_scoring.py` and `m06_voxel_builder.py` call this function.

**Acceptance Criteria:**
1. New `compute_level()` function exists
2. `alg_run_scoring.py` per-level loop body is ≤ 15 lines (calls `compute_level` + writes GPKG)
3. `m06_voxel_builder.py` per-level loop body is ≤ 15 lines (calls `compute_level` + packs slab)
4. Output is byte-identical between the two code paths for the same inputs
5. All existing tests pass
6. Integration test verifies GPKG output matches voxel slab data for the same level

**Files changed:** `modules/m04_scoring_engine.py` or new `modules/m_pipeline.py`, `algorithms/alg_run_scoring.py`, `modules/m06_voxel_builder.py`

---

## Sprint 12 — Test Coverage (Weeks 6–7)

### JC-10: Add Regime Transition Tests

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2), Dr. Prithvi (G3 — regime boundary geology)  
**Effort:** 3 days  
**Priority:** HIGH — regime 0 and 1 have zero coverage  
**Depends on:** JC-08 (thresholds in config), JC-09 (single scoring path)

**Problem:**  
The entire test suite only exercises `regime_id=2` (upper mine). Regime 0 (lower/deep) and regime 1 (transition) have near-zero coverage. The transition regime applies a 30% confidence discount. Regime 0 uses different litho scores (CSR primary host, score=1.0 vs 0.25 in upper), different PG halo behavior, and different structural corridor (N315°E vs N28°E).

**Tests to add:**

1. **`test_litho_scoring_regime_0`**: CSR (code 4) should score 1.0 in regime 0 (vs 0.25 in regime 2). QMS should score 0.6 (vs 1.0 in regime 2).
2. **`test_litho_scoring_regime_1`**: QMS should score 0.8 (between 1.0 and 0.6). Transition discount: verify final scores are 70% of full score.
3. **`test_pg_halo_regime_0`**: PG halo is less diagnostic in lower mine. Score should fill to 0.4 baseline.
4. **`test_csr_standoff_regime_0`**: Uses different break distances `[5, 15, 30]` with `[1.00, 0.70, 0.45, 0.25]`.
5. **`test_structural_corridor_deep`**: N315°E corridor should score high for deep cells near the deep anchor (470210, 2935041, mRL -140). N28°E corridor should score low for these same cells.
6. **`test_regime_boundary_at_z60`**: Cell at z=60 (exact boundary) should be in regime 1 (transition), not 0.
7. **`test_regime_boundary_at_z160`**: Cell at z=160 should be in regime 2 (upper), not 1.
8. **`test_integration_regime_0`**: Full pipeline on synthetic data at mRL -100 (deep regime). Verify CSR-primary scoring behaviour.
9. **`test_transition_confidence_discount`**: Verify that regime 1 scores are discounted by `cfg.regimes.transition_confidence_discount` (0.30 → 70% of full score).

**Acceptance Criteria:**
1. All 9 new tests pass
2. At least one test per criterion function with `regime_id=0`
3. At least one test per criterion function with `regime_id=1`
4. Transition discount is explicitly verified
5. Regime boundary behaviour at z=60 and z=160 is deterministic

**Dr. Prithvi review:** Are the transition confidence discount (30%) and regime boundary elevations (60m, 160m mRL) geologically robust? Or should they be configurable per project?

**Files changed:** `test/test_scoring.py` (new tests), `test/test_integration.py` (new deep-regime integration test)

---

### JC-11: Add Voxel Builder Tests

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2), Rose AI (G2.5 — integration)  
**Effort:** 3 days  
**Priority:** HIGH — zero test coverage  
**Depends on:** JC-09 (shared compute_level)

**Tests to add:**
1. Build voxel from synthetic data (3 levels, 20×20 grid). Verify NPZ archive structure.
2. Verify slab packing — correct number of levels per slab (`voxel_slab_size=10`).
3. Verify metadata JSON written alongside NPZ.
4. Verify progress_callback is called with correct percentages.
5. Verify cancellation (callback raises KeyboardInterrupt → build stops cleanly).
6. Verify NPZ data matches GPKG data for the same level.

**Files changed:** `test/test_voxel.py` (new)

---

### JC-12: Add Golden-File Regression Tests

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2), Dr. Prithvi (G3 — reference values), Rose AI (G2.5)  
**Effort:** 3 days  
**Priority:** HIGH — no baseline for detecting score regressions  
**Depends on:** JC-05 through JC-08 (all scoring corrections applied)

**Problem:**  
No test compares output against known-good reference values. Any change to scoring logic could silently alter prospectivity maps.

**Fix:** Create a small reference dataset (20×20 grid, 3 levels, 2 boreholes with known lithology) with pre-computed expected scores. Assert that proximity and blind scores match within `atol=0.01`.

**The reference values must be computed once with the corrected code (post JC-02 through JC-08), reviewed by Dr. Prithvi for geological plausibility, and frozen as the golden file.**

**Acceptance Criteria:**
1. `test/golden/` directory contains reference config + expected scores JSON
2. `test_regression.py` loads reference data, runs pipeline, asserts match within tolerance
3. Any future scoring change that breaks regression triggers a clear test failure
4. Dr. Prithvi has reviewed the golden scores and confirmed geological plausibility

**Files changed:** `test/test_regression.py` (new), `test/golden/` (new directory with reference data)

---

### JC-13: Add Boundary Value and NaN Input Tests

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2)  
**Effort:** 2 days  
**Priority:** MEDIUM  
**Depends on:** JC-08 (final scoring signatures)

**Tests to add:**
1. NaN input to each scoring function → output should be NaN (not crash, not 0)
2. Inf input → should be handled (clipped or NaN)
3. Zero-length array → should return zero-length array
4. Exact threshold boundaries for PG halo: 2.0m, 4.0m, 10.0m (test both sides)
5. Exact threshold boundaries for CSR standoff: 10.0m, 40.0m
6. Gravity at exactly 0.0 mGal
7. Score at exactly class boundaries: 30.0, 45.0, 60.0, 75.0

**Files changed:** `test/test_scoring.py` (new tests)

---

## Sprint 13 — Data Quality & Performance (Week 8)

### JC-14: Proper Nodata Handling and Warning System

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2), Rose AI (G2.5 — data quality)  
**Effort:** 2 days  
**Priority:** MEDIUM  
**Depends on:** JC-06 (GDAL), JC-13 (NaN tests)

**Fix:**
1. Remove `warnings.filterwarnings('ignore')` from: `m01_data_loader.py` line 12, `m02_drill_processor.py` line 15, `m03_geophys_processor.py` line 16, `m04_scoring_engine.py` line 13, `m06_voxel_builder.py` line 10
2. Replace nodata filter `arr[arr < nodata * 0.9]` (m01 line 85) with proper `np.nan` from GDAL nodata (done in JC-06)
3. Fix `m03_geophys_processor.py` line 125: hardcoded mag fallback `5.0` → use `np.nan` (let scoring handle NaN)
4. Fix `m03_geophys_processor.py` line 130: `grav_std` protection exists (0.01 fallback) but `mag_std` has none → add same protection
5. Add data quality summary after loading: log % finite values per geophysics grid

**Files changed:** `m01_data_loader.py`, `m02_drill_processor.py`, `m03_geophys_processor.py`, `m04_scoring_engine.py`, `m06_voxel_builder.py`

---

### JC-15: GPKG Performance — Batch Writing + Spatial Index

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2), Lala (resource review)  
**Effort:** 3 days  
**Priority:** MEDIUM — slow for production grids  
**Depends on:** JC-09 (shared compute_level), JC-14 (nodata clean)

**Problem:**  
`m05_gpkg_writer.py` writes row-by-row in a Python loop (lines 137–184). For 348,004 cells (Kayad default 482×722), this takes several minutes per level × 145 levels = hours. No spatial index means QGIS must build one on first load.

**Fix:**
1. Pre-compute all geometry blobs as a numpy array of bytes using vectorised operations
2. Build all row tuples as a list of tuples, then `executemany()` in a single transaction
3. After write, create RTree spatial index: `INSERT INTO gpkg_extensions ...` + `CREATE VIRTUAL TABLE rtree_<table>_geom USING rtree(...)`
4. Fix hardcoded date (line 191): use `datetime.date.today().isoformat()`

**Acceptance Criteria:**
1. Write time for 50×50 synthetic grid ≤ 1 second (currently ~2–3s due to loop overhead)
2. Spatial index exists in output GPKG
3. GPKG opens correctly in QGIS with instant rendering (no "building spatial index" delay)
4. Output is byte-compatible with existing GPKGs (same schema, same column order)

**Lala review:** What is the peak RAM footprint for batch-preparing 348K rows? Estimate: ~100 MB for geometry blobs + ~50 MB for score arrays. Acceptable for 16GB machine.

**Files changed:** `modules/m05_gpkg_writer.py`

---

## Sprint 14 — UI & Async (Weeks 9–10)

### JC-16: Non-blocking UI with QgsTask

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2), Vimal AI (G3.5 — operational readiness)  
**Effort:** 4 days  
**Priority:** HIGH — QGIS freezes during scoring  
**Depends on:** JC-01 (imports fixed), JC-09 (single scoring path)

**Fix:** Create `BhumiScoringTask(QgsTask)` that wraps the scoring pipeline. Show progress bar. Support cancellation.

**Files changed:** `ui/dock_panel.py`, `ui/wizard.py`, new `core/scoring_task.py`

---

### JC-17: Config Preset System (Deposit Templates)

**Assigned to:** Deva AI  
**Reviewed by:** Dr. Prithvi (G3 — geological correctness per deposit type), Dr. Riya (G3 — literature basis)  
**Effort:** 5 days  
**Priority:** HIGH — enables mineral discovery beyond Kayad  
**Depends on:** JC-08 (all thresholds in config)

**Presets to create:**
1. **SEDEX Pb-Zn** — current Kayad defaults
2. **VMS Cu-Zn** — replace PG halo with footwall alteration pipe, add chargeability criterion
3. **Epithermal Au** — fault-zone proximity replaces linear corridor, resistivity high criterion
4. **Porphyry Cu-Mo** — concentric ring model around intrusive centre, IP chargeability

Each preset is a JSON file in `core/presets/` that provides all `ScoringThresholdsConfig` values.

**Dr. Prithvi / Dr. Riya:** Each preset needs geological review. What are the published threshold ranges for each deposit type?

**Files changed:** `core/presets/` (new directory, 4 JSON files), `core/config.py` (preset loading)

---

### JC-18: Complete Config Widget for All Geological Parameters

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2), Hema (spec — UI requirements)  
**Effort:** 5 days  
**Priority:** MEDIUM-HIGH  
**Depends on:** JC-17 (presets exist to populate UI)

**Add tabs:**
- Tab 1: Project & Grid (existing)
- Tab 2: Deposit Type selector (loads preset) & Lithology Codes editor
- Tab 3: Scoring Weights (sliders with live weight-sum display)
- Tab 4: Structural Corridors (table editor, with azimuth/anchor fields)
- Tab 5: Depth Regimes (table editor)

**Files changed:** `ui/config_widget.py` (major expansion)

---

## Sprint 15 — Polish & Release (Weeks 11–12)

### JC-19: Symbology Files (.qml/.sld)

**Assigned to:** Deva AI  
**Effort:** 2 days  
**Depends on:** JC-12 (golden-file confirms score ranges)

Pre-built QGIS style files: red=VH (≥75), orange=H (≥60), yellow=M (≥45), blue=L (≥30), grey=VL (<30).

**Files changed:** `styles/` (new directory), `algorithms/alg_load_results.py` (apply styles)

---

### JC-20: Layer Grouping in Results Loading

**Assigned to:** Deva AI  
**Effort:** 1 day

Create QGIS layer group "Bhumi3DMapper — {project_name}" and add levels as children.

**Files changed:** `algorithms/alg_load_results.py`

---

### JC-21: QGIS 4.0 (Qt6) Full Port Test

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA, Vimal AI  
**Effort:** 3 days  
**Depends on:** JC-01, JC-16

Run `pyqt5_to_pyqt6.py` migration. Test on QGIS 4.0. Fix any Qt6 issues.

---

### JC-22: Plugin Repository Submission

**Assigned to:** Deva AI, Hema (documentation)  
**Reviewed by:** Satya (final sign-off), Amit (G4)  
**Effort:** 5 days  
**Depends on:** All previous JCs

- Professional icon design (replace placeholder)
- Help documentation (plugin help pages)
- Update `metadata.txt` with correct URLs
- Submit to QGIS Plugin Repository
- Update GitHub repo README

---

## Dependency Graph

```
JC-01 (imports) ─────────────────────────────────────────────┐
  │                                                           │
JC-02 (grav gradient) ──────────────────────────┐             │
  │                                              │             │
JC-03 (z_levels) ───────────────────────────┐    │             │
  │                                          │    │             │
JC-04 (phantom test) ──────────────────┐     │    │             │
                                        │     │    │             │
JC-05 (polygon area) ──────────────┐    │     │    │             │
  │                                 │    │     │    │             │
JC-06 (GDAL) ─────────────────┐    │    │     │    │             │
  │                             │    │     │    │    │             │
JC-07 (desurvey) ────────┐     │    │     │    │    │             │
  │                        │    │    │     │    │    │             │
JC-08 (thresholds) ──┐    │    │    │     │    │    │             │
  │                    │    │    │    │     │    │    │             │
JC-09 (dedup) ───┐    │    │    │    │     │    │    │             │
  │               │    │    │    │    │     │    │    │             │
JC-10 (regime) ──┤    │    │    │    │     │    │    │             │
JC-11 (voxel)  ──┤    │    │    │    │     │    │    │             │
JC-12 (golden) ──┤    │    │    │    │     │    │    │             │
JC-13 (NaN)    ──┤    │    │    │    │     │    │    │             │
                  │    │    │    │    │     │    │    │             │
JC-14 (nodata)───┤    │    │    │    │     │    │    │             │
JC-15 (perf)   ──┘    │    │    │    │     │    │    │             │
                       │    │    │    │     │    │    │             │
JC-16 (async UI)───────┘    │    │    │     │    │    │─────────────┘
JC-17 (presets) ─────────────┘    │    │     │    │    │
JC-18 (config UI)─────────────────┘    │     │    │    │
JC-19 (styles) ────────────────────────┘     │    │    │
JC-20 (layers) ──────────────────────────────┘    │    │
JC-21 (Qt6)   ───────────────────────────────────┘    │
JC-22 (release) ──────────────────────────────────────┘
```

---

## Sprint Summary

| Sprint | Weeks | Job Cards | Deliverable |
|--------|-------|-----------|-------------|
| **S9** | 1 | JC-01, JC-02, JC-03, JC-04 | v1.1.0 — imports fixed, scoring bug fixed, clean test suite |
| **S10** | 2–3 | JC-05, JC-06, JC-07 | v1.2.0 — spatial accuracy (polygon area, GDAL, desurvey) |
| **S11** | 4–5 | JC-08, JC-09 | v1.3.0 — deposit-agnostic scoring, deduplicated pipeline |
| **S12** | 6–7 | JC-10, JC-11, JC-12, JC-13 | Test coverage: regimes, voxel, regression, boundaries |
| **S13** | 8 | JC-14, JC-15 | Data quality + GPKG performance |
| **S14** | 9–10 | JC-16, JC-17, JC-18 | Async UI + presets + config widget |
| **S15** | 11–12 | JC-19, JC-20, JC-21, JC-22 | Polish + Qt6 + release |

**Total: 22 job cards, 12 weeks, targeting Bhumi3DMapper v2.0**

---

*Every job card serves the primary objective: mineral discovery. The sequencing ensures that foundational accuracy (spatial positions, scoring correctness) is fixed before building on top.*

*Satya to assign. Dr. Prithvi and Dr. Riya geological reviews required at JC-02, JC-05, JC-07, JC-08, JC-10, JC-12, JC-17.*

*Amit G4 required at sprint boundaries: after S9, S10, S11, and S15.*
