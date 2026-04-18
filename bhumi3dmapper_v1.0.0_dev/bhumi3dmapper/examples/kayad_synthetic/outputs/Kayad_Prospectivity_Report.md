# Bhumi3DMapper — Kayad Synthetic Dataset: Prospectivity Run Report

**Generated:** 2026-04-18 (BH-12 corrected run)
**Build:** `post-BH-12` (post BH-08/09/10/11/12 fixes)
**Dataset:** `bhumi3dmapper/examples/kayad_synthetic/`
**Engine:** Engine 1 — Kayad c-criterion (brownfields)
**Run by:** Dr. Prithvi (Chief Geoscientist, AiRE)

---

## 1. Executive Summary

Bhumi3DMapper was run on the corrected Kayad synthetic SEDEX dataset across five
depth levels (mRL +270, +295, +320, +345, +370) — the QMS host-rock target zone.
All five bug fixes (BH-08 through BH-12) are active in this run.

**BH-12 corrected:** Previous example scoring was at mRL 185–235 (footwall
Amphibolite/CSR zone) where scores were suppressed by the hard veto (all cells at
20.0 for Amphibolite levels). The config now correctly targets mRL 270–370 (QMS
host-rock zone) where SEDEX ore is expected to occur.

| mRL | Model | Best Score | Class | Cells ≥75 (High) |
|-----|-------|-----------|-------|------------------|
| +295 | Proximity | **81.8** | High | 612 |
| +295 | Blind (Recon) | **98.6** | Very High | 1,187 |
| +320 | Proximity | **82.4** | High | 529 |
| +320 | Blind (Recon) | **98.6** | Very High | 1,089 |

The README's stated range of **70–95** for centre cells is now confirmed and
demonstrable. The tool is working correctly as a prototype.

---

## 2. Dataset Summary

| Parameter | Value |
|---|---|
| Project | Bhumi3D Example (Synthetic SEDEX) |
| Deposit type | SEDEX Pb-Zn (Kayad analogue, Rajasthan) |
| CRS | EPSG:32643 (WGS 84 / UTM 43N) |
| Grid | 50 × 50 cells at 5m = 250m × 250m footprint |
| Depth levels | mRL +270, +295, +320, +345, +370 (dz = 25m) |
| Total voxels | 12,500 cells (5 levels × 2,500) |
| Drill holes | 50 holes, 224 litho intervals |
| Gravity TIFs | 5 levels at 5m pixel resolution |
| Magnetics TIFs | 5 levels at 30m pixel resolution (NN-upsampled to 5m) |
| Block model | Not configured — C9 inactive |
| Ore polygons | Not provided — C10 inactive |

---

## 3. Lithological Character at Scored Levels

| mRL | Dominant Lithology | % cells | Scoring result |
|---|---|---|---|
| +270 | CSR (code 4) | 73% | Secondary host — C1 = 0.25; scored |
| +270 | QMS (code 1) | 27% | Primary host — C1 = 1.0; high score |
| +295 | QMS (code 1) | 95% | Primary host — C1 = 1.0 throughout |
| +320 | QMS (code 1) | 100% | Full QMS level — maximum C1 score |
| +345 | QMS (code 1) | 92% | Transitioning up — still QMS-dominated |
| +370 | Pegmatite (code 3) | 62% | Structural marker — C1 = 0.6 (intermediate) |

**No Amphibolite at any of these levels.** The hard veto (score cap = 20.0) was
not triggered. All cells scored normally.

---

## 4. Score Distribution Summary

| mRL | Prox max | Prox ≥60 | Prox ≥75 | Blind max | Blind ≥60 | Blind ≥75 |
|-----|---------|---------|---------|---------|---------|---------|
| +270 | 80.0 | 900 | 40 | 97.6 | 1,334 | 465 |
| +295 | 81.8 | 2,165 | **612** | 98.6 | 2,191 | **1,187** |
| +320 | 82.4 | 2,051 | **529** | 98.6 | 2,067 | **1,089** |
| +345 | 76.3 | 1,464 | 66 | 92.4 | 1,798 | 656 |
| +370 | 72.2 | 664 | 0 | 90.1 | 1,192 | 333 |

**Peak prospectivity at mRL +295 and +320** — consistent with the main mineralised
interval in the Kayad-type SEDEX model (below Pegmatite marker, above CSR
footwall).

---

## 5. Geological Interpretation

### 5.1 Primary Target Zone — mRL +295 to +320, QMS Host Rock

**Location:** E 469490–469740, N 2934890–2935140 (full grid; prospective subset centred)
**Centroid of High cells:** approximately E 469583, N 2935014 (ore pod centre)
**Depth:** mRL +295–320 (surface at ~mRL +450; depth to target ~130–155m)

The prospective cluster at mRL +295 to +320 corresponds to the **QMS ore-hosting
horizon** — the primary stratigraphic host for SEDEX Pb-Zn mineralisation in the
Kayad system. At these levels, the c-criterion scoring integrates:

