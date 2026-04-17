# Development History — Bhumi3DMapper

**Project:** Bhumi3DMapper — QGIS plugin for 3D mineral prospectivity mapping
**Created:** 2026-04-17
**Maintained by:** Scrummy AI
**Repository:** https://github.com/AiRE-Geo/Bhumi3Dmapper

---

### [2026-04-17||Morning] Satya → Team
**Context:** Project Initialisation
**Type:** Decision

Bhumi3DMapper v1.0.0 inherited from prior Claude.ai development session. 53 tests passing. Architecture document and autonomous dev prompt preserved. Codebase pushed to `AiRE-Geo/Bhumi3Dmapper` on GitHub.

---

### [2026-04-17||Morning] Team → Team
**Context:** Architecture review against mineral discovery objective
**Type:** Review

Full code review of all 18 source files + 8 test files. Findings:
- 4 critical issues affecting mineral discovery accuracy (desurvey missing, gravity gradient dead-code bug, polygon area wrong, PIL instead of GDAL)
- 6 Kayad-specific hardcoded items limiting multi-deposit use
- Import bugs in UI files that would crash runtime

Produced: 22 sequenced job cards (JC-01 to JC-22) in `Bhumi3DMapper_JobCards_v2.md`.

---

### [2026-04-17||S9] Team → Amit (v1.1.0)
**Context:** Sprint 9 — Foundation Fixes
**Type:** Handoff

Completed: JC-01 (imports fixed across 10 files), JC-02 (gravity gradient dead-code fix), JC-03 (z_levels float boundary fix), JC-04 (phantom test fix). 90 tests pass. Commit `376eccd`.

---

### [2026-04-17||S10] Team → Amit (v1.2.0)
**Context:** Sprint 10 — Spatial Accuracy
**Type:** Handoff

Completed: JC-05 (polygon area — Shoelace formula), JC-06 (GDAL/rasterio/PIL cascade for TIF loading), JC-07 (minimum curvature desurvey module, 6 tests). 97 tests pass. Commit `02f530f`.

Note: Desurvey module built and tested but not wired into `DrillProcessor.geology_at_level()` — deferred for geological validation against Kayad reference data.

---

### [2026-04-17||S11] Team → Amit (v1.3.0)
**Context:** Sprint 11 — Deposit-Agnostic Scoring
**Type:** Handoff

Completed: JC-08. Added `ScoringThresholdsConfig` dataclass with 47 previously-hardcoded threshold values. All 12 scoring functions in `m04_scoring_engine.py` now read from `cfg.criterion_thresholds`. Kayad defaults preserved. 97 tests pass. Commit `28db032`.

**This is the pivotal change** that transforms Bhumi3DMapper from a Kayad-only tool into a multi-deposit mineral discovery platform.

---

### [2026-04-17||S12] Team → Amit
**Context:** Sprint 12 — Test Coverage
**Type:** Handoff

Completed: JC-10 (regime transition tests), JC-12 (regression tests), JC-13 (boundary/NaN tests). 23 new tests across 7 test classes. 120 tests pass. Commit `353a770`.

**Key test additions:**
- Regime 0 (lower) and regime 1 (transition) now have coverage
- Custom threshold tests prove VMS-style configs produce different scores than SEDEX
- Amphibolite veto confirmed under both proximity and blind models

---

### [2026-04-17||S13-S15] Team → Amit
**Context:** Sprint 13-15 — Deposit Presets & Release Prep
**Type:** Handoff

Completed: JC-17 (deposit type presets). Created `core/presets/` package with:
- `sedex_pbzn.json` — SEDEX Pb-Zn (Kayad baseline)
- `vms_cuzn.json` — VMS Cu-Zn (felsic volcanic primary host)
- `epithermal_au.json` — Epithermal Au (fault-proximal scoring)
- `porphyry_cumo.json` — Porphyry Cu-Mo (large-scale proximity breaks)

Plus `loader.py` with `list_presets()`, `load_preset()`, `apply_preset()` functions. 7 preset tests including full-pipeline validation across all deposit types. 129 tests pass. Commit `8c4f546`.

