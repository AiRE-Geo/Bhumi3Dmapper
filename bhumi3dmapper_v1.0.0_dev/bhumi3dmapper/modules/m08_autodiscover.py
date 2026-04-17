# -*- coding: utf-8 -*-
"""
Module 08 — Project Folder Autodiscovery
=========================================
Scans a project root folder for drill, geophysics, and polygon files using
common naming conventions. Returns a populated config.
Pure Python, no QGIS imports.
"""
import os
import re
import glob
from typing import Dict, List, Optional


# Filename patterns in priority order (first match wins)
COLLAR_PATTERNS  = ['collar*.csv', '*_collar.csv', 'holes*.csv', 'hole*.csv',
                    'drillhole*.csv', 'dh_collar*.csv', '*collar*.csv']
ASSAY_PATTERNS   = ['assay*.csv', '*_assay.csv', 'grades*.csv', 'grade*.csv',
                    'samples*.csv', '*assay*.csv']
LITHO_PATTERNS   = ['litho*.csv', '*_litho.csv', 'lithology*.csv', 'geology*.csv',
                    'rocks*.csv', '*litho*.csv']
SURVEY_PATTERNS  = ['survey*.csv', '*_survey.csv', 'deviation*.csv',
                    'surveys*.csv', '*survey*.csv']

GRAVITY_FOLDER_PATTERNS   = ['gravity', 'grav', 'gr', 'grav_inversions',
                             'gravity_slices', 'grav_slices']
MAGNETICS_FOLDER_PATTERNS = ['magnetics', 'mag', 'ms', 'magnetic_susceptibility',
                             'mag_inversions', 'mag_slices', 'susceptibility']
POLYGON_FOLDER_PATTERNS   = ['ore_polygons', 'ore', 'mineralisation', 'polygons',
                             'lenses', 'ore_shapes']


def _find_first_match(folder: str, patterns: List[str]) -> List[str]:
    """Return all files in folder matching any pattern. Case-insensitive."""
    matches = []
    for pat in patterns:
        for f in glob.iglob(os.path.join(folder, '**', pat), recursive=True):
            if os.path.isfile(f) and f not in matches:
                matches.append(f)
        # Also try uppercase variants on case-sensitive filesystems
        for f in glob.iglob(os.path.join(folder, '**', pat.upper()), recursive=True):
            if os.path.isfile(f) and f not in matches:
                matches.append(f)
    return matches


def _find_folder(root: str, patterns: List[str]) -> Optional[str]:
    """Find subfolder matching any pattern. Returns first match or None (legacy)."""
    candidates = _find_folder_candidates(root, patterns)
    return candidates[0] if candidates else None


def _find_folder_candidates(root: str, patterns: List[str]) -> List[str]:
    """Find ALL subfolders matching any pattern, searched up to 2 levels deep."""
    if not os.path.isdir(root):
        return []
    results = []
    try:
        for entry in sorted(os.listdir(root)):
            full = os.path.join(root, entry)
            if not os.path.isdir(full):
                continue
            entry_lower = entry.lower()
            for pat in patterns:
                if pat.lower() in entry_lower:
                    if full not in results:
                        results.append(full)
                    break
    except (PermissionError, OSError):
        pass
    # Recurse one level deeper
    try:
        for entry in sorted(os.listdir(root)):
            full = os.path.join(root, entry)
            if not os.path.isdir(full):
                continue
            try:
                for entry2 in sorted(os.listdir(full)):
                    full2 = os.path.join(full, entry2)
                    if not os.path.isdir(full2):
                        continue
                    for pat in patterns:
                        if pat.lower() in entry2.lower():
                            if full2 not in results:
                                results.append(full2)
                            break
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        pass
    return results


def _contains_tifs(folder: str) -> int:
    """Count .tif files in folder (recursive)."""
    if not folder or not os.path.isdir(folder):
        return 0
    return len(list(glob.iglob(os.path.join(folder, '**', '*.tif'), recursive=True)))


