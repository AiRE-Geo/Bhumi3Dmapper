# -*- coding: utf-8 -*-
"""
Module for loading and formatting contextual geological tooltips.
Tooltips are deposit-type-aware — a VMS user sees different examples than SEDEX.
Pure Python, no QGIS imports.
"""
import json
import os
from typing import Optional

TOOLTIPS_FILE = os.path.join(os.path.dirname(__file__), 'tooltips.json')
_cache: Optional[dict] = None


def _load() -> dict:
    global _cache
    if _cache is None:
        try:
            with open(TOOLTIPS_FILE, encoding='utf-8') as f:
                _cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _cache = {}
    return _cache


def get_tooltip(parameter: str, deposit_type: str = 'generic') -> str:
    """
    Return formatted HTML tooltip for a parameter under a deposit type.
    Falls back to generic if no deposit-specific entry exists.
    Returns empty string if parameter is unknown.
    """
    data = _load()
    p = data.get(parameter, {})
    generic = p.get('generic', {})
    specific = p.get(deposit_type, {}) if deposit_type != 'generic' else {}

    parts = []
    definition = specific.get('definition') or generic.get('definition')
    if definition:
        parts.append(f"<b>{definition}</b>")

    if generic.get('why'):
        parts.append(f"<i>Why it matters:</i> {generic['why']}")

    if specific.get('example'):
        parts.append(f"<i>Example:</i> {specific['example']}")

    if specific.get('suggestion'):
        parts.append(f"<i>Tip:</i> {specific['suggestion']}")

    if generic.get('range'):
        parts.append(f"<i>Typical range:</i> {generic['range']}")

    if generic.get('default'):
        parts.append(f"<i>Default:</i> {generic['default']}")

    return "<br><br>".join(parts) if parts else ""


def list_documented_parameters() -> list:
    """Return list of all parameter names that have tooltips defined."""
    return list(_load().keys())


def has_tooltip(parameter: str) -> bool:
    """Check whether a parameter has any tooltip content."""
    return parameter in _load()
