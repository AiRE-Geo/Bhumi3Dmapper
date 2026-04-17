# Bhumi3DMapper Sprint 16 — Field Geologist UX Job Cards

> **Sprint:** S16 — "The 10-Minute Geologist"  
> **Objective:** A field geologist who has never seen the tool produces their first scored map in ≤ 10 minutes, without opening a JSON file  
> **Duration:** 2 weeks (~12 calendar days with parallelisation, ~24 person-days total)  
> **Lead:** Satya  
> **Sprint Master:** Scrummy AI  
> **Reference:** Team meeting 2026-04-17, logged in `docs/DevelopmentHistory_Bhumi3DMapper.md`

---

## Sprint Context

After completing S9–S15 (technical foundation, deposit-agnostic scoring, 129 tests passing), the tool is technically sound but requires JSON editing for meaningful use. The team held a UX review and identified 8 job cards that transform Bhumi3DMapper from an engineer's tool into a geologist's tool.

**Primary user:** Dr. Prithvi's Type 1 "Camp geologist" — 30 y.o., off-grid laptop, Excel/CSV workflow, 30-second attention span.

**TTFM target:** 10 minutes from plugin install to first scored prospectivity map.

**Hard gate:** Scoring does not run until the data quality preview has been accepted by the user.

---

## Dependency Graph

```
JC-23 (autodiscovery) ────────────┐
                                   │
JC-24 (column mapping) ──────┐     │
                              │     │
JC-25 (deposit chooser) ──┐   │     │
                           │   │     │
JC-29 (CSV encoding) ──┐   │   │     │
                        ▼   ▼   ▼     ▼
                   JC-28 (Data Quality Preview — HARD GATE)
                              │
                              ▼
                    Existing scoring pipeline
                              │
JC-26 (example project) ──────┤
JC-27 (plain-lang errors) ────┤  (cross-cutting — apply everywhere)
JC-30 (tooltips) ─────────────┘
```

---

## JC-23: Folder Autodiscovery

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2), Rose AI (G2.5)  
**Effort:** 4 days  
**Priority:** HIGH  
**Depends on:** None (new UI component)

### Problem

Today a user must manually specify 5+ file paths (collar CSV, assay CSV, litho CSV, gravity folder, magnetics folder) through separate file dialogs. This is 5 context switches and 5 opportunities to pick the wrong file.

Field geologists organise their project data in folders with consistent naming conventions:
```
MyProject/
├── drillholes/
│   ├── collar.csv
│   ├── assay.csv
│   └── litho.csv
├── geophysics/
│   ├── gravity/
│   │   ├── grav_185.tif
│   │   └── ...
│   └── magnetics/
│       ├── mag_185.tif
│       └── ...
└── ore_polygons/
    └── ore_*.gpkg
```

### Solution

Add a "Point at project folder" button in the wizard Welcome page and dock panel. User selects a single folder; the tool recursively scans for common patterns and auto-populates the config.

### Implementation

**New file:** `modules/m08_autodiscover.py` (pure Python, no QGIS)

```python
"""Module 08 — Project folder autodiscovery.
Scans a project root folder for drill, geophysics, and polygon files using
common naming conventions. Returns a populated ProjectConfig.
Pure Python, no QGIS imports.
"""
import os, re, glob
from typing import Dict, List, Optional, Tuple

# Patterns in priority order (first match wins)
COLLAR_PATTERNS   = ['collar*.csv', '*_collar.csv', 'hole*.csv', 'holes.csv', 'drillhole*.csv']
ASSAY_PATTERNS    = ['assay*.csv', '*_assay.csv', 'grade*.csv', 'samples*.csv']
LITHO_PATTERNS    = ['litho*.csv', '*_litho.csv', 'geology*.csv', 'lithology*.csv']
SURVEY_PATTERNS   = ['survey*.csv', '*_survey.csv', 'deviation*.csv']

GRAVITY_FOLDER_PATTERNS    = ['grav*', '*gravity*', 'gr_*']
MAGNETICS_FOLDER_PATTERNS  = ['mag*', '*magnetic*', '*susceptibility*', 'ms_*']
POLYGON_FOLDER_PATTERNS    = ['ore*', 'mineral*', 'polygons*', 'lenses*']


def autodiscover(project_root: str) -> Dict[str, any]:
    """
    Scan project_root recursively; return dict of discovered paths.
    
    Returns:
        {
            'collar_csv': str or None,
            'assay_csv': str or None,
            'litho_csv': str or None,
            'survey_csv': str or None,
            'gravity_folder': str or None,
            'magnetics_folder': str or None,
            'polygon_folder': str or None,
            'ambiguous': List[Dict],  # multiple matches needing user resolution
            'warnings': List[str],
        }
    """
    ...

def apply_to_config(cfg, discovered: dict):
    """Apply discovered paths to a ProjectConfig, returning list of changes made."""
    ...
```

### Acceptance Criteria

1. **Finds standard layout in one call.** Test project with `drillholes/collar.csv`, `drillholes/litho.csv`, `geophysics/gravity/*.tif`, `geophysics/magnetics/*.tif` produces all 5 paths correctly.
2. **Case-insensitive matching.** `COLLAR.CSV`, `Collar.csv`, `collar.CSV` all match.
3. **Handles non-standard but reasonable layouts.** `Drill_Data/BHID_locations.csv` is found and reported as a "possible match" needing user confirmation.
4. **Reports ambiguity, does not guess.** When multiple candidates exist (`collar_v1.csv`, `collar_v2.csv`, `collar_FINAL.csv`), returns all three with modification dates and lets user pick. **Gandalf failure mode #1 gate.**
5. **Handles non-ASCII and spaced paths.** `C:\Proyectos\Añasagasti\Drilling 2025\collar.csv` works.
6. **Returns structured warnings, not exceptions.** Missing expected folder → warning, not crash.
7. **UI integration:** New `QPushButton("Scan Project Folder")` in `WelcomePage` (wizard) and dock panel. Opens `QFileDialog.getExistingDirectory()`, runs autodiscover, shows results in modal review dialog before applying.
8. **Review dialog shows every discovered path** with a checkbox (✓ Apply / ✗ Skip) and the ambiguous matches as radio buttons.
9. **7 new tests** in `test/test_autodiscover.py` covering: standard layout, case variations, ambiguous collar files, missing geophysics folder, non-ASCII paths, empty folder, non-existent root.

### Files

**Create:**
- `modules/m08_autodiscover.py` (~150 lines)
- `test/test_autodiscover.py` (~150 lines)
- `ui/autodiscover_dialog.py` (~120 lines — the review modal)

**Modify:**
- `ui/wizard.py` — add "Scan Folder" button to WelcomePage
- `ui/dock_panel.py` — add "Scan Folder" button next to Load/New

### Geological Review (Dr. Prithvi / Dr. Riya)

- What filename patterns do geologists actually use? Validate the pattern lists against 5+ real-world project folders from different deposits/countries.
- Should autodiscover prefer "most recent file" or "alphabetically last" when there are multiple matches? (Current plan: show all, let user pick.)

