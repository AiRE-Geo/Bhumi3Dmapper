# Bhumi3DMapper — Complete Project Summary & Autonomous Development Prompt

> **Target:** QGIS 3.44 LTR (Qt5) · **Port-ready for:** QGIS 4.0 LTR (Qt6, October 2026)  
> **Priority:** Ease of use · Crash-proof · Production-ready · Zero manual intervention during build

---

## Part 1 — Project Summary

### What Bhumi3DMapper Is

Bhumi3DMapper is a QGIS plugin for multi-criterion 3D mineral prospectivity mapping. It wraps a complete Python computation framework (already built) in a polished QGIS interface. A geologist installs it, fills in a simple panel, clicks Run, and immediately sees scored prospect maps loaded into their QGIS project with colour-coded symbology — no command line, no file conversion, no intermediate steps.

### Origin

The framework was developed during a full geological analysis of the **Kayad Lead-Zinc Mine** (Hindustan Zinc Limited / Vedanta, Ajmer, Rajasthan, India). The analysis integrated:

- 2,112 drill holes (1988–2025), 65,667 assay intervals, 34,693 m of litho logs
- 19 gravity inversion depth slices (mRL −15 to +435, 5 m/pixel)
- 20 magnetic susceptibility depth slices (mRL −15 to +460, 30 m/pixel)
- 30 known mineralisation polygon levels (mRL −265 to +460)
- 5-domain grade block model (~3.2 million blocks)

From this analysis, **two prospectivity models** were built and validated:

| Model | Purpose | Key criteria |
|-------|---------|--------------|
| **Proximity** | Resource delineation — extend known ore | Ore-envelope proximity + plunge axis proximity included |
| **Blind / Environment** | Greenfield step-out — find analogous new ore | All ore-proximity removed; contextual geophysics, Laplacian, novelty score |

Both models produce **5×5 m per-level GeoPackage outputs** (one per mRL elevation), each cell containing 36 fields covering geology, geophysics, and all individual criterion scores.

### Geological Controls Established (Kayad)

**Upper mine (mRL 160–435)**
- Primary host: QMS (Quartz-Muscovite Schist), 70–94% of ore intervals
- PG contact halo: 4–10 m inboard from QMS–Pegmatite contact = peak ore
- CSR standoff: 10–40 m above Calc-Silicate Rock surface = optimal
- Structural corridor: N28°E ±6°, dip 70–80° SE
- Gravity: ore is density-NEGATIVE (−0.03 to −0.19 mGal) vs flanking amphibolite
- Magnetics: persistent local susceptibility minimum within positive field

**Transition (mRL 60–160)**  
Mixed QMS/CSR control — apply 30% confidence discount.

**Lower mine / deep (mRL −265 to +60)**  
- Primary host: CSR (56–75% of intervals)
- Independent N315°E structural corridor (K18, NE bodies)
- K18 domain: 14–18% Zn, exceptional grade
- Independent plunge vector 12°/063°E — 3.4× faster lateral shift than shallow shoot

**Hard veto:** Amphibolite — score capped at 20 regardless of all criteria.

### Novel Blind Targets Identified (Kayad)

| Cluster | Location | mRL Range | Novel VH cells | Priority |
|---------|----------|-----------|----------------|----------|
| 1 — SW Corridor Extension | 500–870 m south | mRL 60–235 | 275 (0.69 ha at mRL 235) | 1 |
| 2 — WSW Deep Flank | 300–1,000 m WSW | mRL 235–360 | 678 (1.70 ha at mRL 360) | 1 — highest |
| 3 — NE Corridor Extension | 1,000–1,250 m NE | mRL 160–435 | Score 93.0 at mRL 435 | 2 |
| 4 — K18-Parallel Deep | 300–900 m from K18 | mRL 35–135 | Semi-novel | 3 |
| 5 — Near-K18 Flank | 300–500 m from K18 | mRL 285–385 | Near-novel | 3 |

### The Core Framework (Already Built)

Nine Python files in `ProspectivityMapper_Framework.zip` — **these are never modified by the plugin**:

| File | Lines | Role |
|------|-------|------|
| `core/config.py` | 313 | All project variables as dataclasses → JSON. Single source of truth. |
| `modules/m01_data_loader.py` | 231 | Load CSV drill + TIF geophysics + GPKG polygons |
| `modules/m02_drill_processor.py` | 190 | Litho/PG-contact/CSR spatial lookups, 30m→5m upsampled |
| `modules/m03_geophys_processor.py` | 190 | Gradient, Laplacian, level interpolation |
| `modules/m04_scoring_engine.py` | 348 | All criterion scoring functions (vectorised numpy) |
| `modules/m05_gpkg_writer.py` | 187 | 2D GeoPackage writer, any CRS/EPSG |
| `modules/m06_voxel_builder.py` | 214 | 3D voxel builder → compressed .npz archives |
| `pipeline.py` | 264 | CLI orchestrator |
| `README.md` | 128 | Usage guide |

### Architecture Decision: 2D GPKGs vs Voxel

- **Primary output: stacked 2D GPKGs** (one per mRL level, ~80–100 MB each)  
  Loads directly into QGIS — no conversion needed, avoids 6.7 GB peak RAM assembly and Windows path issues.

- **Voxel (.npz): on-demand only** for 3D cross-level novel target analysis.

- **Future QGIS 3D option:** UGRID/MDAL 3D Layered Mesh format (better than voxel for QGIS 3D viewer).

### QGIS Version Strategy

- **Target now:** QGIS 3.44 LTR (Qt5, released Feb 2026, LTR until ~May 2027)
- **Port-ready for:** QGIS 4.0 "Norrköping" (Qt6, released March 6 2026; 4.2 LTR due October 2026)
- **Rule:** All Qt imports use `from qgis.PyQt import ...` — never `from PyQt5 import ...`
- **Migration tool:** `pyqt5_to_pyqt6.py` script (Oslandia) + `pyqgis4-checker` Docker image

---

## Part 2 — Autonomous Development Prompt

> **Instructions for Claude:** When this document is provided in the Bhumi3DMapper Claude Project (which contains all 9 core modules), work through each sprint in order. For each sprint: write all code, write all tests, run the tests using the bash/Python tools available, fix any failures, and only mark the sprint complete when all automated tests pass. Do not ask the user to manually test anything — build self-verifying tests for every component.

---

### Design Philosophy

**Ease of use is the top priority.** The target user is a geologist, not a programmer. Every interaction must be:

1. **One-click where possible** — the user should never need to know file paths, run commands, or understand the scoring model to get results.
2. **Self-explanatory** — every field has a tooltip; every error has a human-readable message with a suggested fix.
3. **Recoverable** — any error at any stage leaves the project in a usable state; nothing corrupts or locks.
4. **Informative** — the user always knows what is happening, how far along it is, and what to do next.
5. **Fast to first result** — the default settings should produce a valid prospectivity map for any input data with zero configuration beyond pointing to files.

---

### Plugin Directory Structure

```
bhumi3dmapper/
├── __init__.py
├── metadata.txt
├── bhumi3dmapper.py          ← main class, menu, toolbar
├── provider.py               ← QgsProcessingProvider
├── icon.png                  ← 48×48 icon
├── resources.qrc
├── resources_rc.py           ← compiled by pyrcc5
├── core/                     ← COPY (not symlink) of core/config.py
│   └── config.py
├── modules/                  ← COPY of modules/m01–m06 + __init__.py
│   ├── __init__.py
│   ├── m01_data_loader.py
│   ├── m02_drill_processor.py
│   ├── m03_geophys_processor.py
│   ├── m04_scoring_engine.py
│   ├── m05_gpkg_writer.py
│   └── m06_voxel_builder.py
├── algorithms/
│   ├── __init__.py
│   ├── alg_wizard.py         ← NEW: single-dialog wizard (ease of use)
│   ├── alg_load_data.py
│   ├── alg_run_scoring.py
│   ├── alg_gpkg_export.py
│   ├── alg_voxel_build.py
│   └── alg_load_results.py
├── ui/
│   ├── __init__.py
│   ├── dock_panel.py
│   └── config_widget.py
└── test/
    ├── __init__.py
    ├── conftest.py
    ├── test_config.py
    ├── test_scoring.py
    ├── test_gpkg.py
    ├── test_data_loader.py
    └── test_integration.py
```

> **Important:** Copy (not symlink) `core/` and `modules/` into the plugin directory. Symlinks break on Windows and when installing from ZIP. The copies are exact duplicates — they never diverge.

---

### Sprint 1 — Plugin Skeleton & Menu Item

**Goal:** `Bhumi3DMapper` appears in the QGIS Plugins menu and Processing Toolbox after installing from ZIP.

#### `metadata.txt`