- **C1 — Lithology:** QMS (code 1) scores 1.0 — maximum lithological endorsement
- **C4 — Gravity:** Strong negative gravity residual (up to −0.32 mGal at mRL 295)
  consistent with density-deficit ore pods (sulphide + carbonate replacement)
- **C5 — Magnetics:** Well below-average susceptibility (diamagnetic QMS / sulphide
  signature) — blind model Z-score strongly negative
- **C6 — Structural corridor:** Cells within the N28E corridor score 0.80–1.00
- **C7 — Plunge proximity:** Cells near the plunge axis score higher

### 5.2 Depth Zonation

The score profile with depth reflects the stratigraphy:

| Zone | mRL | Behaviour |
|---|---|---|
| Upper Pegmatite marker | +370 | Prox 72 — C1 intermediate (0.6); structural reference |
| QMS main ore zone | +295–+345 | Prox 76–82 — C1 = 1.0; geophysics most anomalous |
| QMS / CSR transition | +270 | Prox 80 — bimodal (QMS pods in CSR matrix) |

### 5.3 Geophysical Signature at mRL +295 (Peak Level)

| Parameter | Grid mean | Ore pod centre | Interpretation |
|---|---|---|---|
| Gravity | −0.14 mGal | −0.32 mGal | Strong density deficit — sulphide + QMS vs regional |
| Magnetics | ~8–9 µSI | ~−10 to −14 µSI | Strongly diamagnetic — consistent with sulphide QMS |

### 5.4 Inactive Criteria — Score Ceiling

**C9 — Grade Model (proximity weight 0.7):**
No block model was provided. This criterion contributed zero to all proximity
scores, reducing the achievable maximum by approximately 6 percentage points.
*Action: Provide block model CSV files in `block_model.domain_files` config.*

**C10 — Ore Envelope (proximity weight 1.0, blind weight 0.5):**
No ore polygon data provided. C10 blind (novelty) treats all cells as equally
distant from known ore.
*Action: Provide ore polygon GPKGs in `ore_polygons.polygon_folder`.*

With both C9 and C10 active, expected proximity scores would rise to 88–94 (Very
High) for the ore pod centre cells at mRL +295–320.

---

## 6. BH-12 Fix Validation

**Bug closed.** The config previously used scoring levels mRL 185–235 (footwall
Amphibolite/CSR zone), which produced suppressed scores (max 53.6 proximity, all
cells at mRL 185 and 210 hard-vetoed at 20.0). The fix:

1. **`config.json`** — `z_top_mrl` changed from 235 to 370, `z_bot_mrl` from 185
   to 270
2. **Geophysics TIFs** — New synthetic TIFs generated for mRL 270, 295, 320, 345,
   370 (replacing old footwall TIFs at 185, 210, 235)
3. **`gen_tifs_bh12.py`** — Generation script committed to the example folder for
   reproducibility

**Confirmed:** Scores now reach 72–82 proximity (High class) and 90–99 blind
(Very High class) for QMS zone cells. README's stated range of 70–95 is validated.

---

## 7. Pipeline Validation — All Bug Fixes Confirmed

| Fix | Confirmed |
|---|---|
| BH-08: Engine 2 fields loaded from JSON | Engine field = "kayad" correctly read |
| BH-09: Corridor gap warning | No gap at mRL 270–370 (within Shallow_N28E) |
| BH-10: Relative paths resolved on direct load | All paths resolved correctly |
| BH-11: Magnetics scale check | No warning (µSI range 0–15.5, well under 5,000) |
| BH-12: Example config corrected to QMS zone | Scores reach 72–82 proximity (High) |
| Hard veto (C1/Amphibolite) | Not triggered — no Amphibolite at mRL 270–370 |
| Desurvey | Minimum-curvature desurvey applied (50 holes, 100 survey records) |
| C1 QMS primary host | Scores 1.0 at mRL 295 and 320 — confirmed |

---

## 8. Recommendations — Next Steps

1. **Add block model CSV** (C9): Even a synthetic CSV with `main_lens` and `k18`
   domains will activate C9 and demonstrate the full scoring range (expected
   proximity peak ~90+).

2. **Add ore polygon GPKG** (C10): Synthetic GPKG at mRL +295 and +320 showing
   the ore pod footprint will activate C10 and further raise scores.

3. **Re-run VoxelBuilder** and generate QGIS-ready GPKGs for QGIS live demo.

4. **Extend to real Kayad dataset** when drill/geophysics data available.
   BH-11 will check magnetics units automatically. BH-09 will warn if the
   structural corridor config has gaps.

---

*Dr. Prithvi, Chief Geoscientist*
*AiRE — AI Resource Exploration Pvt Ltd*
*2026-04-18 | Bhumi3DMapper build post-BH-12 | BH-08 through BH-12 all active*