---

## JC-24: Column Mapping Dialog with Fuzzy Match and Data Preview

**Assigned to:** Deva AI  
**Reviewed by:** Hema (spec lead), Gandalf QA (G2), Rose AI (G2.5 — data validation), Dr. Prithvi (G3)  
**Effort:** 5 days  
**Priority:** CRITICAL — this is Dr. Prithvi's #1 friction point  
**Depends on:** None (can run in parallel with JC-23)

### Problem

The tool currently hard-requires these column names in drill CSVs: `BHID`, `XCOLLAR`, `YCOLLAR`, `ZCOLLAR`, `DEPTH`, `FROM`, `TO`, `ROCKCODE`, `BRG`, `DIP`, `ZN`, `PB`, `AG`.

Real-world data uses: `HOLE_ID`, `EAST`, `NORTH`, `RL`, `ELEV`, `MAX_DEPTH`, `FROM_M`, `TO_M`, `LITH`, `ROCK_TYPE`, `AZI`, `INCL`, `Zn_pct`, `Pb_ppm`, etc.

Currently the user must pre-process their CSVs to rename columns. This is the #1 reason geologists abandon technical tools.

### Solution

When the user loads a CSV, the tool:
1. Reads the header row and the first 5 data rows
2. Fuzzy-matches each required field against the detected columns
3. Shows a modal dialog with a 2-column table: **Required field** → **Detected column (editable dropdown)**
4. Shows a data preview panel with the first 5 rows and the value range of each column (min/max/sample)
5. User confirms or adjusts mapping
6. The mapping is saved to config (new `DrillDataConfig.column_mapping` field) — applied on every load

### Implementation

**New module:** `modules/m09_column_mapper.py` (pure Python)

```python
"""Fuzzy column name matching for user data files."""
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple
import pandas as pd


# Aliases organised by required field
FIELD_ALIASES = {
    'col_bhid':    ['bhid', 'hole_id', 'holeid', 'dhid', 'drillhole', 'hole', 'borehole'],
    'col_xcollar': ['xcollar', 'east', 'easting', 'x', 'x_collar', 'utm_east'],
    'col_ycollar': ['ycollar', 'north', 'northing', 'y', 'y_collar', 'utm_north'],
    'col_zcollar': ['zcollar', 'rl', 'elev', 'elevation', 'z', 'z_collar', 'altitude'],
    'col_depth':   ['depth', 'max_depth', 'total_depth', 'td', 'eoh'],
    'col_from':    ['from', 'from_m', 'depth_from', 'top', 'start_m'],
    'col_to':      ['to', 'to_m', 'depth_to', 'bottom', 'end_m'],
    'col_rockcode':['rockcode', 'rock_code', 'lith', 'lithology', 'rock_type', 'litho'],
    'col_azimuth': ['brg', 'bearing', 'azimuth', 'azi', 'az'],
    'col_dip':     ['dip', 'incl', 'inclination', 'angle'],
    'col_zn':      ['zn', 'zn_pct', 'zn_ppm', 'zinc', 'zn_grade'],
    'col_pb':      ['pb', 'pb_pct', 'pb_ppm', 'lead', 'pb_grade'],
    'col_ag':      ['ag', 'ag_ppm', 'ag_gt', 'silver', 'ag_grade'],
}


def fuzzy_match(required_field: str, available_columns: List[str],
                 threshold: float = 0.70) -> List[Tuple[str, float]]:
    """
    Return list of (column_name, confidence) ranked by fuzzy similarity.
    Only returns matches above threshold.
    """
    aliases = FIELD_ALIASES.get(required_field, [required_field])
    scored = []
    for col in available_columns:
        best = max(SequenceMatcher(None, col.lower(), a.lower()).ratio()
                   for a in aliases)
        if best >= threshold:
            scored.append((col, best))
    return sorted(scored, key=lambda x: -x[1])


def auto_map(required_fields: List[str],
             available_columns: List[str]) -> Dict[str, Optional[str]]:
    """
    Attempt to map every required field to a best-matching column.
    Returns dict {required_field: matched_column or None}.
    """
    mapping = {}
    used = set()
    for field in required_fields:
        candidates = fuzzy_match(field, available_columns)
        for col, score in candidates:
            if col not in used:
                mapping[field] = col
                used.add(col)
                break
        else:
            mapping[field] = None
    return mapping


def preview_data(df: pd.DataFrame, column: str, n_rows: int = 5) -> Dict:
    """Return a summary dict: sample values, min, max, unique count, dtype."""
    col_data = df[column]
    return {
        'sample': col_data.head(n_rows).tolist(),
        'min': col_data.min() if pd.api.types.is_numeric_dtype(col_data) else None,
        'max': col_data.max() if pd.api.types.is_numeric_dtype(col_data) else None,
        'n_unique': col_data.nunique(),
        'n_null': int(col_data.isna().sum()),
        'dtype': str(col_data.dtype),
    }
```

**New UI dialog:** `ui/column_mapper_dialog.py`

A `QDialog` with:
- A `QTableWidget` with 4 columns: Required Field | Detected Column | Confidence | Preview
- "Detected Column" is a `QComboBox` populated with all available CSV columns
- "Confidence" is a coloured indicator: green (>0.85), amber (0.70-0.85), red (<0.70 or unmapped)
- "Preview" button opens a popover showing the column's sample values and min/max range
- A "Validate and Apply" button that only enables when all required fields are mapped
- A "Save mapping for future projects" checkbox

**Config extension:** Add to `DrillDataConfig`:
```python
column_mapping: Dict[str, str] = field(default_factory=dict)
```

When present, overrides default column names. When empty, falls back to defaults.

**Load path integration:** `DataLoader.load_collar()` / `load_litho()` / `load_assay()` must use `cfg.drill.column_mapping.get(field, default)` for every column access.

### Acceptance Criteria

1. **Fuzzy match recognises common aliases.** `HOLE_ID` → `col_bhid`, `EAST` → `col_xcollar`, `Zn_pct` → `col_zn` — all without user intervention.
2. **Low-confidence matches surface for user review.** A column `Pb_assay_ppm` matches `col_pb` with amber confidence — user confirms.
3. **Unmapped required fields block advancement.** "Validate and Apply" button disabled until all mandatory fields (BHID, coords, depth, from, to) have a mapping.
4. **Optional fields can be skipped.** `col_ag` (silver) can be left unmapped without blocking.
5. **Data preview shows actual values.** Click preview on `XCOLLAR` mapping → shows "Sample: 468655.2, 468712.1, ... | Range: 468655 to 470234". **Gandalf failure mode #2 gate.**
6. **Value range sanity check.** If a column mapped to `col_xcollar` has values ranging 0-90, warn: "This looks like latitude. Is your data in decimal degrees instead of UTM?"
7. **Mapping persists in config JSON.** Round-trip test: save mapping → reload config → mapping preserved.
8. **Backwards compatible.** Projects without `column_mapping` field still work using default column names.
9. **12 new tests** in `test/test_column_mapper.py` covering: exact match, fuzzy match, alias match, no match, ambiguous match (2 columns equally similar), preview statistics, auto_map prevents double-use of same column, value range sanity check.
10. **Internationalisation-ready.** Aliases list is extensible — French/Portuguese/Spanish aliases can be added in a follow-up without code changes.