```ini
[general]
name=Bhumi3DMapper
qgisMinimumVersion=3.28
qgisMaximumVersion=4.99
description=3D mineral prospectivity mapping — SEDEX Pb-Zn, VMS, porphyry, epithermal and more
version=1.0.0
author=AiRE — AI Resource Exploration Pvt Ltd
email=contact@aire-exploration.com
about=Config-driven multi-criterion prospectivity pipeline for exploration geologists.
      No command line needed. Load your drill data and geophysics, click Run, get
      scored prospect maps loaded directly into QGIS with colour-coded symbology.
      Proximity model (resource delineation) + Blind model (greenfield step-out).
tracker=https://github.com/aire-exploration/bhumi3dmapper/issues
repository=https://github.com/aire-exploration/bhumi3dmapper
tags=geology,mining,prospectivity,geophysics,3D,voxel,exploration,drillhole
homepage=https://aire-exploration.com/bhumi3dmapper
category=Analysis
icon=icon.png
experimental=False
deprecated=False
server=False
```

#### `__init__.py`

```python
# -*- coding: utf-8 -*-
def classFactory(iface):  # pylint: disable=invalid-name
    from .bhumi3dmapper import Bhumi3DMapper
    return Bhumi3DMapper(iface)
```

#### `bhumi3dmapper.py`

```python
# -*- coding: utf-8 -*-
"""Main plugin class — registers menu, toolbar, and Processing provider."""
import os
import traceback

from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.core import QgsApplication, Qgis


def tr(msg):
    return QCoreApplication.translate('Bhumi3DMapper', msg)


class Bhumi3DMapper:
    """QGIS Plugin — Bhumi3DMapper."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = tr('Bhumi3DMapper')
        self.toolbar = None
        self.dock = None
        self.provider = None

    # ── Lifecycle ─────────────────────────────────────────────────────────
    def initGui(self):
        """Create menu entries and toolbar icons."""
        try:
            self._register_provider()
            self._add_action(
                icon_name='icon.png',
                text=tr('Open Project Panel'),
                callback=self.openPanel,
                tooltip=tr('Open the Bhumi3DMapper prospectivity panel'),
                add_to_toolbar=True,
            )
            self._add_action(
                icon_name='icon.png',
                text=tr('Quick Start Wizard'),
                callback=self.openWizard,
                tooltip=tr('Step-by-step wizard — fastest way to get your first map'),
                add_to_toolbar=False,
            )
        except Exception:  # pragma: no cover
            self.iface.messageBar().pushMessage(
                'Bhumi3DMapper',
                tr('Failed to initialise plugin. See QGIS log for details.'),
                level=Qgis.Critical, duration=10)
            QgsApplication.instance().messageLog().logMessage(
                traceback.format_exc(), 'Bhumi3DMapper', Qgis.Critical)

    def unload(self):
        """Remove all plugin UI elements."""
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        if self.dock:
            self.iface.removeDockWidget(self.dock)
            self.dock = None
        if self.toolbar:
            del self.toolbar

    # ── Actions ────────────────────────────────────────────────────────────
    def openPanel(self):
        """Open (or show) the dockable project panel."""
        try:
            if self.dock is None:
                from .ui.dock_panel import BhumiDockWidget
                self.dock = BhumiDockWidget(self.iface)
                self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
            self.dock.show()
            self.dock.raise_()
        except Exception:
            self._show_error(tr('Could not open the project panel.'))

    def openWizard(self):
        """Open the Quick Start Wizard."""
        try:
            from .ui.wizard import BhumiWizard
            wizard = BhumiWizard(self.iface.mainWindow())
            wizard.exec_()
        except Exception:
            self._show_error(tr('Could not open the wizard.'))

    # ── Private helpers ────────────────────────────────────────────────────
    def _register_provider(self):
        from .provider import Bhumi3DProvider
        self.provider = Bhumi3DProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def _add_action(self, icon_name, text, callback, tooltip='',
                    add_to_toolbar=True):
        icon = QIcon(os.path.join(self.plugin_dir, icon_name))
        action = QAction(icon, text, self.iface.mainWindow())
        action.triggered.connect(callback)
        action.setToolTip(tooltip)
        self.iface.addPluginToMenu(self.menu, action)
        if add_to_toolbar:
            self.iface.addToolBarIcon(action)
        self.actions.append(action)
        return action

    def _show_error(self, msg):
        QgsApplication.instance().messageLog().logMessage(
            traceback.format_exc(), 'Bhumi3DMapper', Qgis.Critical)
        QMessageBox.critical(self.iface.mainWindow(), 'Bhumi3DMapper', msg)
```

#### `provider.py`

```python
# -*- coding: utf-8 -*-
"""Processing provider — registers all Bhumi3DMapper algorithms."""
import os
from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon


class Bhumi3DProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        from .algorithms.alg_load_data import LoadDataAlgorithm
        from .algorithms.alg_run_scoring import RunScoringAlgorithm
        from .algorithms.alg_gpkg_export import GpkgExportAlgorithm
        from .algorithms.alg_voxel_build import VoxelBuildAlgorithm
        from .algorithms.alg_load_results import LoadResultsAlgorithm
        for alg_class in [LoadDataAlgorithm, RunScoringAlgorithm,
                           GpkgExportAlgorithm, VoxelBuildAlgorithm,
                           LoadResultsAlgorithm]:
            self.addAlgorithm(alg_class())

    def id(self):        return 'bhumi3dmapper'
    def name(self):      return 'Bhumi3DMapper'
    def longName(self):  return '3D Mineral Prospectivity Mapper'
    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), 'icon.png'))
    def versionInfo(self): return '1.0.0'
```

#### Sprint 1 Automated Test (`test/test_sprint1.py`)

```python
"""Sprint 1 — plugin skeleton, no QGIS import needed for these tests."""
import os, json, sys

# Add plugin root to path
PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(PLUGIN_DIR))

def test_metadata_exists():
    path = os.path.join(PLUGIN_DIR, 'metadata.txt')
    assert os.path.exists(path), "metadata.txt missing"

def test_metadata_required_fields():
    import configparser
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(PLUGIN_DIR, 'metadata.txt'))
    g = cfg['general']
    for field in ['name','qgisMinimumVersion','description','version','author']:
        assert field in g, f"metadata.txt missing: {field}"
    assert g['name'] == 'Bhumi3DMapper'
    assert int(g['qgisMinimumVersion'].split('.')[0]) >= 3

def test_init_py_exists():
    assert os.path.exists(os.path.join(PLUGIN_DIR, '__init__.py'))

def test_icon_exists():
    assert os.path.exists(os.path.join(PLUGIN_DIR, 'icon.png')), \
        "icon.png missing — create a 48x48 PNG"

def test_core_modules_present():
    for fname in ['config.py']:
        assert os.path.exists(os.path.join(PLUGIN_DIR, 'core', fname)), \
            f"core/{fname} missing — copy from ProspectivityMapper_Framework"

def test_processing_modules_present():
    for fname in ['m01_data_loader.py','m02_drill_processor.py',
                  'm03_geophys_processor.py','m04_scoring_engine.py',
                  'm05_gpkg_writer.py','m06_voxel_builder.py']:
        assert os.path.exists(os.path.join(PLUGIN_DIR, 'modules', fname)), \
            f"modules/{fname} missing — copy from ProspectivityMapper_Framework"

def test_no_pyqt5_imports():
    """CRITICAL: all Qt imports must use qgis.PyQt for dual Qt5/Qt6 compat."""
    import re
    bad = re.compile(r'^from PyQt5|^import PyQt5', re.MULTILINE)
    for root, dirs, files in os.walk(PLUGIN_DIR):
        dirs[:] = [d for d in dirs if d not in ('test', '__pycache__', '.git')]
        for fname in files:
            if fname.endswith('.py'):
                content = open(os.path.join(root, fname)).read()
                matches = bad.findall(content)
                assert not matches, \
                    f"{fname} contains PyQt5 direct import — use qgis.PyQt instead"
```

**Run Sprint 1 tests:**
```bash
cd /path/to/bhumi3dmapper
pytest test/test_sprint1.py -v
```

**Sprint 1 complete when:** All tests pass and `icon.png` exists (create a placeholder 48×48 PNG if needed).

---

### Sprint 2 — Configuration System & Project Config

**Goal:** `ProjectConfig` loads/saves reliably. The config system is the backbone — get it right before building any UI.

#### `conftest.py` (shared test fixtures)

```python
# -*- coding: utf-8 -*-
"""Shared pytest fixtures — no QGIS dependency."""
import os, sys, pytest

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)

@pytest.fixture
def kayad_config():
    """Minimal valid config matching Kayad project."""
    from core.config import ProjectConfig, GridConfig
    cfg = ProjectConfig(
        project_name='Kayad Test',
        deposit_type='SEDEX Pb-Zn',
        location='Ajmer, Rajasthan, India',
        crs_epsg=32643,
    )
    cfg.grid.xmin = 468655.0
    cfg.grid.ymin = 2932890.0
    cfg.grid.nx = 482
    cfg.grid.ny = 722
    cfg.grid.cell_size_m = 5.0
    cfg.grid.z_top_mrl = 460.0
    cfg.grid.z_bot_mrl = -260.0
    cfg.grid.dz_m = 5.0
    return cfg

@pytest.fixture
def tmp_config_path(tmp_path, kayad_config):
    path = str(tmp_path / 'test_config.json')
    kayad_config.to_json(path)
    return path
```