Deferred to v2.1: JC-14 (nodata system), JC-15 (GPKG batch performance), JC-16 (async UI), JC-18 (config widget expansion), JC-19-22 (symbology, Qt6 port, plugin repo submission). These require QGIS runtime for integration testing.

---

### [2026-04-17||Afternoon] Team Meeting — UX for Field Geologists
**Context:** Post-v2.0 design review — usability for non-technical users
**Type:** Decision / Specification

**Objective:** Make Bhumi3DMapper usable by a field exploration geologist who has never seen JSON and works offline in a remote camp.

This discussion is preserved in full below because it is **an excellent reference for how geological software should be configured for non-technical users**, applicable across all AiRE products.

---

## UX Meeting Transcript — Making Geological Software Usable

### Satya's framing

> The tool works. 129 tests pass. Four deposit presets. But right now it requires the user to edit a JSON file to do anything meaningful. That is a deal-breaker.
>
> A field geologist in a remote exploration camp in Rajasthan or Chile or the Yukon will not open a text editor and hand-type `"criterion_thresholds"`. If we require it, the tool does not get used. Mineral discovery is the primary objective. Usability is not polish — it is the bottleneck.

### Dr. Bangaru Prithvi — Four user types

Four distinct users, each with different needs:

1. **Camp geologist (Type 1):** 30yo, working off a generator-powered laptop in -20°C or +45°C. Has drill logs in Excel, assays in CSV, TIFs from geophysics contractors. Has never heard of JSON. Workflow: receive data → point at files → generate map → show senior by morning. If the tool asks a question they cannot answer in 30 seconds, they close it.

2. **Senior project geologist (Type 2):** 15 years experience. Knows deposit types. Will happily tune weights if the UI allows. Comfortable with GIS but not programming. The power user.

3. **Exploration manager (Type 3):** Wants one-page summaries, ranked target lists, confidence intervals. Doesn't run the tool. Asks "why is target X ranked higher than Y?" — the tool must give a traceable answer.

4. **Consulting geologist (Type 4):** Works across 3-4 projects at different deposit types simultaneously. Needs fast context switching. Sensitive to friction — bills by the hour.

**All four hate surprises. All four trust the tool only if it explains what it did.**

**Critical insight:** Field geologists arrive with data in whatever form their last project used — collar files with `HOLE_ID`, `EAST`, `NORTH`, `RL` instead of `BHID`, `XCOLLAR`, etc. **The tool must accept their column names, not force them to rename.** This is the #1 friction point in geological software.

### Dr. Riya AI — Data variety across deposit types

Data formats vary by deposit style and country:
- **SEDEX Pb-Zn (India/Australia):** acQuire or Maxwell Excel exports, SGS CSV assays, Geosoft GeoTIFFs
- **VMS Cu-Zn (Canada):** Leapfrog Geo `.lfproj`, Gemcom exports
- **Epithermal Au (Latin America):** Smaller drillholes, channel samples, USS IP format
- **Orogenic Au (West Africa):** Paper logs manually entered to spreadsheets. Column names in French/Portuguese.
- **Porphyry Cu-Mo (Chile/Peru):** Hundreds of thousands of blocks from Vulcan/Micromine

Rock code terminology is also inconsistent: "QMS" = "quartz-muscovite schist" = "QSS" in different reports. **Rock code mapping must be fuzzy and suggestive, not exact-match.**

### Hema — Acceptance criteria for "easy to use"

Six measurable criteria:

1. **Time-to-First-Map (TTFM) ≤ 10 minutes** for a first-time user with valid data
2. **Zero command-line, zero text-editor, zero JSON** required
3. **Self-documenting errors** — geological language, which file/field, what to do next
4. **Progressive disclosure** — 80% of configurability hidden by default, expandable for power users
5. **Undo-able** — every action reversible, configs backed up
6. **Resumable** — long runs interruptible and restartable

### Rose AI — Data quality guardrails

