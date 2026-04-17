# -*- coding: utf-8 -*-
"""
Bhumi3DMapper — Shared Repository Loader (Part B)
=================================================
Resolves the path to AiRE-DepositModels/ and loads deposit models with
JSON Schema v2 validation.

Resolution order:
  1. AIRE_DEPOSIT_MODELS environment variable
  2. Sibling-of-plugin-root directory walk
  3. Hardcoded Dropbox fallback
  4. SharedRepoNotFoundError

No QGIS imports permitted. Pure Python.

Decision context: Session 3 Orogenic Gold brainstorming (2026-04-17).
"It is scientifically indefensible to maintain two divergent weight sets
for the same deposit type across these two tools. One source of truth,
both tools read from it." — Amit Tripathi
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional


# ── Custom exceptions ──────────────────────────────────────────────────────────

class SharedRepoNotFoundError(RuntimeError):
    """Raised when AiRE-DepositModels/ cannot be located by any method."""
    pass


class DepositModelNotFoundError(KeyError):
    """Raised when a deposit_type is not registered in manifest.json."""
    pass


class SchemaValidationError(ValueError):
    """Raised when a model JSON fails deposit_model_schema_v2 validation."""
    pass


# ── Constants ─────────────────────────────────────────────────────────────────

_REPO_DIRNAME = "AiRE-DepositModels"

# Hardcoded last-resort path (Windows Dropbox path — update if moved)
_DROPBOX_FALLBACK = (
    r"E:\MPXG Exploration Dropbox\amit tripathi\CAGE-INdevelopment"
    r"\AiRE-QGIS-PluginRepository\AiRE-DepositModels"
)

# review_status prefixes that should be hidden or flagged in the UI
_HIDDEN_STATUSES = ("superseded_by_", "not_yet_brainstormed")
_WARN_STATUSES = ("pre_brainstorm_scaffold",)


# ── Path resolution ────────────────────────────────────────────────────────────

def _is_valid_repo(p: Path) -> bool:
    """True if p is a directory containing manifest.json."""
    return p.is_dir() and (p / "manifest.json").exists()


def get_repo_root() -> Path:
    """
    Resolve and return the AiRE-DepositModels repository root directory.

    Resolution order:
      1. AIRE_DEPOSIT_MODELS environment variable
      2. Walk up from this file's directory looking for a sibling AiRE-DepositModels/
      3. Hardcoded Dropbox fallback path

    Returns
    -------
    Path
        Absolute path to the validated AiRE-DepositModels/ directory.

    Raises
    ------
    SharedRepoNotFoundError
        If the repo cannot be located by any method.
    """
    # 1. Environment variable
    env_path = os.environ.get("AIRE_DEPOSIT_MODELS", "").strip()
    if env_path:
        p = Path(env_path)
        if _is_valid_repo(p):
            return p.resolve()
        raise SharedRepoNotFoundError(
            f"AIRE_DEPOSIT_MODELS is set to '{env_path}' but "
            f"manifest.json not found there. Check the path."
        )

    # 2. Sibling-of-plugin-root discovery
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        candidate = ancestor / _REPO_DIRNAME
        if _is_valid_repo(candidate):
            return candidate.resolve()

    # 3. Hardcoded Dropbox fallback
    fallback = Path(_DROPBOX_FALLBACK)
    if _is_valid_repo(fallback):
        return fallback.resolve()

    raise SharedRepoNotFoundError(
        f"Cannot locate '{_REPO_DIRNAME}'. Try one of:\n"
        "  1. Set env var AIRE_DEPOSIT_MODELS=<path-to-AiRE-DepositModels>\n"
        "  2. Ensure AiRE-DepositModels/ is a sibling of any parent directory "
        "of the Bhumi3DMapper plugin\n"
        f"  3. Check that the Dropbox path exists: {_DROPBOX_FALLBACK}"
    )


# ── Schema loading and validation ──────────────────────────────────────────────

def _load_schema() -> Optional[dict]:
    """
    Load JSON Schema v2 from the shared repo.
    Returns None if the schema file is missing (validation will fall back to
    basic required-field check).
    """
    try:
        schema_path = get_repo_root() / "schema" / "deposit_model_schema_v2.json"
        if schema_path.exists():
            with open(schema_path, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _validate_model_json(data: dict, schema: Optional[dict] = None) -> None:
    """
    Validate raw JSON data against deposit_model_schema_v2.

    Always performs basic required-field check first. If jsonschema is
    installed, also performs full JSON Schema v2 validation.

    Parameters
    ----------
    data : dict
        Raw parsed JSON from a model file.
    schema : dict, optional
        The JSON Schema dict. If None, attempts to load from shared repo.

    Raises
    ------
    SchemaValidationError
        If validation fails.
    """
    # ── Step 1: Always run basic required-field check (no external deps) ──
    required = ["deposit_type", "display_name", "description", "weights"]
    missing = [r for r in required if r not in data]
    if missing:
        raise SchemaValidationError(
            f"Model JSON '{data.get('deposit_type', '?')}' "
            f"missing required fields: {missing}"
        )

    # ── Step 2: Full JSON Schema v2 validation if jsonschema is available ──
    if schema is None:
        schema = _load_schema()

    if schema is None:
        return  # No schema file found — basic check already passed

    try:
        import jsonschema
        try:
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.ValidationError as e:
            raise SchemaValidationError(
                f"Schema v2 validation failed for "
                f"'{data.get('deposit_type', '?')}': {e.message}"
            ) from e
    except ImportError:
        pass  # jsonschema not installed — basic check already passed above


# ── Manifest API ───────────────────────────────────────────────────────────────

def load_manifest() -> dict:
    """
    Load and return the full manifest.json from the shared repository.

    Returns
    -------
    dict
        Parsed manifest.json contents.
    """
    manifest_path = get_repo_root() / "manifest.json"
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)


def list_models(
    include_statuses: Optional[List[str]] = None,
    exclude_statuses: Optional[List[str]] = None,
) -> List[dict]:
    """
    Return manifest model entries filtered by review_status prefix.

    Parameters
    ----------
    include_statuses : list[str], optional
        Only include entries whose review_status starts with one of these
        prefixes. Default: all non-hidden entries.
    exclude_statuses : list[str], optional
        Exclude entries whose review_status starts with one of these prefixes.
        Default: ('superseded_by_', 'not_yet_brainstormed').

    Returns
    -------
    list[dict]
        Filtered list of model entries from manifest["models"].
    """
    manifest = load_manifest()
    models = manifest.get("models", [])

    excludes = exclude_statuses if exclude_statuses is not None else list(_HIDDEN_STATUSES)

    result = []
    for m in models:
        status = m.get("review_status", "")
        if any(status.startswith(ex) for ex in excludes):
            continue
        if include_statuses and not any(status.startswith(inc) for inc in include_statuses):
            continue
        result.append(m)
    return result


def get_model_entry(deposit_type: str) -> dict:
    """
    Return the manifest entry for a specific deposit_type.

    Parameters
    ----------
    deposit_type : str
        Machine identifier (e.g., 'orogenic_au').

    Returns
    -------
    dict
        Manifest entry.

    Raises
    ------
    DepositModelNotFoundError
        If deposit_type is not in manifest.
    """
    manifest = load_manifest()
    for m in manifest.get("models", []):
        if m.get("deposit_type") == deposit_type:
            return m
    available = [m.get("deposit_type", "?") for m in manifest.get("models", [])]
    raise DepositModelNotFoundError(
        f"deposit_type '{deposit_type}' not found in manifest.json. "
        f"Available: {available}"
    )


# ── Model loading ──────────────────────────────────────────────────────────────

def _inject_shared_python(repo: Path) -> None:
    """Add shared repo python/ to sys.path if not already present."""
    python_dir = str(repo / "python")
    if python_dir not in sys.path:
        sys.path.insert(0, python_dir)


def load_deposit_model(deposit_type: str, validate: bool = True):
    """
    Load a DepositModel from the shared AiRE-DepositModels repository.

    Imports the shared DepositModel dataclass from python/deposit_model.py
    and loads the JSON for the given deposit_type with optional schema validation.

    Parameters
    ----------
    deposit_type : str
        Machine identifier (e.g., 'orogenic_au', 'ni_sulphide').
    validate : bool
        If True, validate against JSON Schema v2 before loading (default True).

    Returns
    -------
    DepositModel
        Loaded deposit model instance.

    Raises
    ------
    SharedRepoNotFoundError
        If the shared repo cannot be located.
    DepositModelNotFoundError
        If deposit_type is not in manifest or model file is missing.
    SchemaValidationError
        If JSON schema validation fails (when validate=True).
    """
    repo = get_repo_root()
    _inject_shared_python(repo)

    try:
        from deposit_model import DepositModel  # noqa: F401 (imported for return type)
    except ImportError as exc:
        raise SharedRepoNotFoundError(
            f"Cannot import DepositModel from '{repo / 'python'}'. "
            f"Ensure python/deposit_model.py exists in the shared repo. Error: {exc}"
        ) from exc

    entry = get_model_entry(deposit_type)
    model_path = repo / "models" / entry["file"]

    if not model_path.exists():
        raise DepositModelNotFoundError(
            f"Model JSON not found: {model_path} "
            f"(manifest file reference for '{deposit_type}')"
        )

    # Validate raw JSON before constructing dataclass
    with open(model_path, encoding="utf-8") as f:
        raw = json.load(f)

    if validate:
        schema = _load_schema()
        _validate_model_json(raw, schema)

    from deposit_model import DepositModel
    return DepositModel.from_json(str(model_path))


# ── UI helper ─────────────────────────────────────────────────────────────────

def get_ui_model_list() -> List[Dict[str, str]]:
    """
    Return a UI-ready list of model metadata for the model selector widget.

    Each entry includes: deposit_type, display_name, family, review_status,
    status_badge, primary_commodities, notes, show_warning (bool).

    Returns
    -------
    list[dict]
    """
    all_models = load_manifest().get("models", [])
    result = []
    for m in all_models:
        status = m.get("review_status", "")
        if status.startswith("superseded_by_"):
            badge = "Superseded"
        elif status.startswith("brainstorm_complete_"):
            badge = "Production"
        elif status == "not_yet_brainstormed":
            badge = "Coming Soon"
        elif status.startswith("pre_brainstorm_scaffold"):
            badge = "Preview (needs brainstorming)"
        else:
            badge = f"Status: {status}"

        show_warning = status.startswith(_WARN_STATUSES)
        commodities = ", ".join(m.get("primary_commodities", []))
        result.append({
            "deposit_type": m.get("deposit_type", ""),
            "display_name": m.get("display_name", ""),
            "family": m.get("family", ""),
            "review_status": status,
            "status_badge": badge,
            "show_warning": show_warning,
            "primary_commodities": commodities,
            "notes": m.get("notes", ""),
        })
    return result