#### `test/test_config.py`

```python
# -*- coding: utf-8 -*-
"""Sprint 2 — ProjectConfig roundtrip and validation tests."""
import os, json, pytest

def test_config_creates_default():
    from core.config import ProjectConfig
    cfg = ProjectConfig()
    assert cfg.project_name == 'Unnamed Project'
    assert cfg.grid.cell_size_m == 5.0

def test_config_roundtrip_json(tmp_path, kayad_config):
    path = str(tmp_path / 'cfg.json')
    kayad_config.to_json(path)
    assert os.path.exists(path)
    loaded = type(kayad_config).from_json(path)
    assert loaded.project_name == kayad_config.project_name
    assert loaded.crs_epsg == 32643
    assert loaded.grid.nx == 482
    assert loaded.grid.cell_size_m == 5.0

def test_config_json_is_valid(tmp_path, kayad_config):
    path = str(tmp_path / 'cfg.json')
    kayad_config.to_json(path)
    with open(path) as f:
        data = json.load(f)
    assert 'project_name' in data
    assert 'grid' in data
    assert 'scoring' in data

def test_config_z_levels(kayad_config):
    levels = kayad_config.grid.z_levels
    assert levels[0] == -260.0
    assert levels[-1] == 460.0
    assert len(levels) == 145
    assert all(abs(levels[i+1]-levels[i]-5.0) < 0.01 for i in range(len(levels)-1))

def test_config_cells_per_level(kayad_config):
    assert kayad_config.grid.n_cells_per_level == 482 * 722

def test_scoring_weights_sum(kayad_config):
    w = kayad_config.scoring
    prox_sum = sum(w.proximity.values())
    blind_sum = sum(w.blind.values())
    assert abs(prox_sum - 11.0) < 0.01, f"Proximity weights sum to {prox_sum}, expected 11.0"
    assert abs(blind_sum - 12.0) < 0.01, f"Blind weights sum to {blind_sum}, expected 12.0"

def test_config_missing_file_raises(tmp_path):
    from core.config import ProjectConfig
    with pytest.raises((FileNotFoundError, OSError)):
        ProjectConfig.from_json(str(tmp_path / 'nonexistent.json'))

def test_config_handles_partial_json(tmp_path):
    """Partial config should fill missing fields with defaults."""
    path = str(tmp_path / 'partial.json')
    with open(path, 'w') as f:
        json.dump({'project_name': 'Partial'}, f)
    from core.config import ProjectConfig
    cfg = ProjectConfig.from_json(path)
    assert cfg.project_name == 'Partial'
    assert cfg.grid.cell_size_m == 5.0  # default filled in
```

**Run Sprint 2 tests:**
```bash
pytest test/test_config.py -v
```

---

### Sprint 3 — Scoring Engine (Core Logic)

**Goal:** All 10 criterion functions produce correct values. This is the geological heart of the plugin.

#### `test/test_scoring.py`

```python
# -*- coding: utf-8 -*-
"""Sprint 3 — Criterion function tests. No QGIS needed."""
import numpy as np, pytest, sys, os

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)

from modules.m04_scoring_engine import (
    score_lithology, score_pg_halo, score_footwall_standoff,
    score_gravity_absolute, score_gravity_contextual,
    score_mag_absolute, score_mag_contextual,
    score_structural_corridor, score_plunge_proximity,
    score_gravity_gradient, score_mag_gradient,
    score_gravity_laplacian, score_novelty,
    compute_proximity, compute_blind, apply_hard_veto, score_to_class
)

# ── Helpers ────────────────────────────────────────────────────────────────
def arr(*vals): return np.array(vals, dtype=np.float32)
def cells(n=10):
    E = np.full(n, 469500.0, dtype=np.float32)
    N = np.full(n, 2934900.0, dtype=np.float32)
    return E, N

# ── C1 — Lithology ─────────────────────────────────────────────────────────
def test_litho_qms_upper(kayad_config):
    s = score_lithology(arr(1,1,1), 2, kayad_config)
    assert np.allclose(s, 1.0), "QMS in upper regime should score 1.0"

def test_litho_amphibolite_always_zero(kayad_config):
    for regime in [0,1,2]:
        s = score_lithology(arr(2), regime, kayad_config)
        assert s[0] == 0.0, f"Amphibolite must score 0.0 in all regimes (regime={regime})"

def test_litho_csr_lower(kayad_config):
    s = score_lithology(arr(4), 0, kayad_config)
    assert s[0] == 1.0, "CSR in lower regime should score 1.0"

# ── C2 — PG halo ────────────────────────────────────────────────────────────
def test_pg_halo_peak_zone():
    s = score_pg_halo(arr(5.0, 7.0, 9.0), regime_id=2)
    assert np.all(s == 1.0), "4–10m PG halo should score 1.0"

def test_pg_halo_immediate_contact():
    s = score_pg_halo(arr(1.0), regime_id=2)
    assert s[0] < 1.0, "0–2m (immediate contact) should score < 1.0"

def test_pg_halo_inactive_lower():
    s = score_pg_halo(arr(5.0, 100.0), regime_id=0)
    assert np.allclose(s, 0.4), "PG halo inactive in lower regime — flat 0.4"

# ── C3 — CSR standoff ──────────────────────────────────────────────────────
def test_csr_standoff_optimal_upper():
    s = score_footwall_standoff(arr(15.0, 25.0, 35.0), regime_id=2)
    assert np.all(s == 1.0), "10–40m standoff = 1.0 in upper regime"

def test_csr_contact_optimal_lower():
    s = score_footwall_standoff(arr(2.0, 4.0), regime_id=0)
    assert np.all(s == 1.0), "<5m CSR standoff = 1.0 in lower regime (inverted)"

def test_csr_poor_standoff_upper():
    s = score_footwall_standoff(arr(200.0), regime_id=2)
    assert s[0] < 0.3, "200m standoff should score poorly"

# ── C4 — Gravity ───────────────────────────────────────────────────────────
def test_gravity_absolute_strong_negative():
    s = score_gravity_absolute(arr(-0.15, -0.05, 0.0, 0.5), z_mrl=310.0)
    assert s[0] > s[1] > s[2] > s[3], "More negative gravity → higher score"

def test_gravity_contextual_negative_wins():
    s = score_gravity_contextual(arr(-2.0, 0.0, 2.0), grav_mean=0.0, grav_std=1.0)
    assert s[0] > s[1] > s[2], "Z-score < 0 should score higher"

# ── C5 — Magnetics ─────────────────────────────────────────────────────────
def test_mag_absolute_local_minimum():
    s = score_mag_absolute(arr(-15.0, -5.0, 5.0, 50.0))
    assert s[0] > s[1] > s[2] > s[3], "More negative mag → higher score"

def test_mag_contextual_local_minimum():
    s = score_mag_contextual(arr(-20.0, 0.0, 20.0), mag_mean=0.0, mag_std=10.0)
    assert s[0] > s[1] > s[2]

# ── Hard veto ──────────────────────────────────────────────────────────────
def test_hard_veto_amphibolite(kayad_config):
    lv = arr(2, 1, 1)
    scores = arr(95.0, 90.0, 85.0)
    result = apply_hard_veto(scores, lv, kayad_config)
    assert result[0] <= 20.0, "Amphibolite must be capped at 20"
    assert result[1] == 90.0, "QMS must be unaffected"
    assert result[2] == 85.0, "QMS must be unaffected"

# ── Score classification ────────────────────────────────────────────────────
def test_score_classes(kayad_config):
    scores = arr(80.0, 65.0, 50.0, 35.0, 20.0)
    classes = score_to_class(scores, kayad_config)
    assert list(classes) == [4, 3, 2, 1, 0], \
        "Expected [VH, H, M, L, VL] = [4,3,2,1,0]"

# ── Score range invariant ───────────────────────────────────────────────────
def test_proximity_score_in_range(kayad_config):
    E, N = cells()
    inputs = {
        'lv': arr(1,1,1,1,1,1,1,1,1,1),
        'pg': arr(6,6,6,6,6,6,6,6,6,6),
        'csr': arr(20,20,20,20,20,20,20,20,20,20),
        'grav': np.full(10, -0.05, dtype=np.float32),
        'grav_raw': np.full(10, -0.05, dtype=np.float32),
        'grav_gradient': np.full(10, 0.0005, dtype=np.float32),
        'grav_laplacian': np.full(10, -0.0001, dtype=np.float32),
        'mag': np.full(10, -5.0, dtype=np.float32),
        'mag_gradient': np.full(10, 0.05, dtype=np.float32),
        'cell_E': E, 'cell_N': N, 'z_mrl': 185.0, 'regime_id': 2,
        'dist_ore': np.full(10, 50.0, dtype=np.float32),
        'ore_area': 30000.0,
        'grav_mean': 0.0, 'grav_std': 0.05,
        'mag_mean': 5.0, 'mag_std': 15.0,
        'gg_mean': 0.0003, 'gg_std': 0.0002,
        'lap_std': 0.00005, 'mg_p50': 0.04,
        'block_model_df': None,
    }
    result = compute_proximity(inputs, kayad_config)
    assert 0 <= result['score'].min() <= result['score'].max() <= 100, \
        "All proximity scores must be in [0, 100]"
    result_b = compute_blind(inputs, kayad_config)
    assert 0 <= result_b['score'].min() <= result_b['score'].max() <= 100, \
        "All blind scores must be in [0, 100]"

def test_novelty_decreases_near_ore(kayad_config):
    s = score_novelty(arr(1000.0, 500.0, 200.0, 50.0), kayad_config)
    assert s[0] > s[1] > s[2] > s[3], \
        "Novelty score must decrease as distance to known ore decreases"
```

