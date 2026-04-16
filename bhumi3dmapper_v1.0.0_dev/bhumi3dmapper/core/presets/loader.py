# -*- coding: utf-8 -*-
"""Load deposit-type preset configurations."""
import json
import os

PRESETS_DIR = os.path.dirname(__file__)

def list_presets() -> list:
    """Return list of available preset names."""
    return [f[:-5] for f in os.listdir(PRESETS_DIR)
            if f.endswith('.json') and not f.startswith('_')]

def load_preset(name: str) -> dict:
    """Load a preset by name, returns dict of ScoringThresholdsConfig overrides."""
    path = os.path.join(PRESETS_DIR, f"{name}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Preset '{name}' not found at {path}")
    with open(path) as f:
        return json.load(f)

def _convert_int_keys(d):
    """Recursively convert string-numeric keys to int (JSON only has string keys)."""
    if not isinstance(d, dict):
        return d
    result = {}
    for k, v in d.items():
        try:
            k_int = int(k)
            result[k_int] = _convert_int_keys(v)
        except (ValueError, TypeError):
            result[k] = _convert_int_keys(v)
    return result

def apply_preset(cfg, preset_name: str):
    """Apply a named preset to a ProjectConfig object."""
    overrides = load_preset(preset_name)
    ct = cfg.criterion_thresholds
    for key, value in overrides.get('criterion_thresholds', {}).items():
        if hasattr(ct, key):
            # Convert string keys to int for dict fields like litho_scores
            if isinstance(value, dict):
                value = _convert_int_keys(value)
            setattr(ct, key, value)
    # Also update deposit_type metadata
    if 'deposit_type' in overrides:
        cfg.deposit_type = overrides['deposit_type']
    if 'description' in overrides:
        cfg.project_description = overrides.get('description', '')
    return cfg