**Silent data quality failures are worse than loud errors.** A TIF with wrong CRS that mis-registers by 800m = drill hole in wrong place.

Every UI path must have a *data quality preview step* before computation:
- "Found 2,112 drillholes. 47 have missing collar elevations. 3 have duplicate BHIDs. [Details] [Auto-fix] [Abort]"
- "Gravity TIFs have CRS EPSG:32643 but config says EPSG:32644. Which is correct?"
- "Assay file has 65,667 intervals. 12,445 have no ZN value. [Treat as 0] [Treat as NaN] [Skip]"

User sees this *before* the tool runs. User confirms. Then it runs.

### Deva AI — Six implementation options

| Option | Approach | Impact | Cost |
|--------|----------|--------|------|
| **A** | Point-at-a-folder autodiscovery (scans for `*collar*.csv`, `gravity/*.tif`, etc.) | Fastest TTFM | 2-4 days |
| **B** | Column mapping dialog with fuzzy match + data preview ("XCOLLAR → 'EAST'?") | Solves #1 pain point | 3-5 days |
| **C** | Deposit type chooser as Step 1 (SEDEX/VMS/Epithermal/Porphyry cards) | Right defaults immediately | 1-2 days |
| **D** | Drag-and-drop data cards for each data type | Visual, tactile | 4-10 days |
| **E** | Excel template download/upload workflow | Geologists live in Excel | 2-4 days |
| **F** | Bundled example project ("Run the example" → map in 30s) | Eliminates blank-page paralysis | 1-2 days |

### Lala — ROI analysis and scope veto

Deva's cost estimates underestimated by ~2×. Honest budget:

| Option | Impact on TTFM | Honest cost | ROI |
|--------|----------------|-------------|-----|
| A | -5 min | 4 days | Very high |
| B | -3 min (catches column mismatch) | 5 days | High |
| C | -2 min + prevents wrong deposit model | 2 days | Very high |
| F | -8 min (first-timer confidence) | 2 days | Very high |
| D | -1 min (polish) | 10 days | Low |
| E | 0 min (parallel path) | 4 days | Low |

**Veto on D and E for v2.0** — CSV is already the template. A + B + C + F = 13 days and delivers the 10-minute TTFM target.

### Gandalf QA — Seven failure modes (all blockers)

