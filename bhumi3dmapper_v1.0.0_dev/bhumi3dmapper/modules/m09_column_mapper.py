# -*- coding: utf-8 -*-
"""
Module 09 — Fuzzy Column Mapper
================================
Fuzzy-matches user CSV column names against required field aliases.
Supports any geological database naming convention.
Pure Python, no QGIS imports.
"""
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple


# Aliases for each required field. Extend for non-English conventions.
FIELD_ALIASES = {
    'col_bhid':    ['bhid', 'hole_id', 'holeid', 'dhid', 'drillhole', 'hole', 'borehole', 'hole_name', 'dh_id'],
    'col_xcollar': ['xcollar', 'east', 'easting', 'x', 'x_collar', 'utm_east', 'eastings', 'x_coord'],
    'col_ycollar': ['ycollar', 'north', 'northing', 'y', 'y_collar', 'utm_north', 'northings', 'y_coord'],
    'col_zcollar': ['zcollar', 'rl', 'elev', 'elevation', 'z', 'z_collar', 'altitude', 'collar_rl', 'topo'],
    'col_depth':   ['depth', 'max_depth', 'total_depth', 'td', 'eoh', 'hole_depth', 'final_depth'],
    'col_from':    ['from', 'from_m', 'depth_from', 'top', 'start_m', 'from_depth', 'interval_from'],
    'col_to':      ['to', 'to_m', 'depth_to', 'bottom', 'end_m', 'to_depth', 'interval_to'],
    'col_rockcode':['rockcode', 'rock_code', 'lith', 'lithology', 'rock_type', 'litho', 'lithcode', 'geology'],
    'col_azimuth': ['brg', 'bearing', 'azimuth', 'azi', 'az', 'dh_azi', 'collar_azi'],
    'col_dip':     ['dip', 'incl', 'inclination', 'angle', 'dh_dip', 'collar_dip'],
    'col_zn':      ['zn', 'zn_pct', 'zn_ppm', 'zinc', 'zn_grade', 'zn_assay'],
    'col_pb':      ['pb', 'pb_pct', 'pb_ppm', 'lead', 'pb_grade', 'pb_assay'],
    'col_ag':      ['ag', 'ag_ppm', 'ag_gt', 'silver', 'ag_grade', 'ag_assay'],
}

# Required vs optional mandatory fields (optional can be left unmapped)
REQUIRED_FIELDS = {
    'collar': ['col_bhid', 'col_xcollar', 'col_ycollar', 'col_zcollar'],
    'litho':  ['col_bhid', 'col_from', 'col_to', 'col_rockcode'],
    'assay':  ['col_bhid', 'col_from', 'col_to'],
    'survey': ['col_bhid', 'col_depth', 'col_azimuth', 'col_dip'],
}
OPTIONAL_FIELDS = {
    'collar': ['col_depth'],
    'litho':  [],
    'assay':  ['col_zn', 'col_pb', 'col_ag'],
    'survey': [],
}


def fuzzy_match(required_field: str, available_columns: List[str],
                 threshold: float = 0.70) -> List[Tuple[str, float]]:
    """
    Return list of (column_name, confidence) ranked by fuzzy similarity.
    Only returns matches above threshold.
    """
    aliases = FIELD_ALIASES.get(required_field, [required_field.replace('col_', '')])
    scored = []
    for col in available_columns:
        col_clean = col.strip().lower().replace(' ', '_').replace('-', '_')
        best = 0.0
        for alias in aliases:
            r = SequenceMatcher(None, col_clean, alias.lower()).ratio()
            if r > best:
                best = r
            # Exact match override
            if col_clean == alias.lower():
                best = 1.0
                break
        if best >= threshold:
            scored.append((col, best))
    return sorted(scored, key=lambda x: -x[1])