**Run Sprint 3 tests:**
```bash
pytest test/test_scoring.py -v --tb=short
```

---

### Sprint 4 — Data Loader & Validation

**Goal:** Data validation gives clear, actionable error messages. Never crashes on bad input.

#### `algorithms/alg_load_data.py`

```python
# -*- coding: utf-8 -*-
"""Algorithm: Load & Validate Data — first step in any prospectivity run."""
import os, traceback
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterFile,
    QgsProcessingParameterBoolean,
    QgsProcessingOutputString,
    QgsProcessingContext,
    QgsProcessingFeedback,
    Qgis,
)


def tr(msg):
    return QCoreApplication.translate('LoadDataAlgorithm', msg)


class LoadDataAlgorithm(QgsProcessingAlgorithm):
    CONFIG   = 'CONFIG'
    STRICT   = 'STRICT'
    RESULT   = 'RESULT'
    SUMMARY  = 'SUMMARY'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            self.CONFIG,
            tr('Project configuration file (.json)'),
            QgsProcessingParameterFile.File,
            extension='json',
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.STRICT,
            tr('Strict mode — fail on any warning (recommended for production)'),
            defaultValue=False,
        ))
        self.addOutput(QgsProcessingOutputString(self.RESULT, tr('Result status')))
        self.addOutput(QgsProcessingOutputString(self.SUMMARY, tr('Validation summary')))

    def processAlgorithm(self, parameters, context, feedback):
        config_path = self.parameterAsFile(parameters, self.CONFIG, context)
        strict = self.parameterAsBoolean(parameters, self.STRICT, context)
        feedback.setProgress(0)

        # ── Load config ───────────────────────────────────────────────────
        try:
            from ..core.config import ProjectConfig
            cfg = ProjectConfig.from_json(config_path)
        except Exception as e:
            feedback.reportError(
                tr(f'Cannot load configuration: {e}\n'
                   f'Check that the file exists and is valid JSON.'), fatalError=True)
            return {self.RESULT: 'FAILED', self.SUMMARY: str(e)}

        feedback.setProgress(20)
        if feedback.isCanceled():
            return {}

        # ── Validate data ─────────────────────────────────────────────────
        try:
            from ..modules.m01_data_loader import DataLoader
            loader = DataLoader(cfg)
            issues = []

            # Validate drill files
            for label, path in [
                ('Collar CSV', cfg.drill.collar_csv),
                ('Assay CSV',  cfg.drill.assay_csv),
                ('Litho CSV',  cfg.drill.litho_csv),
            ]:
                if not path:
                    issues.append(f'WARNING: {label} path not set')
                elif not os.path.exists(path):
                    issues.append(f'ERROR: {label} file not found: {path}')
                else:
                    feedback.pushInfo(f'✓ {label}: {os.path.basename(path)}')

            feedback.setProgress(50)
            if feedback.isCanceled():
                return {}

            # Validate geophysics
            for label, folder in [
                ('Gravity TIF folder',   cfg.geophysics.gravity_folder),
                ('Magnetics TIF folder', cfg.geophysics.magnetics_folder),
            ]:
                if not folder:
                    issues.append(f'WARNING: {label} not set')
                elif not os.path.isdir(folder):
                    issues.append(f'ERROR: {label} not found: {folder}')
                else:
                    import glob
                    tifs = glob.glob(os.path.join(folder, '**', '*.tif'), recursive=True)
                    if not tifs:
                        issues.append(f'WARNING: {label} contains no .tif files: {folder}')
                    else:
                        feedback.pushInfo(f'✓ {label}: {len(tifs)} TIF files')

            feedback.setProgress(80)
            if feedback.isCanceled():
                return {}

            # Report issues
            errors   = [i for i in issues if i.startswith('ERROR')]
            warnings = [i for i in issues if i.startswith('WARNING')]

            for w in warnings:
                feedback.pushWarning(w)
            for e in errors:
                feedback.reportError(e)

            if errors or (strict and warnings):
                status = 'FAILED'
                feedback.reportError(
                    tr(f'Validation FAILED with {len(errors)} errors, '
                       f'{len(warnings)} warnings.'), fatalError=False)
            else:
                status = 'PASSED'
                feedback.pushInfo(
                    tr(f'✓ Validation PASSED ({len(warnings)} warnings)'))

            feedback.setProgress(100)
            summary = f'{len(errors)} errors, {len(warnings)} warnings'
            return {self.RESULT: status, self.SUMMARY: summary}

        except Exception as e:
            feedback.reportError(
                tr(f'Unexpected error during validation: {e}'), fatalError=True)
            feedback.pushWarning(traceback.format_exc())
            return {self.RESULT: 'ERROR', self.SUMMARY: str(e)}

    def name(self):           return 'loaddata'
    def displayName(self):    return tr('1 — Load & Validate Data')
    def group(self):          return 'Bhumi3DMapper'
    def groupId(self):        return 'bhumi3dmapper'
    def shortHelpString(self):
        return tr('Validates all input data files (drill CSVs, geophysics TIFs) '
                  'and reports any missing or invalid inputs before running the '
                  'prospectivity analysis.')
    def createInstance(self): return LoadDataAlgorithm()
```

#### `test/test_data_loader.py`

```python
# -*- coding: utf-8 -*-
"""Sprint 4 — DataLoader tests using synthetic data."""
import os, sys, csv, pytest, tempfile
import numpy as np
from PIL import Image

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)

@pytest.fixture
def synthetic_data(tmp_path):
    """Create minimal valid synthetic Kayad-style inputs."""
    # Collar CSV
    collar = tmp_path / 'collar.csv'
    with open(collar, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['BHID','XCOLLAR','YCOLLAR','ZCOLLAR','DEPTH'])
        w.writerow(['KYD001', 469500, 2934900, 460, 250])
        w.writerow(['KYD002', 469600, 2935000, 455, 200])

    # Litho CSV
    litho = tmp_path / 'litho.csv'
    with open(litho, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['BHID','FROM','TO','WIDTH','ROCKCODE'])
        w.writerow(['KYD001', 0,  50,  50, 'QMS'])
        w.writerow(['KYD001', 50, 100, 50, 'PG'])
        w.writerow(['KYD001', 100, 150, 50, 'CSR'])
        w.writerow(['KYD001', 150, 250, 100, 'QMS'])
        w.writerow(['KYD002', 0, 200, 200, 'QMS'])

    # Assay CSV
    assay = tmp_path / 'assay.csv'
    with open(assay, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['BHID','FROM','TO','WIDTH','ZN','PB'])
        w.writerow(['KYD001', 0,  10, 10, 12.5, 1.2])
        w.writerow(['KYD001', 10, 20, 10, 8.3,  0.8])

    # Gravity TIFs (small 50×50, 3 levels)
    grav_dir = tmp_path / 'gravity'
    grav_dir.mkdir()
    for mrl in [185, 210, 235]:
        arr = np.random.uniform(-0.2, 0.5, (50, 50)).astype(np.float32)
        img = Image.fromarray(arr, mode='F')
        img.save(str(grav_dir / f'gravity_{mrl}.tif'))

    # Magnetics TIFs
    mag_dir = tmp_path / 'magnetics'
    mag_dir.mkdir()
    for mrl in [185, 210, 235]:
        arr = np.random.uniform(-50, 100, (10, 10)).astype(np.float32)
        img = Image.fromarray(arr / 1e4, mode='F')
        img.save(str(mag_dir / f'mag_{mrl}.tif'))

    return {
        'collar': str(collar),
        'litho':  str(litho),
        'assay':  str(assay),
        'grav_dir': str(grav_dir),
        'mag_dir':  str(mag_dir),
    }

@pytest.fixture
def configured_config(synthetic_data, tmp_path):
    from core.config import ProjectConfig
    cfg = ProjectConfig(project_name='SyntheticTest')
    cfg.drill.collar_csv = synthetic_data['collar']
    cfg.drill.litho_csv  = synthetic_data['litho']
    cfg.drill.assay_csv  = synthetic_data['assay']
    cfg.geophysics.gravity_folder   = synthetic_data['grav_dir']
    cfg.geophysics.magnetics_folder = synthetic_data['mag_dir']
    cfg.grid.nx = 50; cfg.grid.ny = 50  # small for speed
    return cfg

def test_collar_loads(configured_config):
    from modules.m01_data_loader import DataLoader
    loader = DataLoader(configured_config)
    df = loader.load_collar()
    assert len(df) == 2
    assert 'XCOLLAR' in df.columns

def test_litho_loads_with_lcodes(configured_config):
    from modules.m01_data_loader import DataLoader
    loader = DataLoader(configured_config)
    df = loader.load_litho()
    assert len(df) > 0
    assert 'lcode' in df.columns
    assert 1 in df['lcode'].values  # QMS = 1

def test_gravity_loads(configured_config):
    from modules.m01_data_loader import DataLoader
    loader = DataLoader(configured_config)
    grids = loader.load_gravity()
    assert len(grids) == 3
    assert 185 in grids
    assert grids[185].shape == (50, 50)

def test_validation_passes_with_good_data(configured_config):
    from modules.m01_data_loader import DataLoader
    loader = DataLoader(configured_config)
    result = loader.validate_all()
    assert result is True

def test_validation_fails_gracefully_bad_path(configured_config):
    """Missing files should not raise — should return False with clear message."""
    configured_config.drill.collar_csv = '/nonexistent/path/collar.csv'
    from modules.m01_data_loader import DataLoader
    loader = DataLoader(configured_config)
    result = loader.validate_all()
    assert result is False  # should return False, not raise

def test_empty_litho_rock_code_defaults_to_zero():
    """Unknown rock codes should default to 0, not crash."""
    from modules.m01_data_loader import DataLoader
    from core.config import ProjectConfig
    cfg = ProjectConfig()
    loader = DataLoader(cfg)
    result = loader._classify_rock_code('UNKNOWN_ROCK')
    assert result == 0
```