1. **Folder autodiscovery matches wrong file** (`collar_v1.csv`, `collar_v2.csv`, `collar_FINAL_FINAL.csv`) → must ask user
2. **Column mapping dialog gets ignored** (user clicks OK without reading) → must show actual data preview with value ranges
3. **Deposit type picked wrong** (SEDEX selected for VMS project) → post-load sanity check: "Your rocks: 70% volcanic. SEDEX expects >60% sediment host. Reconsider?"
4. **Example project treated as real output** → red banner "EXAMPLE DATA — NOT YOUR PROJECT"
5. **Progressive disclosure hides critical defaults** → show 3 most important prominently: deposit type, hard veto rock, target levels
6. **CSV encoding breaks** (Latin-1, UTF-8-BOM, Windows-1252 across countries) → auto-detect
7. **Paths with spaces/non-ASCII** (`C:\Users\Perea Ríos\Proyecto Añasagasti\`) → must work

### Vimal AI — Operational reality

1. **Geologists work offline** — remote camps have no internet. Plugin must bundle everything. No runtime pip installs, no API calls. Example project bundled inside plugin.
2. **90% Windows laptops** — path length limits, file locking quirks accounted for.
3. **They will not update** — installed v2.0 used for a year. **v2.0 must be correct at release**, not patched later.

### Dr. Riya AI — Contextual geological help

Tooltips with deposit-type-specific geological examples. Hovering "Structural marker code" in VMS preset shows: *"In VMS deposits, typically the stringer zone or felsic-mafic contact. At Kidd Creek = rhyolite-basalt. At Neves-Corvo = volcaniclastic unit. What is the equivalent in your project?"*

Makes the tool useful for Type 3 (exploration manager) who asks "why." **If the tool can explain its geological choices, it's trusted. If not, it's ignored.**

### Satya's closing decisions

1. **Sprint 16 approved.** JC-23 through JC-30 (8 cards) ship as v2.0 UX release.
2. **Lala's veto stands.** Drag-drop (D) and Excel templates (E) deferred to v2.1.
3. **Tooltips (JC-30) added.** 3 days, parallel with engineering.
4. **Gandalf's 7 failure modes become acceptance test requirements.** No hand-waving.
5. **Rose's data quality preview (JC-28) is a HARD GATE.** Scoring does not run until user accepts the data quality report.
6. **The JSON config stays** as serialisation format, saved automatically, never shown by default. Power users can still edit it.
7. **Zero JSON in the wizard flow.** Quick Start must complete end-to-end without user seeing "JSON" or a text editor.
8. **TTFM target: 10 minutes.** Gandalf designs test scenario, times it post-S16. Iterate if missed.

**Dr. Prithvi's point about column naming (JC-24) is the most important technical constraint. A tool that fails because a file says "EAST" instead of "XCOLLAR" is a broken tool. Prioritise it.**

### Sprint 16 Job Cards

| JC | Title | Effort |
|----|-------|--------|
| **JC-23** | Folder autodiscovery | 4 days |
| **JC-24** | Column mapping dialog — fuzzy match + data preview | 5 days |
| **JC-25** | Deposit type chooser + post-load sanity check | 2 days |
| **JC-26** | Bundled example project (synthetic Kayad-style) | 2 days |
| **JC-27** | Plain-language error messages (no stack traces) | 3 days |
| **JC-28** | Data quality preview screen (HARD GATE) | 4 days |
| **JC-29** | CSV encoding auto-detection | 1 day |
| **JC-30** | Contextual geological tooltips per preset | 3 days |

Total: 24 person-days, parallelisable to ~12 calendar days.

### Ranked UX Options for Non-Technical Field Geologists

This ranking applies broadly to any geological software targeting field users:

| Rank | Approach | Why it matters |
|------|----------|---------------|
| 1 | **Column mapping with fuzzy match + data preview** | Eliminates #1 friction — arbitrary column names |
| 2 | **Folder autodiscovery** | One click instead of 8 file dialogs |
| 3 | **Deposit type chooser + post-load sanity check** | Right defaults; flags wrong-model selections |
| 4 | **Data quality preview before run** | Prevents silent wrong outputs (worst failure mode) |
| 5 | **Bundled example project** | Confidence + learning tool |
| 6 | **Plain-language errors with action guidance** | Geologists can unblock themselves |
| 7 | **CSV encoding auto-detection** | Works in any country |
| 8 | **Contextual geological help (tooltips)** | Builds trust, explains choices |
| 9 | Drag-and-drop data cards *(deferred)* | Polish; not critical |
| 10 | Excel template workbook *(deferred)* | Parallel path; CSV already works |

---

### Design Principles for Geological Software (Generalised Lessons)

These principles emerged from this meeting and apply to all AiRE tools targeting exploration geologists:

1. **Accept data in the geologist's format, not ours.** Column name remapping is mandatory, not optional.
2. **Deposit type is the primary context.** Ask first, let it drive all defaults.
3. **Data quality preview before computation.** Silent errors are catastrophic in exploration — a misregistered grid places drill holes hundreds of metres off.
4. **Offline-first.** Bundle everything. No runtime downloads, no API dependencies. Remote camps have no internet.
5. **Progressive disclosure.** Hide 80% by default. Show 3 critical defaults prominently. Expose everything to power users.
6. **Self-explaining outputs.** Every score must be traceable to observable data. "Why is this target ranked?" must have an answer.
7. **Config files are serialisation, not UI.** Never require a user to open a JSON/YAML file. Save them automatically.
8. **Plain-language errors in geological terms.** "Your file is missing the Zn grade column" not "KeyError: 'ZN'".
9. **Bundled example for instant success.** Eliminates blank-page paralysis and proves the tool works.
10. **Correctness over speed.** Users install once and use for a year. Ship correct, not fast.

---

## End of UX Meeting Log