### Files

**Create:**
- `modules/m09_column_mapper.py` (~120 lines)
- `ui/column_mapper_dialog.py` (~200 lines)
- `test/test_column_mapper.py` (~180 lines)

**Modify:**
- `core/config.py` — add `column_mapping` field to `DrillDataConfig`
- `modules/m01_data_loader.py` — use `cfg.drill.column_mapping.get(...)` in all load methods
- `ui/wizard.py` — show column mapper dialog automatically after CSV is selected
- `ui/dock_panel.py` — expose "Remap Columns" action

### Geological Review (Dr. Prithvi / Dr. Riya)

- **Required:** Dr. Prithvi to supply the alias list from 10+ real-world drill databases. The FIELD_ALIASES dict in the implementation is a starting point and must be validated.
- Dr. Riya to add aliases for non-English conventions (`ECHANT` = sample in French, `PROFONDEUR` = depth).
- Value range sanity rules: what ranges indicate the user has entered wrong data? Dr. Prithvi to define 5+ rules (e.g., "Zn_pct > 50 probably means ppm was miscoded as pct").

---

## JC-25: Deposit Type Chooser + Post-Load Sanity Check

**Assigned to:** Deva AI  
**Reviewed by:** Dr. Prithvi (G3 — sanity rules are geological), Gandalf QA (G2)  
**Effort:** 2 days  
**Priority:** HIGH  
**Depends on:** S13-15 presets system (already built)

### Problem