def autodiscover(project_root: str) -> Dict:
    """
    Scan project_root recursively; return dict of discovered paths and ambiguities.

    Returns:
        {
            'collar_csv': str or None,
            'assay_csv': str or None,
            'litho_csv': str or None,
            'survey_csv': str or None,
            'gravity_folder': str or None,
            'magnetics_folder': str or None,
            'polygon_folder': str or None,
            'ambiguous': List[Dict],      # multiple candidates needing user choice
            'warnings': List[str],        # non-fatal issues
            'scan_root': str,
        }
    """
    result = {
        'collar_csv': None, 'assay_csv': None, 'litho_csv': None,
        'survey_csv': None, 'gravity_folder': None, 'magnetics_folder': None,
        'polygon_folder': None,
        'ambiguous': [],
        'warnings': [],
        'scan_root': project_root,
    }

    if not os.path.isdir(project_root):
        result['warnings'].append(f"Project root does not exist: {project_root}")
        return result

    # Find drill CSVs
    for key, patterns in [
        ('collar_csv', COLLAR_PATTERNS),
        ('assay_csv',  ASSAY_PATTERNS),
        ('litho_csv',  LITHO_PATTERNS),
        ('survey_csv', SURVEY_PATTERNS),
    ]:
        matches = _find_first_match(project_root, patterns)
        if len(matches) == 1:
            result[key] = matches[0]
        elif len(matches) > 1:
            # Multiple candidates → ambiguous, do NOT guess
            result['ambiguous'].append({
                'field': key,
                'candidates': [
                    {'path': m, 'mtime': os.path.getmtime(m),
                     'size': os.path.getsize(m)}
                    for m in matches
                ]
            })
            result['warnings'].append(
                f"Multiple {key} candidates found — user must choose: "
                f"{', '.join(os.path.basename(m) for m in matches)}")
        # zero matches → leave as None (no warning; might not apply)

    # Find geophysics and polygon folders
    for key, patterns in [
        ('gravity_folder',   GRAVITY_FOLDER_PATTERNS),
        ('magnetics_folder', MAGNETICS_FOLDER_PATTERNS),
        ('polygon_folder',   POLYGON_FOLDER_PATTERNS),
    ]:
        candidates = _find_folder_candidates(project_root, patterns)
        if not candidates:
            continue

        # For geophysics folders, prefer candidates that actually contain TIFs
        if key in ('gravity_folder', 'magnetics_folder'):
            tif_candidates = [c for c in candidates if _contains_tifs(c) > 0]
            if tif_candidates:
                result[key] = tif_candidates[0]
                if len(tif_candidates) > 1:
                    result['warnings'].append(
                        f"Multiple {key} candidates with TIFs found: "
                        f"{', '.join(os.path.basename(c) for c in tif_candidates)}. "
                        f"Using first match.")
            else:
                result['warnings'].append(
                    f"Found folder(s) matching {key} but none contain .tif files: "
                    f"{', '.join(os.path.basename(c) for c in candidates)}")
        else:
            # Polygon folders — just pick first match
            result[key] = candidates[0]

    return result


def apply_to_config(cfg, discovered: Dict) -> List[str]:
    """
    Apply discovered paths to a ProjectConfig. Returns list of human-readable change descriptions.
    Only applies unambiguous matches — caller must resolve ambiguities first.
    """
    changes = []
    if discovered.get('collar_csv'):
        cfg.drill.collar_csv = discovered['collar_csv']
        changes.append(f"Collar CSV: {os.path.basename(discovered['collar_csv'])}")
    if discovered.get('assay_csv'):
        cfg.drill.assay_csv = discovered['assay_csv']
        changes.append(f"Assay CSV: {os.path.basename(discovered['assay_csv'])}")
    if discovered.get('litho_csv'):
        cfg.drill.litho_csv = discovered['litho_csv']
        changes.append(f"Litho CSV: {os.path.basename(discovered['litho_csv'])}")
    if discovered.get('survey_csv'):
        cfg.drill.survey_csv = discovered['survey_csv']
        changes.append(f"Survey CSV: {os.path.basename(discovered['survey_csv'])}")
    if discovered.get('gravity_folder'):
        cfg.geophysics.gravity_folder = discovered['gravity_folder']
        changes.append(f"Gravity folder: {os.path.basename(discovered['gravity_folder'])}")
    if discovered.get('magnetics_folder'):
        cfg.geophysics.magnetics_folder = discovered['magnetics_folder']
        changes.append(f"Magnetics folder: {os.path.basename(discovered['magnetics_folder'])}")
    if discovered.get('polygon_folder'):
        cfg.ore_polygons.polygon_folder = discovered['polygon_folder']
        changes.append(f"Ore polygon folder: {os.path.basename(discovered['polygon_folder'])}")
    return changes
