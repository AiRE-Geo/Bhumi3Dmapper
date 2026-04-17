# -*- coding: utf-8 -*-
"""
Plain-Language Error Translation
=================================
Converts raw Python exceptions into user-friendly error messages with
actionable suggestions, for display to field geologists.

The translate() function wraps any exception in a UserError that has:
  - message: what went wrong (geological/workflow language)
  - suggestion: specific action to take
  - technical: original exception (hidden by default)
  - severity: info | warning | error | critical

No QGIS imports — usable in algorithms/, ui/, and modules/.
"""
import os
from typing import Optional


class UserError(Exception):
    """Exception enriched with user-facing message and suggested action."""

    def __init__(self, message: str, suggestion: str,
                 technical: Optional[Exception] = None,
                 severity: str = 'error',
                 context: str = ''):
        self.message = message
        self.suggestion = suggestion
        self.technical = technical
        self.severity = severity  # 'info' | 'warning' | 'error' | 'critical'
        self.context = context
        super().__init__(f"{message} — {suggestion}")

    def to_dict(self):
        return {
            'message': self.message,
            'suggestion': self.suggestion,
            'severity': self.severity,
            'context': self.context,
            'technical': f"{type(self.technical).__name__}: {self.technical}" if self.technical else None,
        }


def translate(exc: Exception, context: str = '') -> UserError:
    """
    Translate a raw exception into a user-friendly UserError.
    Handles 15+ common exception types with geology-appropriate messages.
    """
    # Already translated
    if isinstance(exc, UserError):
        return exc

    msg = str(exc)

    # ── File system errors ─────────────────────────────────────────
    if isinstance(exc, FileNotFoundError):
        path = exc.filename or context or 'file'
        basename = os.path.basename(path) if path else 'file'
        return UserError(
            message=f"Cannot find: {basename}",
            suggestion=(
                f"Check that the path exists: {path}\n"
                f"If your project folder was moved, update the config or "
                f"use 'Scan Project Folder' to re-detect paths."
            ),
            technical=exc, context=context,
        )

    if isinstance(exc, PermissionError):
        path = exc.filename or context
        return UserError(
            message=f"Cannot read/write: {os.path.basename(path) if path else 'file'}",
            suggestion=(
                "The file may be open in another program (Excel, QGIS, "
                "Notepad). Close it and try again. On Windows, also check "
                "that you have write permission to the output folder."
            ),
            technical=exc, context=context,
        )

    if isinstance(exc, IsADirectoryError):
        return UserError(
            message=f"Expected a file but got a folder: {exc.filename}",
            suggestion="Select the specific file, not the folder containing it.",
            technical=exc, context=context,
        )

    # ── CSV / data errors ──────────────────────────────────────────
    if isinstance(exc, UnicodeDecodeError):
        return UserError(
            message="Cannot read the file — unusual text encoding",
            suggestion=(
                "Your CSV uses a non-standard text encoding. "
                "Open it in Excel and save as 'CSV UTF-8 (Comma delimited)'. "
                "This fixes most encoding issues."
            ),
            technical=exc, context=context,
        )

    if isinstance(exc, KeyError):
        col = str(exc).strip("'\"")
        return UserError(
            message=f"Missing required column: {col}",
            suggestion=(
                f"Your data file does not have a column named '{col}'.\n"
                f"Use 'Remap Columns' to point to the equivalent column in your file, "
                f"or rename the column in your CSV."
            ),
            technical=exc, context=context,
        )

    if isinstance(exc, (ValueError,)):
        # Check if it's a data conversion error
        if 'could not convert' in msg.lower() or 'invalid literal' in msg.lower():
            return UserError(
                message="A number column contains non-numeric values",
                suggestion=(
                    "Check that numeric columns (coordinates, grades, depths) do not contain "
                    "text like 'N/A' or '-'. Replace with empty cells or 0."
                ),
                technical=exc, context=context,
            )
        # Generic ValueError
        return UserError(
            message=f"Data problem: {msg}",
            suggestion="Check the input values. See technical details for specifics.",
            technical=exc, context=context,
        )

    # ── pandas-specific ───────────────────────────────────────────
    try:
        import pandas as pd
        if isinstance(exc, pd.errors.EmptyDataError):
            return UserError(
                message=f"The file is empty: {context or 'input file'}",
                suggestion=(
                    "Check the file in Excel. An empty CSV usually means the "
                    "export from your drill database failed — re-export and retry."
                ),
                technical=exc, context=context,
            )
        if isinstance(exc, pd.errors.ParserError):
            return UserError(
                message="Cannot parse the CSV — malformed structure",
                suggestion=(
                    "Open the file in Excel and check for: inconsistent column counts, "
                    "stray commas in text fields, or missing quotes around values with commas. "
                    "Re-save as CSV when fixed."
                ),
                technical=exc, context=context,
            )
    except ImportError:
        pass

    # ── sqlite (GPKG) errors ──────────────────────────────────────
    try:
        import sqlite3
        if isinstance(exc, sqlite3.OperationalError):
            if 'locked' in msg.lower():
                return UserError(
                    message="Output file is locked",
                    suggestion=(
                        "The GPKG file is open in QGIS or another program. "
                        "Close it there and try again."
                    ),
                    technical=exc, context=context,
                )
            return UserError(
                message=f"Database error: {msg}",
                suggestion="Check the technical details. If you cannot resolve, report this issue.",
                technical=exc, context=context, severity='critical',
            )
    except ImportError:
        pass

    # ── memory / resource errors ──────────────────────────────────
    if isinstance(exc, MemoryError):
        return UserError(
            message="Out of memory",
            suggestion=(
                "Your dataset is too large for available RAM. Try:\n"
                "• Reduce the grid size (smaller nx/ny)\n"
                "• Process fewer levels at once (set LEVELS in Run Scoring)\n"
                "• Close other programs"
            ),
            technical=exc, context=context, severity='critical',
        )

    # ── numeric / math errors ────────────────────────────────────
    if isinstance(exc, (ZeroDivisionError, ArithmeticError)):
        return UserError(
            message="Numerical error in scoring computation",
            suggestion=(
                "This usually indicates empty or invalid input data for a scoring criterion. "
                "Check that your geophysics grids have valid values."
            ),
            technical=exc, context=context,
        )

    # ── type errors (often a config issue) ─────────────────────────
    if isinstance(exc, TypeError):
        return UserError(
            message=f"Configuration type mismatch: {msg}",
            suggestion=(
                "Your config file has a value in the wrong format. "
                "Try creating a fresh config from a preset and re-applying your data paths."
            ),
            technical=exc, context=context,
        )

    # ── attribute errors ──────────────────────────────────────────
    if isinstance(exc, AttributeError):
        return UserError(
            message=f"Internal error: {msg}",
            suggestion=(
                "This is likely a plugin bug. Please report with the technical details "
                "at https://github.com/AiRE-Geo/Bhumi3Dmapper/issues"
            ),
            technical=exc, context=context, severity='critical',
        )

    # ── generic fallback ──────────────────────────────────────────
    return UserError(
        message=f"Unexpected problem: {msg}" if msg else f"Unexpected error ({type(exc).__name__})",
        suggestion=(
            "This is likely a plugin bug. Click 'Show technical details' for the "
            "full error information, and report it at "
            "https://github.com/AiRE-Geo/Bhumi3Dmapper/issues"
        ),
        technical=exc,
        severity='critical',
        context=context,
    )


def format_for_display(error: UserError, include_technical: bool = False) -> str:
    """Format a UserError as plain text for log/console output."""
    icon = {'info': 'ℹ', 'warning': '⚠', 'error': '✗', 'critical': '‼'}.get(error.severity, '✗')
    lines = [
        f"{icon} {error.message}",
        f"  → {error.suggestion}",
    ]
    if error.context:
        lines.append(f"  (during: {error.context})")
    if include_technical and error.technical:
        lines.append(f"  Technical: {type(error.technical).__name__}: {error.technical}")
    return '\n'.join(lines)
