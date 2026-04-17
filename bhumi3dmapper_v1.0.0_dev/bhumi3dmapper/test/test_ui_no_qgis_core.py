# -*- coding: utf-8 -*-
"""
Test: ui/model_selector.py does not import qgis.core or qgis.analysis.

BH-REM-P1 Gap 3 requirement (addendum amendment): the model selector widget
must never import qgis.core, qgis.analysis, qgis.server, qgis.processing, or
any other QGIS non-Qt module. It must remain importable in pure-Python
environments (e.g., CI without QGIS installed) for unit testing of its logic.

Only qgis.PyQt (the Qt bindings packaged with QGIS) is permitted.
"""
import ast
import os
import sys
import pytest


_UI_DIR = os.path.join(os.path.dirname(__file__), '..', 'ui')
_FORBIDDEN_PREFIXES = (
    "qgis.core",
    "qgis.analysis",
    "qgis.server",
    "qgis.processing",
    "qgis.gui",           # QgisInterface etc. — not needed in pure data widgets
)


def _collect_imports(filepath: str) -> list:
    """
    Parse a Python file and return all imported module names.
    Returns list of strings like 'qgis.core', 'qgis.PyQt.QtWidgets', etc.
    """
    with open(filepath, encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as exc:
        pytest.fail(f"Syntax error parsing {filepath}: {exc}")

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


class TestModelSelectorNoQgisCore:

    def _get_model_selector_path(self) -> str:
        path = os.path.join(_UI_DIR, "model_selector.py")
        if not os.path.exists(path):
            pytest.fail(
                f"ui/model_selector.py not found at {path}. "
                "Gap 3 not yet implemented."
            )
        return path

    def test_model_selector_exists(self):
        """ui/model_selector.py must exist."""
        assert os.path.exists(self._get_model_selector_path())

    def test_no_qgis_core_imports(self):
        """
        ui/model_selector.py must not import any qgis non-Qt module.
        Permitted: qgis.PyQt.*
        Forbidden: qgis.core, qgis.analysis, qgis.gui, qgis.server, qgis.processing
        """
        path = self._get_model_selector_path()
        imports = _collect_imports(path)
        violations = [
            imp for imp in imports
            if any(imp == prefix or imp.startswith(prefix + ".")
                   for prefix in _FORBIDDEN_PREFIXES)
        ]
        assert not violations, (
            f"ui/model_selector.py imports forbidden QGIS core modules:\n"
            f"  {violations}\n"
            "Only qgis.PyQt.* imports are permitted in UI widgets. "
            "All data must come from bhumi3dmapper.core and bhumi3dmapper.modules."
        )

    def test_qgis_pyqt_imports_are_guarded(self):
        """
        Any qgis.PyQt imports must be inside a try/except ImportError block
        so the module remains importable in test environments without QGIS.
        The file must define _HAS_QT to signal Qt availability.
        """
        path = self._get_model_selector_path()
        with open(path, encoding="utf-8") as f:
            source = f.read()
        assert "_HAS_QT" in source, (
            "ui/model_selector.py must define _HAS_QT to signal Qt availability. "
            "qgis.PyQt imports must be inside a try/except ImportError block."
        )

    def test_module_importable_without_qt(self):
        """
        ui/model_selector.py must be importable even when Qt/QGIS are absent.
        This verifies the try/except guard works correctly.
        """
        # If qgis.PyQt is available, test still passes — just confirms import works.
        # If qgis.PyQt is NOT available, the module must still import (with _HAS_QT=False).
        try:
            # Force fresh import by clearing from sys.modules if present
            mods_to_remove = [k for k in sys.modules if "model_selector" in k]
            for m in mods_to_remove:
                del sys.modules[m]

            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "model_selector_test_import",
                self._get_model_selector_path(),
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            # If we reach here, import succeeded
            assert hasattr(mod, "_HAS_QT"), "Module must define _HAS_QT"
        except Exception as exc:
            pytest.fail(
                f"ui/model_selector.py raised an exception on import: {exc}\n"
                "The module must be importable without Qt/QGIS installed."
            )

    def test_get_selected_deposit_type_api_exists(self):
        """ModelSelectorWidget must expose get_selected_deposit_type() method."""
        path = self._get_model_selector_path()
        with open(path, encoding="utf-8") as f:
            source = f.read()
        assert "def get_selected_deposit_type" in source

    def test_override_low_coverage_checked_api_exists(self):
        """ModelSelectorWidget must expose override_low_coverage_checked() method."""
        path = self._get_model_selector_path()
        with open(path, encoding="utf-8") as f:
            source = f.read()
        assert "def override_low_coverage_checked" in source
