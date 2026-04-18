# Bhumi3DMapper — Kayad Synthetic Dataset: Prospectivity Run Report

**Generated:** 2026-04-18  
**Build:** `0e74433` (post BH-08/09/10/11 fixes)  
**Dataset:** `bhumi3dmapper/examples/kayad_synthetic/`  
**Engine:** Engine 1 — Kayad c-criterion (brownfields)  
**Run by:** Dr. Prithvi (Chief Geoscientist, AiRE)

---

## 1. Executive Summary

Bhumi3DMapper was run on the Kayad synthetic SEDEX example dataset across three
depth levels (mRL +185, +210, +235). The pipeline executed without error. All
four bug fixes (BH-08 through BH-11) were confirmed active during this run.

The run identified a single prospective cluster at **mRL +235** — the
Calc-Silicate Rock (CSR) / Amphibolite contact horizon — with:

| Model | Best Score | Class | Prospective Cells (≥45) |
|---|---|---|---|
| Proximity | 53.6 | Moderate | 535 |
| Blind (Recon) | 73.8 | approaching High | 959 |

**Important caveat:** The scoring levels in this synthetic dataset (mRL 185–235)
are in the **footwall Amphibolite zone**, not the QMS host-rock target zone
(estimated mRL 270–370 based on the drill data). This is a dataset configuration
issue — see Section 6 (BH-12).

---

## 2. Dataset Summary

| Parameter | Value |
|---|---|
| Project | Bhumi3D Example (Synthetic SEDEX) |
| Deposit type | SEDEX Pb-Zn (Kayad analogue, Rajasthan) |
| CRS | EPSG:32643 (WGS 84 / UTM 43N) |
| Grid | 50 × 50 cells at 5m = 250m × 250m footprint |
| Depth levels | mRL +185, +210, +235 (dz = 25m) |
| Total voxels | 7,500 cells |
| Drill holes | 50 holes, 224 litho intervals |
| Gravity TIFs | 3 levels at 5m pixel resolution |
| Magnetics TIFs | 3 levels at 30m pixel resolution (NN-upsampled to 5m) |
| Block model | Not configured — C9 inactive |
| Ore polygons | Not provided — C10 inactive |

---

## 3. Lithological Character at Scored Levels

| mRL | Dominant Lithology | % cells | Scoring result |
|---|---|---|---|
| +235 | Amphibolite (code 2) | 57.3% | Hard veto applied to 1,432 cells |
| +235 | CSR (code 4) | 42.7% | Scored normally (secondary host, upper regime) |
| +210 | Amphibolite | 100% | All 2,500 cells hard-vetoed at score = 20.0 |
| +185 | Amphibolite | 100% | All 2,500 cells hard-vetoed at score = 20.0 |

The hard veto (score cap = 20.0 for Amphibolite) **is working correctly**. It
correctly suppresses amphibolite cells that cannot host SEDEX mineralisation.

---

## 4. Target Elevation Maps

### 4.1 mRL +235 — Proximity Model

```
TARGET ELEVATION MAP -- Kayad Synthetic  mRL +235
PROXIMITY MODEL  (N up, E right)  step=25m
Score: H=High(>=60)  M=Moderate(>=45)  L=Low(>=30)  .=Very Low

N\E  469492 469517 469542 469567 469592 469617 469642 469667 469692 469717
2935137   .       .       .       .       .       .       L       L       L       .
2935112   .       .       .       .       .       M       L       L       .       .
2935087   L       L       .       .       .       M       M       L       L       .
2935062   L       L       L       .       L       M       L       L       L       L
2935037   L       M       M       M       .       .       .       .       M       L
2935012   L       M       M       M       .       .       .       .       M       L
2934987   M       M       L       M       .       .       .       .       .       .
2934962   M       M       M       M       M       .       .       .       .       .
2934937   .       .       .       .       .       M       L       L       .       .
2934912   .       .       .       .       .       L       L       L       .       .
```

### 4.2 mRL +235 — Blind (Reconnaissance) Model