def auto_map(file_type: str, available_columns: List[str],
             threshold: float = 0.70) -> Dict[str, Optional[str]]:
    """
    Attempt to map every required+optional field for a file_type to a best-matching column.
    Returns dict {required_field: matched_column or None}.
    Prevents double-assignment: one column cannot map to two fields.
    """
    required = REQUIRED_FIELDS.get(file_type, [])
    optional = OPTIONAL_FIELDS.get(file_type, [])
    all_fields = required + optional
    mapping = {}
    used = set()

    # First pass: exact matches (confidence = 1.0)
    for field in all_fields:
        candidates = fuzzy_match(field, available_columns, threshold=0.99)
        for col, score in candidates:
            if col not in used:
                mapping[field] = col
                used.add(col)
                break

    # Second pass: fuzzy fill the rest
    for field in all_fields:
        if field in mapping:
            continue
        candidates = fuzzy_match(field, available_columns, threshold=threshold)
        for col, score in candidates:
            if col not in used:
                mapping[field] = col
                used.add(col)
                break
        else:
            mapping[field] = None

    return mapping


def preview_data(df, column: str, n_rows: int = 5) -> Dict:
    """Return a summary dict for a column: sample values, range, null count, dtype."""
    import pandas as pd
    if column not in df.columns:
        return {'error': f'Column {column} not in dataframe'}
    col_data = df[column]
    is_numeric = pd.api.types.is_numeric_dtype(col_data)
    return {
        'column': column,
        'sample': col_data.dropna().head(n_rows).tolist(),
        'min': float(col_data.min()) if is_numeric and col_data.notna().any() else None,
        'max': float(col_data.max()) if is_numeric and col_data.notna().any() else None,
        'n_unique': int(col_data.nunique()),
        'n_null': int(col_data.isna().sum()),
        'n_total': int(len(col_data)),
        'dtype': str(col_data.dtype),
        'is_numeric': is_numeric,
    }


def validate_mapping(mapping: Dict[str, Optional[str]],
                      file_type: str) -> Tuple[bool, List[str]]:
    """
    Check that all required fields have a mapping.
    Returns (is_valid, list_of_missing_required_fields).
    """
    required = REQUIRED_FIELDS.get(file_type, [])
    missing = [f for f in required if mapping.get(f) is None]
    return (len(missing) == 0, missing)


def sanity_check_column(df, column: str, required_field: str) -> List[str]:
    """
    Run sanity checks on a mapped column. Returns list of warnings.
    E.g., X coordinates in 0-90 range -> probably latitude not UTM.
    """
    import pandas as pd
    warnings = []
    if column not in df.columns:
        return warnings
    col_data = df[column]
    if not pd.api.types.is_numeric_dtype(col_data):
        # Check certain fields that must be numeric
        if required_field in ('col_xcollar', 'col_ycollar', 'col_zcollar',
                              'col_from', 'col_to', 'col_depth',
                              'col_azimuth', 'col_dip',
                              'col_zn', 'col_pb', 'col_ag'):
            warnings.append(f"{required_field}: column '{column}' is not numeric - "
                            f"check for text values or bad delimiters.")
        return warnings

    data = col_data.dropna()
    if len(data) == 0:
        return warnings

    mn, mx = float(data.min()), float(data.max())

    if required_field == 'col_xcollar':
        if -180 <= mn <= 180 and -180 <= mx <= 180:
            warnings.append(f"X coordinates range {mn:.2f} to {mx:.2f} - "
                            f"this looks like longitude (decimal degrees), not UTM metres. "
                            f"Check your CRS setting.")
    elif required_field == 'col_ycollar':
        if -90 <= mn <= 90 and -90 <= mx <= 90:
            warnings.append(f"Y coordinates range {mn:.2f} to {mx:.2f} - "
                            f"this looks like latitude (decimal degrees), not UTM metres. "
                            f"Check your CRS setting.")
    elif required_field == 'col_zn':
        if mx > 50:
            warnings.append(f"Zn values up to {mx:.1f} - if this is percent, values "
                            f"above 50% are unusual. If this is ppm, your Zn column "
                            f"should be named Zn_ppm for clarity.")
    elif required_field == 'col_dip':
        if mn < -90 or mx > 90:
            warnings.append(f"Dip values {mn:.1f} to {mx:.1f} are outside -90 to +90 range.")
    elif required_field == 'col_azimuth':
        if mn < 0 or mx > 360:
            warnings.append(f"Azimuth values {mn:.1f} to {mx:.1f} are outside 0 to 360 range.")

    return warnings