**Run Sprint 4 tests:**
```bash
pytest test/test_data_loader.py -v --tb=short
```

---

### Sprint 5 — GeoPackage Writer

**Goal:** GPKGs are valid, correctly structured, and loadable in QGIS.

#### `test/test_gpkg.py`

```python
# -*- coding: utf-8 -*-
"""Sprint 5 — GeoPackage writer tests."""
import os, sys, sqlite3, struct, pytest
import numpy as np

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)

REQUIRED_FIELDS = [
    'mrl', 'regime', 'regime_name', 'litho_code', 'litho_name',
    'pg_dist_m', 'csr_standoff', 'grav_mGal', 'grav_gradient',
    'grav_laplacian', 'mag_uSI', 'mag_gradient', 'dist_ore_m',
    'prox_c1', 'prox_c2', 'prox_c3', 'prox_c4', 'prox_c5',
    'prox_c6', 'prox_c7', 'prox_c9', 'prox_c10',
    'prox_score', 'prox_class_id',
    'blind_c1', 'blind_c2', 'blind_c3', 'blind_c4', 'blind_c5',
    'blind_c6', 'blind_c7b', 'blind_c8', 'blind_c9_lap', 'blind_c10',
    'blind_score', 'blind_class_id', 'dist_ore_m', 'novel_target',
]

@pytest.fixture
def synthetic_gpkg(tmp_path, kayad_config):
    """Write a minimal GPKG for 5×5 cells at mRL 185."""
    from modules.m05_gpkg_writer import write_level_gpkg
    n = 25  # 5×5 test grid
    cell_E = np.array([469500.0 + i*5 for i in range(n)], dtype=np.float32)
    cell_N = np.array([2934900.0 + i*5 for i in range(n)], dtype=np.float32)
    geo = {
        'lv':  np.ones(n, dtype=np.uint8),
        'pg':  np.full(n, 6.0, dtype=np.float32),
        'csr': np.full(n, 20.0, dtype=np.float32),
        'grav': np.full(n, -0.05, dtype=np.float32),
        'grav_raw': np.full(n, -0.05, dtype=np.float32),
        'grav_gradient': np.full(n, 0.0005, dtype=np.float32),
        'grav_laplacian': np.full(n, -0.0001, dtype=np.float32),
        'mag':  np.full(n, -5.0, dtype=np.float32),
        'mag_gradient': np.full(n, 0.05, dtype=np.float32),
        'dist_ore': np.linspace(10, 1000, n).astype(np.float32),
        'regime_id': 2,
        'grav_mean': 0.0, 'grav_std': 0.05,
        'mag_mean': 5.0, 'mag_std': 15.0,
        'gg_mean': 0.0003, 'gg_std': 0.0002,
        'lap_std': 0.00005, 'mg_p50': 0.04,
    }
    prox = {
        'c1': np.ones(n, dtype=np.float32),
        'c2': np.full(n, 0.8, dtype=np.float32),
        'c3': np.full(n, 0.9, dtype=np.float32),
        'c4': np.full(n, 0.75, dtype=np.float32),
        'c5': np.full(n, 0.7, dtype=np.float32),
        'c6': np.full(n, 0.95, dtype=np.float32),
        'c7': np.full(n, 0.85, dtype=np.float32),
        'c9': np.full(n, 0.75, dtype=np.float32),
        'c10': np.full(n, 0.8, dtype=np.float32),
        'score': np.full(n, 82.5, dtype=np.float32),
        'class': np.full(n, 4, dtype=np.uint8),
    }
    blind = {
        'c1': np.ones(n, dtype=np.float32),
        'c2': np.full(n, 0.8, dtype=np.float32),
        'c3': np.full(n, 0.9, dtype=np.float32),
        'c4': np.full(n, 0.7, dtype=np.float32),
        'c5': np.full(n, 0.65, dtype=np.float32),
        'c6': np.full(n, 0.95, dtype=np.float32),
        'c7b': np.full(n, 0.75, dtype=np.float32),
        'c8':  np.full(n, 0.7, dtype=np.float32),
        'c9_lap': np.full(n, 0.8, dtype=np.float32),
        'c10': np.full(n, 0.6, dtype=np.float32),
        'score': np.full(n, 79.0, dtype=np.float32),
        'class': np.full(n, 3, dtype=np.uint8),
    }
    path = str(tmp_path / 'test_mRL+185.gpkg')
    write_level_gpkg(path, 185.0, prox, blind, geo, cell_E, cell_N, kayad_config)
    return path

def test_gpkg_file_created(synthetic_gpkg):
    assert os.path.exists(synthetic_gpkg), "GPKG file was not created"
    assert os.path.getsize(synthetic_gpkg) > 1000, "GPKG file is suspiciously small"

def test_gpkg_is_valid_sqlite(synthetic_gpkg):
    con = sqlite3.connect(synthetic_gpkg)
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM gpkg_contents").fetchall()]
    assert len(tables) > 0, "GPKG has no layers in gpkg_contents"
    con.close()

def test_gpkg_has_geometry_column(synthetic_gpkg):
    con = sqlite3.connect(synthetic_gpkg)
    rows = con.execute("SELECT * FROM gpkg_geometry_columns").fetchall()
    assert len(rows) > 0, "No geometry columns registered"
    con.close()

def test_gpkg_row_count(synthetic_gpkg):
    con = sqlite3.connect(synthetic_gpkg)
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM gpkg_contents").fetchall()]
    count = con.execute(f"SELECT COUNT(*) FROM [{tables[0]}]").fetchone()[0]
    assert count == 25, f"Expected 25 cells, got {count}"
    con.close()

def test_gpkg_required_fields_present(synthetic_gpkg):
    con = sqlite3.connect(synthetic_gpkg)
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM gpkg_contents").fetchall()]
    cols = [r[1] for r in con.execute(
        f"PRAGMA table_info([{tables[0]}])").fetchall()]
    for field in ['prox_score', 'blind_score', 'prox_class_id', 'blind_class_id',
                  'litho_code', 'litho_name', 'regime_name', 'dist_ore_m']:
        assert field in cols, f"Required field missing: {field}"
    con.close()

def test_gpkg_score_range_valid(synthetic_gpkg):
    con = sqlite3.connect(synthetic_gpkg)
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM gpkg_contents").fetchall()]
    rows = con.execute(
        f"SELECT prox_score, blind_score FROM [{tables[0]}]").fetchall()
    for ps, bs in rows:
        assert 0 <= ps <= 100, f"prox_score out of range: {ps}"
        assert 0 <= bs <= 100, f"blind_score out of range: {bs}"
    con.close()

def test_gpkg_novel_target_column(synthetic_gpkg):
    """novel_target should be 1 where dist_ore_m > novelty threshold."""
    con = sqlite3.connect(synthetic_gpkg)
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM gpkg_contents").fetchall()]
    rows = con.execute(
        f"SELECT dist_ore_m, novel_target FROM [{tables[0]}]").fetchall()
    for dist, novel in rows:
        if dist > 500:
            assert novel == 1, f"dist={dist}m should be novel=1, got {novel}"
        else:
            assert novel == 0, f"dist={dist}m should be novel=0, got {novel}"
    con.close()

def test_gpkg_srs_registered(synthetic_gpkg):
    con = sqlite3.connect(synthetic_gpkg)
    srids = [r[0] for r in con.execute(
        "SELECT srs_id FROM gpkg_spatial_ref_sys").fetchall()]
    assert 32643 in srids, "EPSG:32643 not registered in gpkg_spatial_ref_sys"
    con.close()
```