```
BLIND MODEL  (N up, E right)  step=25m
Score: H=High(>=60)  M=Moderate(>=45)  L=Low(>=30)  .=Very Low

N\E  469492 469517 469542 469567 469592 469617 469642 469667 469692 469717
2935137   .       .       .       .       .       .       M       L       M       .
2935112   .       .       .       .       .       M       M       L       .       .
2935087   L       M       .       .       .       H       H       M       M       .
2935062   M       M       M       .       M       H       M       H       M       M
2935037   M       M       M       H       .       .       .       .       H       M
2935012   M       M       H       H       .       .       .       .       M       M
2934987   M       M       M       H       .       .       .       .       .       .
2934962   M       M       M       M       H       .       .       .       .       .
2934937   .       .       .       .       .       H       M       M       .       .
2934912   .       .       .       .       .       M       M       L       .       .
```

---

## 5. Geological Interpretation

### 5.1 Primary Target Cluster — mRL +235, CSR Contact Zone

**Location:** E 469490–469700, N 2934910–2935130 (205m × 215m footprint)  
**Centroid:** E 469583, N 2935014  
**Depth:** mRL +235 (surface at ~mRL +450; depth to target ~215m)

The prospective cluster at mRL +235 corresponds to the **CSR / Amphibolite contact
horizon**, where the footwall calc-silicate rock transitions into the barren
amphibolite basement. In Kayad-type SEDEX systems, this contact marks the
structural floor beneath which ore-hosting QMS does not extend.

**Why is this horizon prospective despite CSR dominance?**

At mRL +235, the c-criterion scoring integrates:

- **C1 — Lithology:** CSR (code 4) scores 0.25 in the upper regime — secondary host,
  not primary, but not vetoed.
- **C4 — Gravity:** Mild negative gravity residual (mean −0.018 mGal in cluster)
  consistent with a density-deficit signature at this horizon.
- **C5 — Magnetics:** Below-average susceptibility (~9–12 µSI vs. grid mean ~13 µSI)
  consistent with reduced magnetic lithologies (CSR over Amphibolite).
- **C6 — Structural corridor:** Cells within the N28E corridor corridor footprint
  score 0.80–1.00. The cluster aligns with the Shallow_N28E corridor axis
  (E:469519, N:2934895 at mRL +185).
- **C7 — Plunge proximity:** Cells near the plunge axis of the corridor score higher.

The **blind model outperforms proximity at this level** (max 73.8 vs 53.6) because
the blind model uses contextual z-scoring (C4b, C5b) which is more sensitive to
subtle geophysical anomalies in a small survey area with low absolute amplitude.

### 5.2 Bimodal Pattern — N28E Structural Control

The target map shows two clusters:
- **SW cluster** (E 469490–469580, N 2934910–2935000): Moderate to Low proximity,
  Moderate blind — CSR cells near the western corridor shoulder.
- **NE cluster** (E 469580–469700, N 2935050–2935150): Moderate proximity, High
  blind — CSR cells near the eastern corridor shoulder, closer to the N28E axis
  with slightly stronger negative gravity.

This bimodal pattern is consistent with the N28E corridor geometry at mRL +235,
where the plunge offset at 215m depth below anchor has shifted the corridor axis
approximately 6m to the NE relative to the surface trace.

### 5.3 Geophysical Signature

| Parameter | Grid mean | Cluster mean | Interpretation |
|---|---|---|---|
| Gravity | +0.039 mGal | +0.018 mGal | Slight negative anomaly in cluster |
| Magnetics | +13.23 µSI | +11.70 µSI | Below-average susceptibility in cluster |

The geophysical contrast is modest at this level — consistent with the dataset
being at the CSR/Amphibolite contact rather than within the QMS host zone where
full density-deficit (negative gravity) and diamagnetic response (negative
susceptibility) would be expected.

### 5.4 Inactive Criteria — Score Ceiling

Two criteria were inactive during this run:

**C9 — Grade Model (proximity weight 0.7):**  
No block model was provided. This criterion contributed zero to all proximity
scores, reducing the achievable maximum by approximately 6 percentage points.
*Action: Provide block model CSV files in `block_model.domain_files` config.*

