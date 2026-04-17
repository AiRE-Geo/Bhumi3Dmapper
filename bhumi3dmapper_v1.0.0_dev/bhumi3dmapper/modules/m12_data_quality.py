# -*- coding: utf-8 -*-
"""
Module 12 — Data Quality Checks (HARD GATE before scoring)
===========================================================
Runs comprehensive data quality checks on drill, geophysics, and grid
inputs before scoring begins. Surfaces issues to the user with clear
descriptions and suggested fixes.

This is a HARD GATE: scoring does NOT run until the user has seen and
acknowledged the data quality report. Critical issues block advancement
entirely. Warnings require explicit acknowledgement.

Pure Python, no QGIS imports.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import numpy as np


@dataclass
class DQIssue:
    category: str          # 'drill' | 'geophysics' | 'polygons' | 'grid'
    severity: str          # 'info' | 'warning' | 'critical'
    title: str             # one-line summary
    details: str           # full explanation
    action: str            # suggested fix
    affected: int = 0      # number of records/cells affected
    blocks_advance: bool = False  # True → user cannot proceed

    def to_dict(self):
        return {
            'category': self.category, 'severity': self.severity,
            'title': self.title, 'details': self.details,
            'action': self.action, 'affected': self.affected,
            'blocks_advance': self.blocks_advance,
        }


@dataclass
class DQReport:
    issues: List[DQIssue] = field(default_factory=list)
    n_checks_run: int = 0

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == 'critical')

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == 'warning')

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == 'info')

    @property
    def blocks_advance(self) -> bool:
        return any(i.blocks_advance for i in self.issues)

    @property
    def is_clean(self) -> bool:
        return self.warning_count == 0 and self.critical_count == 0

    def by_category(self) -> Dict[str, List[DQIssue]]:
        out = {}
        for i in self.issues:
            out.setdefault(i.category, []).append(i)
        return out

    def summary(self) -> str:
        if self.is_clean:
            return f"✓ All {self.n_checks_run} checks passed."
        parts = []
        if self.critical_count:
            parts.append(f"❗ {self.critical_count} critical")
        if self.warning_count:
            parts.append(f"⚠ {self.warning_count} warnings")
        if self.info_count:
            parts.append(f"ℹ {self.info_count} info")
        return f"{self.n_checks_run} checks. " + ", ".join(parts)


def check_drill_quality(collar_df, litho_df, assay_df, survey_df, cfg) -> List[DQIssue]:
    """Run all drill data quality checks. Returns list of issues."""
    issues = []

    # ── Collar checks ────────────────────────────────────────────
    if collar_df is None or len(collar_df) == 0:
        issues.append(DQIssue(
            category='drill', severity='critical',
            title='No drillholes loaded',
            details='The collar file is empty or could not be read.',
            action='Check the collar CSV path and format.',
            affected=0, blocks_advance=True,
        ))
        return issues  # cannot continue without collars

    n_holes = len(collar_df)

    # BHID column access (use column_mapping if present)
    bhid_col = cfg.drill.column_mapping.get('col_bhid', cfg.drill.col_bhid) \
        if hasattr(cfg.drill, 'column_mapping') and cfg.drill.column_mapping \
        else cfg.drill.col_bhid
    zcol = cfg.drill.column_mapping.get('col_zcollar', cfg.drill.col_zcollar) \
        if hasattr(cfg.drill, 'column_mapping') and cfg.drill.column_mapping \
        else cfg.drill.col_zcollar
    xcol = cfg.drill.column_mapping.get('col_xcollar', cfg.drill.col_xcollar) \
        if hasattr(cfg.drill, 'column_mapping') and cfg.drill.column_mapping \
        else cfg.drill.col_xcollar
    ycol = cfg.drill.column_mapping.get('col_ycollar', cfg.drill.col_ycollar) \
        if hasattr(cfg.drill, 'column_mapping') and cfg.drill.column_mapping \
        else cfg.drill.col_ycollar

    # Duplicate BHIDs
    if bhid_col in collar_df.columns:
        dup = int(collar_df[bhid_col].duplicated().sum())
        if dup > 0:
            issues.append(DQIssue(
                category='drill', severity='critical',
                title=f"{dup} duplicate borehole IDs in collar",
                details=f"Your collar file has {dup} BHIDs appearing more than once. "
                        f"This will cause incorrect spatial lookups.",
                action="Remove duplicates in the CSV, or assign unique IDs.",
                affected=dup, blocks_advance=True,
            ))

    # Missing collar elevations
    if zcol in collar_df.columns:
        missing_z = int(collar_df[zcol].isna().sum())
        if missing_z > 0:
            issues.append(DQIssue(
                category='drill', severity='warning',
                title=f"{missing_z} boreholes have no collar elevation",
                details=f"{missing_z} of {n_holes} holes are missing {zcol} values. "
                        f"Subsurface positions for these holes will be inaccurate.",
                action=f"Fill {zcol} values in the CSV or exclude these holes.",
                affected=missing_z,
            ))

    # Coordinate sanity — detect decimal-degree coordinates mistakenly labelled as UTM
    if xcol in collar_df.columns and ycol in collar_df.columns:
        import pandas as pd
        x_data = pd.to_numeric(collar_df[xcol], errors='coerce').dropna()
        y_data = pd.to_numeric(collar_df[ycol], errors='coerce').dropna()
        if len(x_data) > 0:
            x_range = float(x_data.max() - x_data.min())
            if x_range < 10 and abs(x_data.mean()) < 180:
                issues.append(DQIssue(
                    category='drill', severity='critical',
                    title='Collar coordinates look like decimal degrees, not UTM metres',
                    details=f"X coordinate range is only {x_range:.2f} — typical UTM range "
                            f"is thousands of metres.",
                    action='Your coordinates may be in lat/long. Re-project to UTM, '
                           'or update the CRS EPSG in the config to a geographic CRS.',
                    affected=n_holes, blocks_advance=True,
                ))

    # ── Litho checks ────────────────────────────────────────────
    if litho_df is not None and len(litho_df) > 0 and 'lcode' in litho_df.columns:
        # Unknown rock codes
        unknown = int((litho_df['lcode'] == 0).sum())
        unknown_pct = 100.0 * unknown / len(litho_df)
        if unknown_pct > 10:
            issues.append(DQIssue(
                category='drill',
                severity='warning' if unknown_pct < 30 else 'critical',
                title=f"{unknown_pct:.0f}% of litho intervals have unknown rock codes",
                details=f"{unknown} of {len(litho_df)} intervals mapped to 'Unknown'. "
                        f"These get default scores (0.25) which may reduce map quality.",
                action="Check your rock_codes dict in config — every rock name in the CSV "
                       "should be listed.",
                affected=unknown,
                blocks_advance=unknown_pct > 50,  # critical if majority unknown
            ))

        # Check for holes with no litho
        if bhid_col in litho_df.columns and bhid_col in collar_df.columns:
            collar_bhids = set(collar_df[bhid_col].dropna().astype(str))
            litho_bhids = set(litho_df[bhid_col].dropna().astype(str))
            holes_no_litho = len(collar_bhids - litho_bhids)
            if holes_no_litho > n_holes * 0.3:
                issues.append(DQIssue(
                    category='drill', severity='warning',
                    title=f"{holes_no_litho} boreholes have no litho data",
                    details=f"These holes will contribute nothing to lithology scoring.",
                    action='Check that all drilled holes are in the litho CSV.',
                    affected=holes_no_litho,
                ))

    # ── Assay checks ────────────────────────────────────────────
    if assay_df is not None and len(assay_df) > 0:
        zn_col = cfg.drill.column_mapping.get('col_zn', cfg.drill.col_zn) \
            if hasattr(cfg.drill, 'column_mapping') and cfg.drill.column_mapping \
            else cfg.drill.col_zn
        if zn_col in assay_df.columns:
            # Negative grades
            import pandas as pd
            zn_data = pd.to_numeric(assay_df[zn_col], errors='coerce')
            neg = int((zn_data < 0).sum())
            if neg > 0:
                issues.append(DQIssue(
                    category='drill', severity='critical',
                    title=f"{neg} negative {zn_col} values",
                    details='Negative grade values are invalid geological data.',
                    action='Values below detection limit should be 0 or small positive, '
                           'not negative. Check for data entry errors.',
                    affected=neg, blocks_advance=True,
                ))

            # Missing grades
            missing_zn = int(zn_data.isna().sum())
            miss_pct = 100.0 * missing_zn / len(assay_df)
            if miss_pct > 5:
                issues.append(DQIssue(
                    category='drill',
                    severity='warning' if miss_pct < 50 else 'critical',
                    title=f"{miss_pct:.0f}% of assay rows have no {zn_col} value",
                    details=f"{missing_zn} of {len(assay_df)} intervals have no grade.",
                    action='These will be treated as NaN during scoring. If these are '
                           'below detection limit, replace with 0 or a small positive value.',
                    affected=missing_zn,
                ))

    return issues


def check_geophysics_quality(grav_grids, mag_grids, cfg) -> List[DQIssue]:
    """Check geophysics grid quality."""
    issues = []

    # Missing geophysics
    if not grav_grids:
        issues.append(DQIssue(
            category='geophysics', severity='warning',
            title='No gravity data loaded',
            details='Gravity criteria (C4, C7b, C9) will not contribute to scoring. '
                    'Scores will be dominated by drill and magnetics criteria.',
            action='Add gravity TIFs to enable full scoring, or proceed without gravity.',
            affected=0,
        ))

    if not mag_grids:
        issues.append(DQIssue(
            category='geophysics', severity='warning',
            title='No magnetics data loaded',
            details='Magnetics criteria (C5, C8) will not contribute to scoring.',
            action='Add magnetics TIFs to enable full scoring, or proceed without.',
            affected=0,
        ))

    # Coverage vs requested levels
    try:
        expected = set(int(z) for z in cfg.grid.z_levels)
    except Exception:
        expected = set()

    for name, grids in [('gravity', grav_grids), ('magnetics', mag_grids)]:
        if not grids:
            continue
        actual = set(grids.keys())
        missing = expected - actual
        if expected and missing:
            coverage = 100.0 * len(actual & expected) / max(len(expected), 1)
            if coverage < 50:
                issues.append(DQIssue(
                    category='geophysics', severity='warning',
                    title=f"{name.capitalize()} covers only {coverage:.0f}% of requested levels",
                    details=f'{len(missing)} of {len(expected)} levels have no {name} TIF. '
                            f'Missing levels will be linearly interpolated.',
                    action=f'Add {name} TIFs for better coverage.',
                    affected=len(missing),
                ))

    # High nodata fraction per grid
    for name, grids in [('gravity', grav_grids), ('magnetics', mag_grids)]:
        if not grids:
            continue
        for mrl, arr in grids.items():
            if arr is None:
                continue
            try:
                nan_pct = 100.0 * float(np.isnan(arr).sum()) / float(arr.size)
            except Exception:
                continue
            if nan_pct > 30:
                issues.append(DQIssue(
                    category='geophysics',
                    severity='warning' if nan_pct < 70 else 'critical',
                    title=f'{name.capitalize()} at mRL {mrl}: {nan_pct:.0f}% nodata',
                    details=f'Large portions of this level have no {name} data.',
                    action='Check the source TIF, or accept that scores will have gaps '
                           'at this level.',
                    affected=int(arr.size * nan_pct / 100),
                ))

    return issues


def check_grid_quality(cfg) -> List[DQIssue]:
    """Check grid configuration."""
    issues = []
    g = cfg.grid

    # Very large grids (memory concern)
    n_cells = g.nx * g.ny
    try:
        n_levels = len(g.z_levels)
    except Exception:
        n_levels = 0
    total = n_cells * n_levels

    if total > 100_000_000:  # >100M cells
        issues.append(DQIssue(
            category='grid', severity='warning',
            title=f'Very large grid: {total:,} total cells',
            details=f'{g.nx}×{g.ny} × {n_levels} levels. Scoring will take a long time '
                    f'and require significant RAM.',
            action='Consider a larger cell size or fewer levels if possible.',
            affected=total,
        ))
    elif total == 0:
        issues.append(DQIssue(
            category='grid', severity='critical',
            title='Grid has zero cells',
            details='nx, ny, or z_levels is zero.',
            action='Set grid dimensions in config.',
            affected=0, blocks_advance=True,
        ))

    # Z range sanity
    if g.z_top_mrl <= g.z_bot_mrl:
        issues.append(DQIssue(
            category='grid', severity='critical',
            title='Invalid Z range: top ≤ bottom',
            details=f'z_top_mrl={g.z_top_mrl}, z_bot_mrl={g.z_bot_mrl}',
            action='Set z_top_mrl > z_bot_mrl in config.',
            affected=0, blocks_advance=True,
        ))

    # Cell size sanity
    if g.cell_size_m <= 0:
        issues.append(DQIssue(
            category='grid', severity='critical',
            title='Invalid cell size',
            details=f'cell_size_m={g.cell_size_m}',
            action='Set cell_size_m > 0.',
            affected=0, blocks_advance=True,
        ))

    return issues


def run_all_checks(cfg, collar_df=None, litho_df=None, assay_df=None,
                    survey_df=None, grav_grids=None, mag_grids=None) -> DQReport:
    """
    Run all data quality checks. Caller supplies already-loaded dataframes
    and grids so this function doesn't do I/O itself.
    Returns a DQReport.
    """
    report = DQReport()
    issues = []
    issues.extend(check_drill_quality(collar_df, litho_df, assay_df, survey_df, cfg))
    issues.extend(check_geophysics_quality(grav_grids or {}, mag_grids or {}, cfg))
    issues.extend(check_grid_quality(cfg))
    report.issues = issues
    # Rough count of checks run
    report.n_checks_run = 12  # approximate count of distinct checks
    return report