**Run Sprint 5 tests:**
```bash
pytest test/test_gpkg.py -v --tb=short
```

---

### Sprint 6 — Integration Test (Full Pipeline, No QGIS)

**Goal:** Run the full pipeline on synthetic data end-to-end. Verify output files are correct.

#### `test/test_integration.py`

```python
# -*- coding: utf-8 -*-
"""Sprint 6 — Full pipeline integration test without QGIS."""
import os, sys, sqlite3, pytest
import numpy as np
from PIL import Image

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PLUGIN_DIR)

@pytest.fixture(scope='module')
def full_pipeline_output(tmp_path_factory, synthetic_data):
    """Run full pipeline on 3 mRL levels and return output dir."""
    tmp = tmp_path_factory.mktemp('pipeline')
    from core.config import ProjectConfig

    cfg = ProjectConfig(project_name='IntegrationTest', crs_epsg=32643)
    cfg.drill.collar_csv = synthetic_data['collar']
    cfg.drill.litho_csv  = synthetic_data['litho']
    cfg.drill.assay_csv  = synthetic_data['assay']
    cfg.geophysics.gravity_folder   = synthetic_data['grav_dir']
    cfg.geophysics.magnetics_folder = synthetic_data['mag_dir']
    cfg.geophysics.gravity_pixel_size_m   = 5.0
    cfg.geophysics.magnetics_pixel_size_m = 30.0
    cfg.grid.xmin = 469490.0; cfg.grid.ymin = 2934890.0
    cfg.grid.nx = 50; cfg.grid.ny = 50
    cfg.grid.z_top_mrl = 235.0; cfg.grid.z_bot_mrl = 185.0; cfg.grid.dz_m = 25.0
    cfg.outputs.output_dir = str(tmp)
    cfg.outputs.project_name = 'IntegrationTest'

    # Save config
    config_path = str(tmp / 'config.json')
    cfg.to_json(config_path)

    # Run pipeline steps
    from modules.m01_data_loader import DataLoader
    from modules.m02_drill_processor import DrillProcessor
    from modules.m03_geophys_processor import GeophysicsProcessor
    from modules.m04_scoring_engine import compute_proximity, compute_blind
    from modules.m05_gpkg_writer import write_level_gpkg

    loader = DataLoader(cfg)
    collar_df = loader.load_collar()
    litho_df  = loader.load_litho()
    grav_grids = loader.load_gravity()
    mag_grids  = loader.load_magnetics()

    dp = DrillProcessor(cfg)
    dp.build_lookups(collar_df, litho_df)

    gp = GeophysicsProcessor(cfg)
    gp.load(grav_grids, mag_grids)

    import math
    all_ore_E = np.array([469500.0], dtype=np.float32)
    all_ore_N = np.array([2934900.0], dtype=np.float32)
    cols = np.arange(cfg.grid.nx); rows = np.arange(cfg.grid.ny)
    CC, CR = np.meshgrid(cols, rows)
    cell_E = (cfg.grid.xmin + (CC+0.5)*cfg.grid.cell_size_m).ravel().astype(np.float32)
    cell_N = (cfg.grid.ymin + (CR+0.5)*cfg.grid.cell_size_m).ravel().astype(np.float32)
    dE = cell_E[:,None] - all_ore_E[None,:]
    dN = cell_N[:,None] - all_ore_N[None,:]
    dist_ore = np.sqrt(dE**2+dN**2).min(axis=1).astype(np.float32)

    gpkg_paths = []
    for z in [185.0, 210.0, 235.0]:
        gf = gp.at_level(z)
        lv, pg, csr = dp.geology_at_level(z)
        inputs = {
            'lv': lv, 'pg': pg, 'csr': csr,
            'grav': gf['grav'], 'grav_raw': gf.get('grav_raw', gf['grav']),
            'grav_gradient': gf['grav_gradient'],
            'grav_laplacian': gf['grav_laplacian'],
            'mag': gf['mag'], 'mag_gradient': gf['mag_gradient'],
            'cell_E': cell_E, 'cell_N': cell_N,
            'z_mrl': z, 'regime_id': 2,
            'dist_ore': dist_ore, 'ore_area': 30000.0,
            'grav_mean': gf['grav_mean'], 'grav_std': gf['grav_std'],
            'mag_mean': gf['mag_mean'], 'mag_std': gf['mag_std'],
            'gg_mean': gf['gg_mean'], 'gg_std': gf['gg_std'],
            'lap_std': gf['lap_std'], 'mg_p50': gf['mg_p50'],
            'block_model_df': None,
        }
        prox = compute_proximity(inputs, cfg)
        blind = compute_blind(inputs, cfg)
        geo = {**gf, 'lv': lv, 'pg': pg, 'csr': csr,
               'dist_ore': dist_ore, 'regime_id': 2}
        path = str(tmp / f'IntegrationTest_Prospectivity_mRL{int(z):+04d}.gpkg')
        write_level_gpkg(path, z, prox, blind, geo, cell_E, cell_N, cfg)
        gpkg_paths.append(path)

    return {'config_path': config_path, 'output_dir': str(tmp),
            'gpkg_paths': gpkg_paths, 'cfg': cfg}

def test_pipeline_creates_3_gpkgs(full_pipeline_output):
    for path in full_pipeline_output['gpkg_paths']:
        assert os.path.exists(path), f"GPKG not created: {path}"

def test_pipeline_gpkgs_have_correct_cell_count(full_pipeline_output):
    cfg = full_pipeline_output['cfg']
    expected = cfg.grid.nx * cfg.grid.ny
    for path in full_pipeline_output['gpkg_paths']:
        con = sqlite3.connect(path)
        tables = [r[0] for r in con.execute(
            "SELECT table_name FROM gpkg_contents").fetchall()]
        count = con.execute(f"SELECT COUNT(*) FROM [{tables[0]}]").fetchone()[0]
        assert count == expected, f"{path}: expected {expected} cells, got {count}"
        con.close()

def test_pipeline_scores_are_valid(full_pipeline_output):
    for path in full_pipeline_output['gpkg_paths']:
        con = sqlite3.connect(path)
        tables = [r[0] for r in con.execute(
            "SELECT table_name FROM gpkg_contents").fetchall()]
        rows = con.execute(
            f"SELECT prox_score, blind_score FROM [{tables[0]}]").fetchall()
        for ps, bs in rows:
            assert 0 <= ps <= 100
            assert 0 <= bs <= 100
        con.close()

def test_pipeline_amphibolite_veto(full_pipeline_output):
    """All amphibolite cells must be capped at score 20."""
    for path in full_pipeline_output['gpkg_paths']:
        con = sqlite3.connect(path)
        tables = [r[0] for r in con.execute(
            "SELECT table_name FROM gpkg_contents").fetchall()]
        bad = con.execute(
            f"SELECT COUNT(*) FROM [{tables[0]}] "
            f"WHERE litho_code=2 AND prox_score > 20").fetchone()[0]
        assert bad == 0, f"{path}: {bad} amphibolite cells have prox_score > 20"
        con.close()

def test_pipeline_config_json_saved(full_pipeline_output):
    import json
    with open(full_pipeline_output['config_path']) as f:
        data = json.load(f)
    assert data['project_name'] == 'IntegrationTest'
    assert data['crs_epsg'] == 32643
```

**Run Sprint 6 tests:**
```bash
pytest test/test_integration.py -v --tb=short
```

---

### Sprint 7 — Qt6 Compatibility & Production Hardening

**Goal:** Zero Qt5-specific imports. All code handles errors gracefully.

#### Production hardening rules (apply to all files)

1. **Every user-visible function wraps its body in `try/except Exception`** and reports to QGIS message bar, not just raises.

2. **All file I/O is wrapped** — missing files return `None` or `False` with a descriptive message, never raise `FileNotFoundError` to the user.

3. **All numpy operations handle NaN** — use `np.nanmean`, `np.nanstd`, not `np.mean`.

4. **All algorithm `processAlgorithm()` methods check `feedback.isCanceled()`** at least every 10% progress.

5. **Every QgsTask background function** catches all exceptions, logs them, and sets a failure flag rather than raising.

6. **Layer loading never silently fails** — always check `layer.isValid()` and report if False.

#### Qt6 compatibility checklist (run after every commit)

```bash
# Check for any direct PyQt5/PyQt6 imports
grep -rn "from PyQt5\|import PyQt5\|from PyQt6\|import PyQt6" bhumi3dmapper/ \
    --include="*.py" | grep -v test | grep -v __pycache__
# Expected output: nothing (zero matches)

# Run automated migration checker
pyqt5_to_pyqt6.py --dry_run --logfile qt6_check.log bhumi3dmapper/
grep -c "ISSUE\|ERROR" qt6_check.log || echo "No issues found"
```

#### `test/test_qt_compat.py`

