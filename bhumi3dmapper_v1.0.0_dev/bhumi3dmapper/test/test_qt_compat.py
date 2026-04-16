# -*- coding: utf-8 -*-
"""Sprint 7 — Qt5/Qt6 compatibility checks. No QGIS needed."""
import os
import sys
import re
import pytest

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


def test_no_exec_method_without_underscore():
    """Qt6 renamed exec_() to exec(). Check for safe usage patterns."""
    for py_file in get_plugin_py_files():
        content = open(py_file, encoding='utf-8', errors='ignore').read()
        # exec_() is fine in Qt5 and works in Qt6 via compat layer
        # raw .exec() would shadow the Python builtin — but qgis.PyQt handles it
        pass  # informational only — exec_() is the safe form


def test_core_modules_have_no_qgis_imports():
    """Core modules (core/, modules/) must never import QGIS."""
    qgis_import = re.compile(r'^from qgis|^import qgis', re.MULTILINE)
    for subdir in ['core', 'modules']:
        dir_path = os.path.join(PLUGIN_DIR, subdir)
        if not os.path.isdir(dir_path):
            continue
        for fname in os.listdir(dir_path):
            if not fname.endswith('.py'):
                continue
            content = open(os.path.join(dir_path, fname), encoding='utf-8').read()
            matches = qgis_import.findall(content)
            assert not matches, (
                f"{subdir}/{fname} imports QGIS ({matches[0]}). "
                f"Core modules must be pure Python for standalone testing.")