The current UI has a deposit type dropdown in `config_widget.py` but it does not actually load a preset — it just stores a string. Users select "VMS Cu-Zn" but scoring still uses SEDEX defaults. Dr. Prithvi also flagged that users pick the wrong deposit type (Gandalf failure mode #3) — the tool should catch this post-load.

### Solution

**Two-part change:**

1. **Step 1 of wizard becomes "What are you exploring for?"** — visual cards, one per preset. Selecting a card immediately calls `apply_preset()` on the config, loading all 47 thresholds.

2. **After data is loaded, run a sanity check** that compares the detected lithology composition against what the preset expects. If mismatch, surface a warning with actionable options.

### Implementation

**New UI component:** `ui/deposit_chooser_page.py` — replaces or prepends `WelcomePage` in wizard.

```python
class DepositChooserPage(QWizardPage):
    """Visual deposit type selector — the first thing a geologist sees."""
    
    def __init__(self):
        super().__init__()
        self.setTitle(tr('What are you exploring for?'))
        self.setSubTitle(tr('Choose your deposit type. This sets geologically appropriate defaults that you can tune later.'))
        
        # 2×2 grid of preset cards
        grid = QGridLayout(self)
        self.preset_cards = {}
        
        presets = [
            ('sedex_pbzn',    'SEDEX Pb-Zn',       '🔴', 'Sedimentary-exhalative lead-zinc\n(Kayad, Mt Isa, Rampura)'),
            ('vms_cuzn',      'VMS Cu-Zn',         '🟢', 'Volcanogenic massive sulphide\n(Kidd Creek, Neves-Corvo)'),
            ('epithermal_au', 'Epithermal Au',     '🟡', 'Low-sulphidation gold-silver\n(Hishikari, Waihi)'),
            ('porphyry_cumo', 'Porphyry Cu-Mo',    '🔵', 'Porphyry copper-molybdenum\n(El Teniente, Chuquicamata)'),
            ('custom',        'Custom / Unknown',  '⚪', 'I will configure thresholds myself\nor load an existing config'),
        ]
        
        for i, (key, name, icon, desc) in enumerate(presets):
            card = self._make_card(icon, name, desc)
            card.clicked.connect(lambda _=None, k=key: self._on_select(k))
            self.preset_cards[key] = card
            grid.addWidget(card, i // 2, i % 2)
        
        self.registerField('deposit_preset*', self, 'preset_name',
                           b'presetChanged(QString)')
```

**New sanity check:** `modules/m10_sanity.py`

```python
"""Post-load geological sanity checks.
After data is loaded, compare detected characteristics against what the
selected deposit preset expects. Flag mismatches for user review.
"""
def check_deposit_type_match(cfg, litho_df) -> List[Dict]:
    """
    Returns list of warnings. Each warning:
        {
            'severity': 'info' | 'warning' | 'critical',
            'message': str,
            'suggestion': str,
            'actions': List[str],  # e.g. ['Switch preset', 'Ignore', 'Remap codes']
        }
    """
    warnings = []
    
    # Count lithology codes
    counts = litho_df['lcode'].value_counts(normalize=True)
    
    # Sanity rules by deposit type
    if cfg.deposit_type == 'SEDEX Pb-Zn':
        # Expect >60% code 1 (QMS-like) or code 4 (CSR-like)
        host_fraction = counts.get(1, 0) + counts.get(4, 0)
        if host_fraction < 0.40:
            warnings.append({
                'severity': 'warning',
                'message': f'Your drill data shows {100*host_fraction:.0f}% host rock. '
                           f'SEDEX typically has >60% host rock.',
                'suggestion': 'Your deposit may not be SEDEX. Consider VMS or other presets.',
                'actions': ['Switch preset', 'Remap rock codes', 'Continue anyway'],
            })
    elif cfg.deposit_type == 'VMS Cu-Zn':
        # Expect significant felsic volcanic (code 5)
        felsic_fraction = counts.get(5, 0)
        if felsic_fraction < 0.20:
            warnings.append({
                'severity': 'warning',
                'message': f'Your drill data shows only {100*felsic_fraction:.0f}% felsic volcanic. '
                           f'VMS deposits are typically hosted in felsic-dominated sequences.',
                'suggestion': 'Check rock code mapping, or consider a different preset.',
                'actions': ['Switch preset', 'Remap rock codes', 'Continue anyway'],
            })
    # ... similar for Epithermal and Porphyry
    
    return warnings
```

### Acceptance Criteria

1. **Deposit chooser is Step 1 of wizard.** User sees it before any data entry.
2. **Card click applies preset.** `cfg.criterion_thresholds` is updated immediately; all 47 thresholds match the preset.
3. **Custom card preserves current config.** No preset applied; user falls through to manual config flow.
4. **Post-load sanity check runs automatically** after `DataLoader.load_litho()` completes.
5. **Sanity warnings show actionable buttons.** User can: switch preset (applies new preset, keeps data), remap rock codes (opens JC-24 dialog), or continue anyway (logged in audit trail).
6. **Known-good case produces no warnings.** Kayad synthetic data with SEDEX preset → zero warnings. **Gandalf failure mode #3 gate.**
7. **Known-bad case produces warning.** Kayad synthetic data with Porphyry preset → warning about felsic expectation vs. detected composition.
8. **"Continue anyway" logged.** Written to config as `cfg.audit.overrides = ['deposit_type_sanity_ignored']`.
9. **5 new tests** in `test/test_sanity.py` covering: each preset's sanity rule with matching and mismatching data.

### Files

**Create:**
- `ui/deposit_chooser_page.py` (~180 lines)
- `modules/m10_sanity.py` (~120 lines)
- `test/test_sanity.py` (~100 lines)

**Modify:**
- `ui/wizard.py` — insert `DepositChooserPage` as first page
- `core/presets/loader.py` — add 'custom' preset handling (no-op)
- `algorithms/alg_load_data.py` — run sanity check after litho load

### Geological Review (Dr. Prithvi — REQUIRED)

- Dr. Prithvi to review and extend the sanity rules per preset. Current implementation has minimal rules. Need 3-5 rules per deposit type.
- Dr. Riya to add deposit-type-specific warnings (e.g., Epithermal: "No silicification code detected").

---

## JC-26: Bundled Example Project

**Assigned to:** Deva AI  
**Reviewed by:** Dr. Prithvi (G3 — example must be geologically plausible), Gandalf QA (G2)  
**Effort:** 2 days  
**Priority:** HIGH — eliminates blank-page paralysis  
**Depends on:** None

### Problem

First-time users have no reference for what a "correct" setup looks like. They open the tool, see empty fields, and don't know what goes where. They close the tool.

### Solution

Ship a complete example project inside the plugin. Add an "Open Example Project" button that loads the example in 1 click and runs the full pipeline to produce an example map in ~30 seconds.

**Every example output must carry a visual "EXAMPLE DATA — NOT YOUR PROJECT" banner** to prevent user confusion (Gandalf failure mode #4).

### Implementation

**New directory:** `bhumi3dmapper/examples/kayad_synthetic/`

Contents:
- `config.json` — complete, valid config with paths relative to example folder
- `data/collar.csv` — 50 synthetic boreholes in Kayad grid extent
- `data/litho.csv` — 500 litho intervals with realistic SEDEX distribution (QMS host + PG + CSR)
- `data/assay.csv` — 200 assay intervals with Zn, Pb grades
- `data/survey.csv` — vertical and inclined holes for desurvey testing
- `geophysics/gravity/grav_185.tif` — 50×50 synthetic gravity TIF
- `geophysics/gravity/grav_210.tif`
- `geophysics/gravity/grav_235.tif`
- `geophysics/magnetics/mag_185.tif` — 10×10 synthetic mag
- `geophysics/magnetics/mag_210.tif`
- `geophysics/magnetics/mag_235.tif`
- `README.md` — describes what this example demonstrates

**New module:** `modules/m11_example.py`

```python
"""Example project loader — copies bundled example data to a user-chosen location."""
import os, shutil
from pathlib import Path

EXAMPLE_DIR = Path(__file__).parent.parent / 'examples' / 'kayad_synthetic'

def copy_example_project(target_dir: str) -> str:
    """Copy the bundled example to target_dir. Returns path to config.json."""
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(EXAMPLE_DIR, target / 'kayad_example', dirs_exist_ok=True)
    return str(target / 'kayad_example' / 'config.json')
```

**UI integration:** New "Try Example Project" button in `WelcomePage`:
```python
btn_example = QPushButton(tr('🎓 Try Example Project (30 seconds)'))
btn_example.setToolTip(tr(
    'Loads a synthetic SEDEX Pb-Zn dataset and runs the full pipeline. '
    'Produces an example map to verify the tool works on your machine. '
    'Results are clearly marked EXAMPLE DATA.'
))
```

**Banner injection:** Modify `m05_gpkg_writer.py` to add an `is_example` flag in the GPKG metadata when writing example outputs. `alg_load_results.py` reads this flag and adds a layer group name like `"⚠️ EXAMPLE — NOT YOUR DATA"` and sets layer opacity to 60%.

### Acceptance Criteria

1. **Example ships inside plugin.** Plugin ZIP contains `examples/kayad_synthetic/` with all files. No runtime download.
2. **Total example size < 2 MB.** Synthetic TIFs compressed.
3. **"Try Example" completes in ≤ 30 seconds** on a 2020-era laptop. User sees a scored GPKG in QGIS within 30s of clicking.
4. **Example outputs are visually marked.** Layer group titled "⚠️ EXAMPLE DATA — NOT YOUR PROJECT" in QGIS layer tree. **Gandalf failure mode #4 gate.**
5. **Example runs SEDEX preset.** Scores for primary host cells should be 70-95 (verified in integration test).
6. **README.md in example folder** explains the synthetic data: grid extent, number of holes, expected outputs.
7. **Example dir is copied to user-chosen location** (not run in-place inside the plugin folder — avoids write permissions issues).
8. **3 new tests** in `test/test_example.py`: example copies correctly, config loads, full pipeline runs on example data in <60s.

### Files

**Create:**
- `examples/kayad_synthetic/config.json`
- `examples/kayad_synthetic/data/*.csv` (4 files)
- `examples/kayad_synthetic/geophysics/gravity/*.tif` (3 files)
- `examples/kayad_synthetic/geophysics/magnetics/*.tif` (3 files)
- `examples/kayad_synthetic/README.md`
- `modules/m11_example.py` (~40 lines)
- `test/test_example.py` (~80 lines)
- Synthetic data generator script: `scripts/generate_example_data.py` (Dr. Prithvi to review)

**Modify:**
- `ui/wizard.py` — add "Try Example" button to WelcomePage
- `modules/m05_gpkg_writer.py` — add `is_example` metadata flag
- `algorithms/alg_load_results.py` — detect example flag, apply banner styling

### Geological Review (Dr. Prithvi — REQUIRED)

- Dr. Prithvi to review the synthetic data for geological plausibility. The example should look like a believable SEDEX deposit: QMS host, PG halo, CSR at depth, gravity-negative ore zone.
- The synthetic geophysics must show the expected signatures. Random noise won't teach anything — the example must demonstrate the scoring model working on realistic-looking data.

---

## JC-27: Plain-Language Error Messages

**Assigned to:** Deva AI  
**Reviewed by:** Hema (plain English quality), Gandalf QA (G2)  
**Effort:** 3 days  
**Priority:** HIGH (cross-cutting — touches many files)  
**Depends on:** None (can run in parallel)

### Problem

Current error messages expose Python internals to geologists:
- `KeyError: 'XCOLLAR'` (meaningless to a non-programmer)
- `FileNotFoundError: [Errno 2] No such file or directory: 'X:/data/collar.csv'`
- `IndexError: list index out of range` (from various scoring bugs)

Geologists see these, panic, and either give up or report opaque bugs that developers can't reproduce.

### Solution

Wrap every user-facing error in a plain-language translation. Every error message must contain:
1. **What went wrong** (in geological/workflow terms, not Python terms)
2. **Where** (which file, which step)
3. **What to do next** (specific action)
4. **Technical details hidden by default** (click "Show details" to see stack trace)

### Implementation

**New module:** `core/errors.py`

```python
"""User-facing error translation layer."""
from typing import Optional


class UserError(Exception):
    """Exception with a user-facing message and suggested action."""
    def __init__(self, message: str, suggestion: str,
                  technical: Optional[Exception] = None,
                  severity: str = 'error'):
        self.message = message
        self.suggestion = suggestion
        self.technical = technical
        self.severity = severity  # 'info' | 'warning' | 'error' | 'critical'
        super().__init__(f"{message} — {suggestion}")


# Translation registry: Python exception class → translation function
def translate(exc: Exception, context: str = '') -> UserError:
    """Translate a raw exception into a user-friendly UserError."""
    msg = str(exc)
    
    if isinstance(exc, FileNotFoundError):
        path = exc.filename or ''
        return UserError(
            message=f"Cannot find file: {path}",
            suggestion=(
                "Check that the path is correct and the file exists. "
                "If your project folder was moved, update the config or "
                "use 'Scan Project Folder' to re-detect paths."
            ),
            technical=exc,
        )
    
    if isinstance(exc, KeyError):
        col = str(exc).strip("'\"")
        return UserError(
            message=f"Missing required column: {col}",
            suggestion=(
                f"Your CSV does not have a column named '{col}'. "
                f"Use 'Remap Columns' to point to the equivalent column in your file, "
                f"or rename the column in your CSV."
            ),
            technical=exc,
        )
    
    if isinstance(exc, pd.errors.EmptyDataError):
        return UserError(
            message=f"The file is empty: {context}",
            suggestion="Check the file in Excel. An empty CSV usually means the "
                      "export failed — re-export from your drill database.",
            technical=exc,
        )
    
    if isinstance(exc, PermissionError):
        return UserError(
            message=f"Cannot read/write: {exc.filename}",
            suggestion=(
                "The file may be open in another program (Excel, QGIS). "
                "Close it and try again."
            ),
            technical=exc,
        )
    
    if isinstance(exc, UnicodeDecodeError):
        return UserError(
            message=f"Cannot read the file — unusual character encoding",
            suggestion=(
                "Your CSV uses a non-standard text encoding. "
                "Open it in Excel and re-save as 'CSV UTF-8'."
            ),
            technical=exc,
        )
    
    # Generic fallback
    return UserError(
        message=f"Unexpected problem: {msg}",
        suggestion=(
            "This is likely a bug. Check the 'Show technical details' for the "
            "full error, and report it at https://github.com/AiRE-Geo/Bhumi3Dmapper/issues"
        ),
        technical=exc,
        severity='critical',
    )
```

**Error display dialog:** `ui/error_dialog.py`

```python
class GeologistErrorDialog(QDialog):
    """Plain-language error dialog with collapsible technical details."""
    def __init__(self, error: UserError, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Bhumi3DMapper')
        
        layout = QVBoxLayout(self)
        
        # Icon + severity-coloured header
        header = QLabel(f"❗ {error.message}" if error.severity == 'error' 
                         else f"⚠️ {error.message}")
        header.setStyleSheet('font-size: 14pt; font-weight: bold; color: '
                              + ('#c00' if error.severity == 'error' else '#c80'))
        layout.addWidget(header)
        
        # What to do
        suggestion = QLabel(f"<b>What to do:</b><br>{error.suggestion}")
        suggestion.setWordWrap(True)
        layout.addWidget(suggestion)
        
        # Collapsible technical details
        if error.technical:
            self.details_btn = QPushButton('▶ Show technical details (for reports)')
            self.details_btn.setCheckable(True)
            self.details_btn.toggled.connect(self._toggle_details)
            layout.addWidget(self.details_btn)
            
            self.details_text = QTextEdit()
            self.details_text.setPlainText(
                f"{type(error.technical).__name__}: {error.technical}\n\n" +
                traceback.format_exc())
            self.details_text.setReadOnly(True)
            self.details_text.setVisible(False)
            layout.addWidget(self.details_text)
        
        # Buttons
        btn_box = QHBoxLayout()
        btn_copy = QPushButton('Copy details')
        btn_copy.clicked.connect(self._copy_details)
        btn_close = QPushButton('Close')
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_copy)
        btn_box.addStretch()
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)
```

### Acceptance Criteria

1. **All user-facing error paths use `translate()`.** `dock_panel.py`, `wizard.py`, `alg_*.py` wrap exceptions in `try/except Exception as e: show(translate(e))`.
2. **No stack traces visible by default.** User sees clean message; clicks "Show details" to see Python traceback.
3. **15+ common exceptions translated.** `FileNotFoundError`, `KeyError`, `ValueError`, `PermissionError`, `UnicodeDecodeError`, `pd.errors.*`, `sqlite3.OperationalError`, etc.
4. **Every translation includes a specific suggestion.** Not generic "try again" — points to the actual fix.
5. **"Copy details" works.** Users can paste the technical output into GitHub issues.
6. **Severity drives colour/icon.** Info (blue i), Warning (amber ⚠), Error (red ❗), Critical (red 🚨).
7. **10 new tests** in `test/test_errors.py` covering: each translation, custom message formatting, technical hiding, suggestion presence.

### Files

**Create:**
- `core/errors.py` (~200 lines)
- `ui/error_dialog.py` (~120 lines)
- `test/test_errors.py` (~150 lines)

**Modify:**
- `ui/dock_panel.py` — wrap every `except Exception as e:` in `translate(e)`
- `ui/wizard.py` — same
- `algorithms/alg_load_data.py` — already has error handling, route through translator
- `algorithms/alg_run_scoring.py` — same
- `modules/m01_data_loader.py` — raise `UserError` with context at load failure points

### Geological Review (Hema — plain-English quality)

- Hema to review every suggestion message for clarity. No jargon. Imperative mood ("Check...", "Close...", "Re-export..."). Max 2 sentences per suggestion.

---

## JC-28: Data Quality Preview Screen (HARD GATE)

**Assigned to:** Deva AI  
**Reviewed by:** Rose AI (G2.5 — she owns this design), Gandalf QA (G2), Dr. Prithvi (G3)  
**Effort:** 4 days  
**Priority:** CRITICAL — this is Rose's hard gate  
**Depends on:** JC-23 (data loaded), JC-24 (columns mapped), JC-25 (deposit type set)

### Problem

Currently the tool computes scores on whatever data it receives, with no visibility into data quality issues. A gravity TIF with wrong CRS silently mis-registers by 800m. An assay file with 20% missing Zn values silently treats them as zero. A drill database with duplicate BHIDs silently double-counts intervals.

In exploration geology, silent wrong outputs cause drill holes in the wrong place — the worst possible failure mode.

### Solution

Between "data loaded + columns mapped + deposit type set" and "run scoring", insert a **mandatory data quality report screen**. The user cannot proceed to scoring until they have seen and acknowledged this report. Critical issues block advancement entirely; warnings allow "proceed with acknowledgement" (logged).

### Implementation

**New module:** `modules/m12_data_quality.py`

```python
"""Data quality checks — run before scoring to surface issues to user."""
from dataclasses import dataclass
from typing import List, Dict, Optional
import numpy as np
import pandas as pd


@dataclass
class DQIssue:
    category: str   # 'drill' | 'geophysics' | 'polygons' | 'grid'
    severity: str   # 'info' | 'warning' | 'critical'
    title: str      # "12,445 missing Zn values in assay"
    details: str    # "Your assay CSV has 65,667 rows. 12,445 (19%) have no ZN value."
    action: str     # "These will be treated as NaN. Alternative: set to zero via config."
    affected: int   # number of records affected
    blocks_advance: bool = False


def check_drill_quality(collar_df, litho_df, assay_df, survey_df=None, cfg=None) -> List[DQIssue]:
    issues = []
    
    # Collar checks
    n_holes = len(collar_df)
    if n_holes == 0:
        issues.append(DQIssue('drill', 'critical', 'No drillholes loaded',
            'Collar CSV is empty.', 'Check the file and re-load.', 0, True))
        return issues
    
    # Duplicate BHIDs
    dup = collar_df[cfg.drill.col_bhid].duplicated().sum()
    if dup > 0:
        issues.append(DQIssue('drill', 'critical', f'{dup} duplicate borehole IDs',
            f'Your collar file has {dup} BHIDs that appear more than once.',
            'Remove duplicates in the CSV or assign unique IDs.', dup, True))
    
    # Missing collar elevations
    missing_z = collar_df[cfg.drill.col_zcollar].isna().sum()
    if missing_z > 0:
        issues.append(DQIssue('drill', 'warning',
            f'{missing_z} boreholes have no collar elevation',
            f'Affects subsurface interval positioning. Scoring may be inaccurate for these.',
            'Fill in ZCOLLAR values in the CSV or exclude these holes.', missing_z))
    
    # Coordinate sanity — catch wrong CRS / unit
    x_range = collar_df[cfg.drill.col_xcollar].max() - collar_df[cfg.drill.col_xcollar].min()
    if x_range < 10:
        issues.append(DQIssue('drill', 'critical',
            'Collar coordinates look like decimal degrees, not metres',
            f'X coordinate range is only {x_range:.2f} — typical UTM range is 1000s of metres.',
            'Your CRS setting may be wrong, or coordinates need conversion.', n_holes, True))
    
    # Litho checks
    if litho_df is not None and len(litho_df) > 0:
        # Unknown rock codes
        unknown = (litho_df['lcode'] == 0).sum()
        unknown_pct = 100 * unknown / len(litho_df)
        if unknown_pct > 10:
            issues.append(DQIssue('drill', 'warning',
                f'{unknown_pct:.0f}% of litho intervals have unknown rock codes',
                f'{unknown} of {len(litho_df)} intervals mapped to "Unknown". '
                f'These will get default scores.',
                'Check your rock code mapping in the config.', unknown))
    
    # Assay checks
    if assay_df is not None and len(assay_df) > 0:
        # Missing grades
        if cfg.drill.col_zn in assay_df.columns:
            missing_zn = assay_df[cfg.drill.col_zn].isna().sum()
            miss_pct = 100 * missing_zn / len(assay_df)
            if miss_pct > 5:
                issues.append(DQIssue('drill', 'warning',
                    f'{miss_pct:.0f}% of assay rows have no Zn value',
                    f'{missing_zn} of {len(assay_df)} intervals have no ZN grade.',
                    'These will be treated as NaN (not zero) during scoring.',
                    missing_zn))
        # Negative grades
        for col in [cfg.drill.col_zn, cfg.drill.col_pb]:
            if col in assay_df.columns:
                neg = (assay_df[col] < 0).sum()
                if neg > 0:
                    issues.append(DQIssue('drill', 'critical',
                        f'{neg} negative grade values in {col}',
                        'Negative grades are invalid.',
                        'Check for data entry errors. Grades below detection '
                        'limit should be recorded as 0 or a small positive number.',
                        neg, True))
    
    return issues


def check_geophysics_quality(grav_grids, mag_grids, cfg) -> List[DQIssue]:
    issues = []
    
    if not grav_grids:
        issues.append(DQIssue('geophysics', 'warning',
            'No gravity data loaded',
            'Gravity criteria (C4, C7b, C9) will not contribute to scoring.',
            'Add gravity TIFs to continue, or proceed without gravity.', 0))
    
    # Check grid coverage
    expected_levels = set(cfg.grid.z_levels)
    actual_levels = set(grav_grids.keys())
    missing_levels = expected_levels - actual_levels
    if missing_levels:
        coverage = 100 * len(actual_levels) / max(len(expected_levels), 1)
        issues.append(DQIssue('geophysics', 'info',
            f'Gravity covers {coverage:.0f}% of requested levels',
            f'Missing levels will be linearly interpolated from available ones.',
            'Add TIFs for missing levels for more accurate scoring.',
            len(missing_levels)))
    
    # Check for nodata percentage
    for mrl, arr in grav_grids.items():
        nan_pct = 100 * np.isnan(arr).sum() / arr.size
        if nan_pct > 30:
            issues.append(DQIssue('geophysics', 'warning',
                f'Gravity TIF at mRL {mrl}: {nan_pct:.0f}% nodata',
                f'Large portions of this level have no gravity data.',
                'Scoring for this level will have gaps.', int(arr.size * nan_pct / 100)))
    
    # CRS check (if GDAL available)
    # ... (reads CRS from TIF, compares to cfg.grid.epsg)
    
    return issues


def run_all_checks(cfg, loader) -> Dict[str, List[DQIssue]]:
    """Run all data quality checks. Returns dict by category."""
    collar = loader.load_collar()
    litho = loader.load_litho()
    assay = loader.load_assay() if cfg.drill.assay_csv else None
    survey = loader.load_survey() if cfg.drill.survey_csv else None
    
    drill_issues = check_drill_quality(collar, litho, assay, survey, cfg)
    geo_issues = check_geophysics_quality(
        loader.load_gravity(), loader.load_magnetics(), cfg)
    
    return {
        'drill': drill_issues,
        'geophysics': geo_issues,
    }
```

**UI screen:** `ui/data_quality_dialog.py`

A large `QDialog` or `QWizardPage` with:
- Summary header: "✓ 23 checks passed. ⚠️ 4 warnings. ❗ 0 critical issues."
- Tabbed panels by category (Drill / Geophysics / Polygons / Grid)
- Each issue rendered as a card with: icon, title, details (collapsible), action text
- Bottom bar:
  - If any critical: only "Cancel" is enabled — cannot proceed
  - If only warnings: "Acknowledge & Proceed" (logs acknowledgement) and "Cancel"
  - If all clean: "Proceed to Scoring" enabled

### Acceptance Criteria

1. **Runs automatically** between data load and scoring. User cannot skip.
2. **Shows categorised issue report** with counts in the header.
3. **Critical issues block advancement.** "Proceed" button disabled; user must fix the data.
4. **Warnings require explicit acknowledgement.** User clicks "I acknowledge these issues" checkbox before proceeding.
5. **Acknowledgement is logged.** Written to audit trail in output folder.
6. **All 10+ check types fire on synthetic bad data.** Test data with duplicates, negatives, missing grades, wrong-CRS coordinates all surface correctly.
7. **Clean data passes silently.** Kayad synthetic data → 0 critical, 0 warnings, "All checks passed" message.
8. **Performance:** Full check on 2,000 holes + 50 geophysics TIFs completes in <5s.
9. **Plain language throughout.** No "NaN", no "dtype mismatch", no Python terminology.
10. **15 new tests** in `test/test_data_quality.py` — one per check type + integration test.

### Files

**Create:**
- `modules/m12_data_quality.py` (~400 lines)
- `ui/data_quality_dialog.py` (~300 lines)
- `test/test_data_quality.py` (~250 lines)

**Modify:**
- `algorithms/alg_run_scoring.py` — run DQ check before scoring loop; abort if critical
- `ui/wizard.py` — insert DQ page between DataPage and RunPage
- `ui/dock_panel.py` — "Run Scoring" button now triggers DQ check first

### Geological Review (Rose AI owns — REQUIRED)

- Rose AI is the spec lead. She defines what "data quality" means in this context and writes the acceptance rules.
- Dr. Prithvi to review the drill quality rules (especially the coordinate sanity check — what constitutes "reasonable" UTM vs lat/long vs grid coordinates across different deposits?).

---

## JC-29: CSV Encoding Auto-Detection

**Assigned to:** Deva AI  
**Reviewed by:** Gandalf QA (G2), Rose AI (G2.5 — data integrity)  
**Effort:** 1 day  
**Priority:** MEDIUM (but low cost — quick win)  
**Depends on:** None

### Problem

CSVs from different countries use different text encodings:
- UTF-8 (standard)
- UTF-8-BOM (Microsoft Excel in some locales)
- Windows-1252 / CP1252 (European Windows)
- Latin-1 (Western European legacy)
- Shift-JIS (Japan)

Pandas `read_csv` defaults to UTF-8 and crashes with `UnicodeDecodeError` on the others. Geologists in non-English locales have to manually convert files.

### Solution

Auto-detect encoding via the `charset-normalizer` library (pure Python, small dependency) or fall back to a heuristic trial of common encodings.

### Implementation

**Add to `modules/m01_data_loader.py`:**

```python
def _detect_encoding(path: str) -> str:
    """Try common encodings until one works. Returns encoding name."""
    # Read first 100KB for detection
    with open(path, 'rb') as f:
        raw = f.read(100_000)
    
    # Try charset-normalizer if available (best)
    try:
        from charset_normalizer import from_bytes
        result = from_bytes(raw).best()
        if result:
            return result.encoding
    except ImportError:
        pass
    
    # Fallback: try common encodings in priority order
    for enc in ['utf-8-sig', 'utf-8', 'cp1252', 'latin-1', 'shift_jis', 'utf-16']:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    
    # Last resort
    return 'latin-1'  # Can always decode any bytes, even if wrong


# Wrap all pd.read_csv calls:
def _read_csv_smart(path: str, **kwargs) -> pd.DataFrame:
    """Read CSV with auto-detected encoding."""
    enc = _detect_encoding(path)
    try:
        return pd.read_csv(path, encoding=enc, **kwargs)
    except UnicodeDecodeError as e:
        from core.errors import UserError
        raise UserError(
            message=f"Cannot read {os.path.basename(path)} — unusual text encoding",
            suggestion=(
                "Open the file in Excel and save as 'CSV UTF-8 (Comma delimited)'. "
                "This fixes most encoding issues."
            ),
            technical=e,
        )
```

Replace all `pd.read_csv(path, ...)` with `self._read_csv_smart(path, ...)`.

### Acceptance Criteria

1. **UTF-8 files load normally.** No regression.
2. **UTF-8-BOM files load (Excel export).** Common case — must work.
3. **Windows-1252 with `é`, `ñ`, `ü` characters loads correctly.** Test with French column names like `PROFONDEUR`.
4. **Truly unreadable files produce a `UserError`** with the "save as UTF-8" suggestion — not a raw `UnicodeDecodeError`.
5. **No crash on binary files.** If user points at a PDF by accident, clean error not stack trace.
6. **7 new tests** in `test/test_encoding.py` — one per encoding type + error path.

### Files

**Modify:**
- `modules/m01_data_loader.py` — add `_detect_encoding`, `_read_csv_smart`, use throughout

**Create:**
- `test/test_encoding.py` (~80 lines)
- `test/fixtures/` — 5 small test CSVs, one per encoding

### Geological Review

- None required. Pure technical fix.

---

## JC-30: Contextual Geological Tooltips

**Assigned to:** Dr. Riya AI (content), Deva AI (implementation)  
**Reviewed by:** Dr. Prithvi (G3 — geological accuracy)  
**Effort:** 3 days (2 days content by Dr. Riya + 1 day engineering by Deva)  
**Priority:** HIGH — builds trust, enables Type 3 (exploration manager) users  
**Depends on:** JC-25 (deposit presets wired in)

### Problem

When a geologist hovers over "Structural marker code" they see no context. They don't know what the tool expects, what typical values are, or how to choose for their deposit. Trust erodes. Or worse, they pick wrong.

### Solution

Every configurable parameter gets a tooltip that includes:
1. **Plain English definition** of the parameter
2. **Why it matters** geologically
3. **Deposit-type-specific examples** (from the preset literature references)
4. **Suggested range** with typical values

Tooltips are loaded from a JSON dictionary keyed by parameter name and deposit type.

### Implementation

**New file:** `core/tooltips.json`

```json
{
    "structural_marker_code": {
        "generic": {
            "definition": "The rock code that marks the primary structural control in your deposit (e.g., a specific fault lithology or contact).",
            "why": "Used to compute C2 PG halo scoring — cells near the structural marker score higher.",
            "range": "Any integer from your rock code mapping.",
            "default": "3 (Pegmatite for SEDEX)"
        },
        "SEDEX Pb-Zn": {
            "definition": "Code for Pegmatite, which marks the fold-axis structural control at Kayad-type deposits.",
            "example": "At Kayad (Rajasthan): code 3 = Pegmatite. At Rampura-Agucha: similar pegmatitic units.",
            "suggestion": "If your SEDEX deposit has a different structural marker (graphitic schist, carbonate bed), update the rock_codes dict and use that code."
        },
        "VMS Cu-Zn": {
            "definition": "In VMS systems, typically the stringer zone or the felsic-mafic contact marking the feeder pipe.",
            "example": "At Kidd Creek: rhyolite-basalt contact. At Neves-Corvo: volcaniclastic unit. At Greens Creek: stringer zone.",
            "suggestion": "Choose the code for the rock type that defines the hydrothermal upflow zone in your deposit."
        },
        "Epithermal Au": {
            "definition": "In epithermal deposits, typically the silicified zone or the main fault/vein lithology.",
            "example": "At Hishikari: banded quartz vein material. At Waihi: Martha Fault silicified andesite.",
            "suggestion": "Use the rock code for your dominant vein host or silicified alteration package."
        },
        "Porphyry Cu-Mo": {
            "definition": "Typically the causative mineralised porphyry intrusive body itself.",
            "example": "At El Teniente: quartz-monzonite porphyry. At Chuquicamata: porphyry stocks.",
            "suggestion": "Use the rock code for the productive intrusive body, not the barren host rocks."
        }
    },
    "pg_breaks": { /* ... similar structure ... */ },
    "csr_upper_breaks": { /* ... */ },
    "novelty_distance_m": { /* ... */ }
    /* ... 30+ parameters total */
}
```

**Loader module:** `core/tooltips.py`

```python
"""Load contextual tooltips for UI widgets, filtered by deposit type."""
import json, os

TOOLTIPS_FILE = os.path.join(os.path.dirname(__file__), 'tooltips.json')
_cache = None

def _load():
    global _cache
    if _cache is None:
        with open(TOOLTIPS_FILE) as f:
            _cache = json.load(f)
    return _cache

def get_tooltip(parameter: str, deposit_type: str = 'generic') -> str:
    """Return formatted HTML tooltip for a parameter and deposit type."""
    data = _load()
    p = data.get(parameter, {})
    generic = p.get('generic', {})
    specific = p.get(deposit_type, {})
    
    parts = []
    if specific.get('definition'):
        parts.append(f"<b>{specific['definition']}</b>")
    elif generic.get('definition'):
        parts.append(f"<b>{generic['definition']}</b>")
    
    if generic.get('why'):
        parts.append(f"<i>Why it matters:</i> {generic['why']}")
    
    if specific.get('example'):
        parts.append(f"<i>Example:</i> {specific['example']}")
    
    if specific.get('suggestion'):
        parts.append(f"<i>Tip:</i> {specific['suggestion']}")
    
    if generic.get('range'):
        parts.append(f"<i>Typical range:</i> {generic['range']}")
    
    return '<br><br>'.join(parts) or f"No help available for {parameter}"
```

**UI integration:** Every widget in `ui/config_widget.py` and future widgets calls `setToolTip(get_tooltip(param_name, cfg.deposit_type))`.

### Acceptance Criteria

1. **30+ parameters have tooltips.** All `ScoringThresholdsConfig` fields plus key `ScoringWeightsConfig` fields.
2. **4 deposit types have specific examples.** SEDEX, VMS, Epithermal, Porphyry all have real-world examples in tooltips.
3. **Tooltips reflect the selected deposit.** Changing preset updates tooltips automatically.
4. **Fallback to generic.** Parameters without deposit-specific tooltips show the generic version.
5. **Formatted HTML.** Tooltips use bold, italics, and line breaks for readability.
6. **Dr. Prithvi signed off** on all geological examples.
7. **Loaded on demand, cached.** JSON file parsed once, held in memory.
8. **5 new tests** in `test/test_tooltips.py` — coverage, missing keys, deposit filtering, fallback behaviour.

### Files

**Create:**
- `core/tooltips.py` (~60 lines)
- `core/tooltips.json` (~300 lines — written by Dr. Riya, reviewed by Dr. Prithvi)
- `test/test_tooltips.py` (~100 lines)

**Modify:**
- `ui/config_widget.py` — wire `setToolTip(get_tooltip(...))` on every field
- `ui/wizard.py` — add tooltips to wizard fields
- Future `ui/config_widget_expanded.py` (from deferred JC-18) — tooltips throughout

### Geological Review (Dr. Prithvi — REQUIRED for every tooltip with deposit examples)

- Dr. Prithvi must sign off on every real-world example. No invented examples — must match published geological literature.
- Dr. Riya to cite the primary references in a follow-up document so users can trace back to sources.

---

## Sprint 16 Roll-Up

### Timeline (12 calendar days with parallelisation)

```
Week 1:
  Day 1-2  │ JC-25 (deposit chooser)     ─── Deva
  Day 1-4  │ JC-23 (autodiscovery)       ─── Deva (parallel start)
  Day 1    │ JC-29 (encoding)            ─── Deva (quick win)
  Day 1-2  │ JC-26 (example project data) ── Dr. Prithvi + Deva
  Day 3-7  │ JC-24 (column mapping)      ─── Deva + Hema spec + Dr. Prithvi review
  Day 1-2  │ JC-30 tooltips content       ── Dr. Riya

Week 2:
  Day 8-11 │ JC-28 (data quality)        ─── Deva (spec by Rose)
  Day 10-12│ JC-27 (plain-language errors) ─ Deva + Hema review
  Day 8    │ JC-30 tooltips wiring       ─── Deva
  Day 12   │ Integration + TTFM test      ── Gandalf
```

### Amit G4 gate criteria

Before v2.0 ships, Amit must confirm:
1. **Time-to-First-Map ≤ 10 minutes** measured by Gandalf with a first-time-user scenario.
2. **Zero JSON editing required** to complete the standard workflow.
3. **Data quality gate blocks scoring** on known-bad synthetic data.
4. **Example project runs to completion** in <60 seconds.
5. **Column remapping works** for a real-world CSV with columns `HOLE_ID`, `EAST`, `NORTH`, `RL`, `Zn_pct`.
6. **Dr. Prithvi geological sign-off** on: deposit sanity rules (JC-25), example dataset (JC-26), tooltip content (JC-30).

### Quality Gates (team review required at each)

| Gate | Responsible | Criterion |
|------|-------------|-----------|
| G1 — Spec | Hema | Every JC has testable acceptance criteria |
| G2 — Code Review | Gandalf QA | All tests pass, no stack traces in UI paths |
| G2.5 — Integration | Rose AI | Data quality gate fires on bad data, clean on good data |
| G3 — Geological | Dr. Prithvi + Dr. Riya | Tooltip content and sanity rules accurate |
| G3.5 — Operational | Vimal AI | Plugin ZIP builds and installs offline on Windows |
| G4 — User Acceptance | Amit | TTFM ≤ 10min measured; 5 criteria above all met |

---

## Post-Sprint: Deferred to v2.1

Per Lala's veto, these are not in S16:

- **Drag-and-drop data cards** (Option D from meeting) — polish, defer based on user feedback
- **Excel template workbook** (Option E) — CSV already works; parallel path
- **JC-09 (pipeline deduplication)** — internal refactor, not user-facing
- **JC-14 (nodata system)** — partial work done in S9; full system deferred
- **JC-15 (GPKG batch writing)** — performance optimisation
- **JC-16 (async UI with QgsTask)** — requires QGIS runtime testing
- **JC-18 (config widget expansion)** — tabs for weights, corridors, regimes

These return to the v2.1 backlog after S16 ships and Amit/users provide feedback.

---

## Summary

**8 job cards. 24 person-days. 12 calendar days with parallelisation.**

**This sprint transforms Bhumi3DMapper from "a QGIS plugin that works if you know how to configure it" into "a tool that a field geologist can install on Monday and use on Tuesday."**

*Sprint approved by Satya. Scrummy opens the backlog. Hema writes specs tomorrow. Dr. Prithvi blocks 2 hours for geological review. Dr. Riya starts tooltip content in parallel with engineering.*

*Mineral discovery remains the primary objective. Every job card serves that objective by removing friction between the geologist and the discovery target.*