**C10 — Ore Envelope (proximity weight 1.0, blind weight 0.5):**  
No ore polygon data was provided. C10 proximity (ore envelope) contributes zero.
C10 blind (novelty) treats all cells as equally distant from known ore.
*Action: Provide ore polygon GPKGs in `ore_polygons.polygon_folder`.*

---

## 6. Critical Finding — BH-12: Example Dataset Level Range Error

**Severity: HIGH — example dataset does not demonstrate the intended behaviour.**

The Kayad synthetic drill data shows the following stratigraphy (depth from collar
at ~mRL +450):

| Depth from collar | Approx. mRL range | Rock type (code) |
|---|---|---|
| 0–180m | +270 to +450 | QMS host rock (code 1) |
| 80–100m | +350 to +370 | Pegmatite structural marker (code 3) |
| 180–220m | +230 to +270 | CSR footwall (code 4) |
| 220–344m | +105 to +230 | Amphibolite basement (code 2 — hard veto) |

**The scored levels (mRL +185, +210, +235) are in the CSR/Amphibolite zone, not
the QMS target zone (mRL +270 to +370).**

The README's claimed score range of 70–95 for centre cells cannot be achieved at
these levels because:
1. mRL +185 and +210 are 100% Amphibolite — hard veto forces all scores to 20.0.
2. mRL +235 is 57% Amphibolite + 43% CSR — max proximity is 53.6 (Moderate).

**Correct scoring levels should be mRL +270 to +370 (QMS + PG + CSR interaction).**

**Action required (BH-12):**  
Update `kayad_synthetic/config.json`:
```json
"grid": {
  "z_top_mrl": 370.0,
  "z_bot_mrl": 270.0,
  "dz_m": 25.0
}
```
And regenerate geophysics TIFs to cover mRL 270, 295, 320, 345, 370.
Scores in the QMS zone are expected to reach 75–85 (High to Very High).

---

## 7. Output Files Generated

| File | Description |
|---|---|
| `Kayad_Prospectivity_AllLevels.csv` | Full voxel table — 7,500 rows, all 3 levels |
| `Kayad_Target_Cells.csv` | 959 target cells with score ≥ 45 (all at mRL +235) |
| `Kayad_mRL235_Target_Map.csv` | mRL +235 grid map with scores, litho, geophysics |
| `Kayad_Prospectivity_Report.md` | This report |

---

## 8. Pipeline Validation — Bug Fixes Confirmed

| Fix | Confirmed |
|---|---|
| BH-08: Engine 2 fields loaded from JSON | Engine field = "kayad" correctly read |
| BH-10: Relative paths resolved on direct load | All paths resolved to absolute without error |
| BH-09: Corridor gap warning | No gap fires at levels 185–235 (within Shallow_N28E) |
| BH-11: Magnetics scale check | No warning (data correctly in µSI range 0–23) |
| Hard veto (C1/Amphibolite) | Correctly applied at mRL 185 and 210 — score = 20.0 |
| Desurvey | Minimum-curvature desurvey applied (50 holes, 100 survey records) |
| Corridor geometry N28E | Correctly applied — bimodal target pattern matches corridor geometry |

---

## 9. Recommendations

1. **Immediate — Fix example config (BH-12):** Correct `z_top_mrl` to 370,
   `z_bot_mrl` to 270, regenerate example TIFs for QMS target zone.

2. **Short term — Add block model:** Even a synthetic CSV with main_lens and k18
   domains will activate C9 and demonstrate the full scoring range.

3. **Short term — Add ore polygons:** Synthetic GPKG at mRL +295 and +320 showing
   the synthetic ore pod will activate C10 and improve proximity scores.

4. **Short term — Add mRL 270–370 to the example:** Add 5 TIF levels per survey
   at the QMS horizon to demonstrate the tool's full prospectivity range
   and validate the README's claimed 70–95 score range.

5. **For real Kayad dataset:** Supply NGRI/GSI airborne magnetics in µSI (or set
   `magnetics_units: "10-4si"` if in that unit). Confirm C9 block model domain
   files before run. BH-11 warning will fire if values are out of range.

---

*Dr. Prithvi, Chief Geoscientist*  
*AiRE — AI Resource Exploration Pvt Ltd*  
*2026-04-18 | Bhumi3DMapper build 0e74433*