```python
# -*- coding: utf-8 -*-
"""Sprint 7 — Qt5/Qt6 compatibility checks. No QGIS needed."""
import os, sys, re, pytest

PLUGIN_DIR = os.path.dirname(os.path.dirname(__file__))

FORBIDDEN_PATTERNS = [
    r'from PyQt5\b',
    r'import PyQt5\b',
    r'from PyQt6\b',   # also forbidden — must use qgis.PyQt
    r'import PyQt6\b',
]

def get_plugin_py_files():
    files = []
    for root, dirs, fnames in os.walk(PLUGIN_DIR):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'test')]
        for fname in fnames:
            if fname.endswith('.py'):
                files.append(os.path.join(root, fname))
    return files

@pytest.mark.parametrize('py_file', get_plugin_py_files())
def test_no_direct_qt_imports(py_file):
    """All Qt imports must go through qgis.PyQt for dual compatibility."""
    content = open(py_file, encoding='utf-8', errors='ignore').read()
    for pattern in FORBIDDEN_PATTERNS:
        matches = re.findall(pattern, content)
        assert not matches, (
            f"{os.path.relpath(py_file, PLUGIN_DIR)} contains forbidden import: "
            f"{matches[0]}\n"
            f"Replace with: from qgis.PyQt import ...")

def test_qgsapplication_import_style():
    """QgsApplication must be imported from qgis.core, not directly."""
    for py_file in get_plugin_py_files():
        content = open(py_file, encoding='utf-8', errors='ignore').read()
        if 'QgsApplication' in content:
            assert 'from qgis.core import' in content or \
                   'from qgis import' in content, \
                f"{py_file}: QgsApplication import style may be incompatible"
```

**Run Sprint 7 tests:**
```bash
pytest test/test_qt_compat.py -v
```

---

### Sprint 8 — Packaging & Final CI

**Goal:** Installable ZIP that works on clean QGIS 3.28+.

#### `Makefile` (Windows-compatible via `nmake` or `make`)

```makefile
PLUGIN_NAME = bhumi3dmapper
VERSION = 1.0.0
ZIP_NAME = $(PLUGIN_NAME)_v$(VERSION).zip

.PHONY: all test clean package

all: test package

test:
    pytest $(PLUGIN_NAME)/test/ -v --tb=short

compile_resources:
    pyrcc5 $(PLUGIN_NAME)/resources.qrc -o $(PLUGIN_NAME)/resources_rc.py

package: compile_resources
    zip -r $(ZIP_NAME) $(PLUGIN_NAME)/ \
        --exclude '*/test/*' \
        --exclude '*/__pycache__/*' \
        --exclude '*.pyc' \
        --exclude '*.git*' \
        --exclude '*/conftest.py'
    @echo "Built: $(ZIP_NAME)"

clean:
    rm -f $(ZIP_NAME)
    find $(PLUGIN_NAME) -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
    find $(PLUGIN_NAME) -name '*.pyc' -delete 2>/dev/null || true
```

#### `.github/workflows/ci.yml`

```yaml
name: Bhumi3DMapper CI
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    name: Unit & Integration Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install numpy pandas Pillow scipy pytest pytest-cov

      - name: Run all tests (no QGIS needed)
        run: |
          pytest bhumi3dmapper/test/ -v --tb=short \
            --cov=bhumi3dmapper \
            --cov-report=term-missing \
            --cov-fail-under=80

      - name: Qt6 compatibility check
        run: |
          # Check for direct PyQt5/6 imports
          HITS=$(grep -rn "from PyQt5\|import PyQt5\|from PyQt6\|import PyQt6" \
            bhumi3dmapper/ --include="*.py" | grep -v test | grep -v __pycache__ | wc -l)
          echo "Forbidden Qt imports found: $HITS"
          test $HITS -eq 0 || (echo "FAIL: Remove direct PyQt imports" && exit 1)

  build:
    name: Build ZIP Package
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install pyrcc5
        run: sudo apt-get install -y pyqt5-dev-tools
      - name: Compile resources
        run: pyrcc5 bhumi3dmapper/resources.qrc -o bhumi3dmapper/resources_rc.py
      - name: Create installable ZIP
        run: |
          zip -r bhumi3dmapper_v1.0.0.zip bhumi3dmapper/ \
            --exclude '*/test/*' --exclude '*/__pycache__/*' \
            --exclude '*.pyc' --exclude '*.git*'
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: bhumi3dmapper-zip
          path: bhumi3dmapper_v1.0.0.zip
```

---

### Run All Tests (Complete Suite)

```bash
# From the directory containing bhumi3dmapper/
pytest bhumi3dmapper/test/ -v --tb=short

# With coverage
pytest bhumi3dmapper/test/ -v --cov=bhumi3dmapper --cov-report=term-missing

# Specific sprint
pytest bhumi3dmapper/test/test_scoring.py -v

# Qt compat only
pytest bhumi3dmapper/test/test_qt_compat.py -v
```

---

### QGIS 4.0 Port Checklist (October 2026)

When QGIS 4.2 LTR ships, run these steps:

- [ ] Run `pyqt5_to_pyqt6.py bhumi3dmapper/` (automated migration script)
- [ ] Test on QGIS 4.0 using OSGeo4W Qt6 build
- [ ] Update `qgisMinimumVersion=3.28` stays; add `qgisMaximumVersion=4.99`
- [ ] Replace `pyrcc5` with `pyrcc6` in Makefile and CI
- [ ] Run full test suite — all tests should pass unchanged
- [ ] Submit updated ZIP to QGIS Plugin Repository

---

### Kayad Reference Values for All Tests

| Parameter | Value |
|-----------|-------|
| CRS | EPSG:32643 |
| Grid origin | xmin=468655, ymin=2932890 |
| Grid | nx=482, ny=722, cell=5m, 145 Z-levels |
| Z range | mRL −260 to +460 at 5m |
| N28°E corridor anchor | E469519 / N2934895 / mRL 185 |
| Plunge (shallow) | 30°/075°E, 122m E per 100m down |
| N315°E deep anchor | E470210 / N2935041 / mRL −140 |
| Plunge (deep) | 12°/063°E, 410m E per 100m down |
| Peak proximity score | 90.6 at mRL 310 |
| Peak blind score | 93.0 at mRL 435 (E470148/N2936252) |
| Novelty threshold | 500 m from any known ore centroid |

---

*Bhumi3DMapper — Autonomous Development Prompt v1.0 · March 2026 · QGIS 3.44 LTR · Qt5/Qt6 dual-compatible*

---

## v2.0 Development Plan — Mineral Discovery as Primary Objective

> **Detailed Job Cards:** See `Bhumi3DMapper_JobCards_v2.md` for the full 22-card sequenced development plan with exact line numbers, acceptance criteria, and dependency graph.  
> **Summary below. The job cards file is the authoritative source.**

> **Lead:** Satya  
> **Date:** 2026-04-17  
> **Status:** Draft for Team Review  
> **Review required by:** Full AiRE Team

### Executive Summary

Bhumi3DMapper v1.0.0 is a working QGIS plugin with 53 passing tests, covering the full pipeline from data loading to scored GeoPackage output. However, the code review reveals **4 critical issues** that directly compromise mineral discovery accuracy, **6 high-priority issues** that limit the tool to Kayad-only use, and several medium-priority improvements needed for production readiness.

**The biggest risk to mineral discovery:** The scoring engine and drill processor contain Kayad-specific hardcoded values throughout. Any user running this on a different deposit will get silently wrong results. The drill hole desurvey is missing entirely, meaning all subsurface geology is vertically projected from collar — potentially hundreds of meters off at depth.

### Current State Assessment

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

### Phase 1 — Critical Fixes (Mineral Discovery Accuracy)

These issues directly produce **wrong prospectivity maps**. Must be fixed before any field use.

#### JC-1.1: Implement Drill Hole Desurvey
- **File:** `modules/m02_drill_processor.py`
- **Problem:** Survey data is loaded by `m01_data_loader.py` but **never used**. All subsurface positions are computed as `z_collar - from_depth` (vertical projection). For deviated holes, the actual XYZ position depends on azimuth and dip. At 500m depth with 10° deviation, geology is assigned ~87m from its true position.
- **Fix:** Implement minimum-curvature desurvey using survey (BHID, DEPTH, AZI, DIP). Compute true XYZ for each interval midpoint. Update `geology_at_level()` to use desurveyed coordinates.
- **Impact:** HIGH — affects every criterion that depends on spatial position of drill data (C1 lithology, C2 PG halo, C3 CSR standoff, C9 grade model)
- **Effort:** 3–5 days
- **Tests needed:** Desurvey of known vertical hole (identity), 45° hole, S-curved hole

#### JC-1.2: Fix Gravity Gradient Scoring Dead Code
- **File:** `modules/m04_scoring_engine.py`, `score_gravity_gradient()`
- **Problem:** Conditions evaluated in wrong order. The `grav_grad > g80` branch catches everything above the 80th percentile, making `grav_grad > g90` **unreachable dead code**. Cells with very high gradient score 0.55 instead of intended 0.35.
- **Fix:** Reorder conditions: check g90 before g80, or use `elif` chain from highest to lowest.
- **Impact:** MEDIUM-HIGH — inflates blind model scores in high-gradient zones
- **Effort:** 1 hour
- **Tests needed:** Add test with values above g90; verify correct score (0.35)

#### JC-1.3: Fix Ore Polygon Area Calculation
- **File:** `modules/m01_data_loader.py`, line ~150
- **Problem:** `'area': len(xs) * 25` counts vertices × 25 sq.m. Not a valid area calculation. Corrupts ore-envelope equivalent radius in C10 scoring.
- **Fix:** Implement Shoelace formula or use `shapely.Polygon.area`.
- **Impact:** HIGH — directly affects ore_envelope proximity scoring (C10) and novelty classification
- **Effort:** 2 hours
- **Tests needed:** Known polygon area (rectangle, triangle, irregular)

#### JC-1.4: Replace PIL with Rasterio/GDAL for TIF Loading
- **File:** `modules/m01_data_loader.py`
- **Problem:** PIL/Pillow has **no CRS awareness, no geotransform, no nodata handling**. If a gravity TIF has a different origin or pixel size, values are silently assigned to wrong grid cells.
- **Fix:** Replace `Image.open()` with `rasterio.open()`. Read CRS, transform, nodata. Validate against `ProjectConfig.grid`. Resample if needed.
- **Impact:** HIGH — spatial misregistration invalidates C4 (gravity), C5 (magnetics), C7b/C8 (gradients), C9 (Laplacian)
- **Effort:** 2–3 days
- **Tests needed:** TIF with known geotransform; mismatched CRS detection; nodata handling
- **Note:** Adds `rasterio` dependency (usually available in QGIS Python)

### Phase 2 — Deposit-Agnostic Generalisation

These issues mean the plugin **only works correctly for Kayad**. Fixing them enables mineral discovery at any deposit.

#### JC-2.1: Move All Hardcoded Thresholds to Config
- **Files:** `m04_scoring_engine.py`, `m02_drill_processor.py`, `m05_gpkg_writer.py`
- **Problem:** PG halo distances, CSR standoff distances, gravity/magnetic thresholds, plunge proximity distances, structural/footwall rock codes, litho score tables, regime/class name dicts — all hardcoded to Kayad.
- **Fix:** Add `ScoringThresholds` dataclass to `core/config.py`. Kayad values become the default preset.
- **Impact:** HIGH — without this, any non-Kayad project gets meaningless scores
- **Effort:** 3–4 days
- **Tests needed:** Scoring with non-default thresholds; config roundtrip with custom thresholds

#### JC-2.2: Config Preset System (Deposit Templates)
- **File:** `core/config.py` (new: `core/presets/`)
- **Fix:** Create preset configs for: **SEDEX Pb-Zn** (current), **VMS Cu-Zn**, **Epithermal Au**, **Porphyry Cu-Mo**
- **Impact:** HIGH — makes the tool usable for the deposits that matter most for discovery
- **Effort:** 5–7 days (requires geological input per deposit type)

#### JC-2.3: Complete Config Widget for All Geological Parameters
- **File:** `ui/config_widget.py`
- **Fix:** Add tabbed config editor: Project & Grid | Deposit Type & Lithology | Scoring Weights (sliders) | Structural Corridors (map picker) | Depth Regimes
- **Impact:** MEDIUM-HIGH — without this, only expert users can configure for new deposits
- **Effort:** 5–7 days

#### JC-2.4: Fix Import Bugs in UI Files
- **Files:** `ui/dock_panel.py` (lines 141, 156, 207), `ui/wizard.py` (lines 83–88, 122–125, 136–139, 224–227)
- **Fix:** Change `from .core.config` → `from ..core.config` in dock_panel; replace `sys.path` hacking with relative imports in wizard.
- **Impact:** HIGH — plugin UI crashes on use
- **Effort:** 1 hour

### Phase 3 — Production Hardening

#### JC-3.1: Non-blocking UI with QgsTask
- **Files:** `ui/wizard.py`, `ui/dock_panel.py`, `algorithms/alg_run_scoring.py`
- **Fix:** Wrap computation in `QgsTask` subclass with progress bar and cancellation.
- **Effort:** 3–4 days

#### JC-3.2: GPKG Performance — Batch Writing + Spatial Index
- **File:** `modules/m05_gpkg_writer.py`
- **Fix:** Vectorise with numpy, use `executemany()`, add RTree spatial index.
- **Effort:** 2–3 days

#### JC-3.3: Deduplicate Scoring Pipeline
- **Files:** `algorithms/alg_run_scoring.py`, `modules/m06_voxel_builder.py`
- **Fix:** Extract shared `compute_level()` function.
- **Effort:** 1–2 days

#### JC-3.4: Proper Nodata Handling and Warning System
- **Files:** `m01_data_loader.py`, `m03_geophys_processor.py`
- **Fix:** Remove global warning suppression. Use `np.nan` consistently. Add data quality report.
- **Effort:** 2 days

#### JC-3.5: Fix Config z_levels Float Boundary Issue
- **File:** `core/config.py`
- **Fix:** Replace `np.arange` with `np.linspace` or integer-step approach.
- **Effort:** 1 hour

### Phase 4 — Test Coverage for Discovery Confidence

#### JC-4.1: Add Regime Transition Tests
- Test regime 0 (deep) and regime 1 (transition with 30% confidence discount).
- **Effort:** 2–3 days

#### JC-4.2: Add Voxel Builder Tests
- `m06_voxel_builder.py` has zero tests.
- **Effort:** 2–3 days

#### JC-4.3: Fix _classify_rock_code Phantom Test
- `test_data_loader.py` calls `loader._classify_rock_code()` which doesn't exist.
- **Effort:** 1 hour

#### JC-4.4: Add Golden-File Regression Tests
- Create reference dataset with pre-computed expected scores. Assert exact match.
- **Effort:** 2–3 days

#### JC-4.5: Add Boundary Value and NaN Input Tests
- NaN, inf, zero-length arrays, exact threshold boundaries.
- **Effort:** 1–2 days

### Phase 5 — Feature Expansion for Discovery

#### JC-5.1: Symbology Files (.qml/.sld)
- Pre-built QGIS styles for prospectivity classification. **Effort:** 1–2 days

#### JC-5.2: Layer Grouping in Results Loading
- Group levels in QGIS layer tree. **Effort:** 1 day

#### JC-5.3: 3D Layered Mesh (UGRID/MDAL) Export
- Native QGIS 3D viewer support. **Effort:** 5–7 days

#### JC-5.4: QGIS 4.0 (Qt6) Full Port Test
- Run migration script and test. **Effort:** 2–3 days

#### JC-5.5: Plugin Repository Submission
- Icon, docs, QGIS Plugin Repository. **Effort:** 3–5 days

### Sprint Schedule (Proposed)

| Sprint | Duration | Job Cards | Focus |
|--------|----------|-----------|-------|
| **S9** | 1 week | JC-1.2, JC-1.3, JC-2.4, JC-3.5, JC-4.3 | Quick critical fixes |
| **S10** | 2 weeks | JC-1.1, JC-1.4 | Desurvey + GDAL migration |
| **S11** | 2 weeks | JC-2.1, JC-2.2 | Deposit-agnostic scoring |
| **S12** | 2 weeks | JC-2.3, JC-3.1 | Config UI + async processing |
| **S13** | 1 week | JC-3.2, JC-3.3, JC-3.4 | Performance + cleanup |
| **S14** | 2 weeks | JC-4.1, JC-4.2, JC-4.4, JC-4.5 | Test coverage |
| **S15** | 2 weeks | JC-5.1–JC-5.5 | Features + release |

**Total estimated: ~12 weeks to production-ready v2.0**

### Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Rasterio not available in target QGIS Python | Medium | High | Fall back to GDAL bindings (always available in QGIS) |
| Desurvey implementation introduces new bugs | Medium | High | Validate against known Kayad drill hole trajectories |
| Preset configs for non-SEDEX deposits need geological review | High | High | Engage domain experts per deposit type before release |
| Qt6 migration breaks UI | Low | Medium | Maintain Qt5 as primary; Qt6 port in parallel branch |
| Performance insufficient for grids >1M cells | Medium | Medium | Profile hot paths; consider Cython for scoring engine |

### Decision Points for Team Review

1. **Do we fix desurvey (JC-1.1) before any field deployment?** Recommendation: YES
2. **Which deposit types for v2.0 presets?** Recommendation: SEDEX + VMS + Epithermal + Porphyry
3. **Rasterio vs GDAL bindings?** Recommendation: Rasterio with GDAL fallback
4. **3D mesh export now or v3.0?** Recommendation: Defer
5. **Ship intermediate v1.1.0 with Sprint 9 quick fixes?** Recommendation: YES

---

*This plan to be reviewed by the full team with the lens: "Does every job card serve the primary objective of mineral discovery?"*

*Satya to lead prioritisation and assignment in the team meeting.*
