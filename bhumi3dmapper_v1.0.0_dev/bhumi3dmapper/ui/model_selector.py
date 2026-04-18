# -*- coding: utf-8 -*-
"""
Bhumi3DMapper — Deposit Model Selector Widget (BH-REM-P1 Gap 3)
===============================================================
Wizard page 2 widget for selecting a shared-repo deposit model and
displaying the Evidence Key Bridge coverage indicator.

Design rules
------------
- NO qgis.core imports — pure Qt (qgis.PyQt) + data from shared_repo_loader
  and evidence_key_bridge. Enforced by test/test_ui_no_qgis_core.py.
- Coverage indicator is 4-band coloured:
    green  ≥ 75%  — good coverage
    yellow 50–75% — adequate, minor warning
    orange 25–50% — LOW: warn prominently
    red    < 25%  — CRITICAL: block + override checkbox
- Block-state dialog lists specific keys contributing > 5% weight each.
- Selected deposit_type propagates to cfg.json_model_deposit_type via signal.

BH-REM-P1 two-engine architecture (Session 3, 2026-04-17):
  Engine 1 — m04 Kayad c-criterion engine (brownfields)
  Engine 2 — m13 JSON WLC engine (reconnaissance, reads shared repo via bridge)
This widget is the gateway to Engine 2.

No automated test for the Qt widget itself — manual inspection sufficient for
Phase 1. Added to v2.0.1 UX test plan. Coverage computation tested via
TestCoverageReport in test_evidence_key_bridge.py.
"""
from __future__ import annotations

from typing import List, Optional

try:
    from qgis.PyQt.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QListWidget,
        QListWidgetItem, QProgressBar, QCheckBox, QPushButton, QDialog,
        QDialogButtonBox, QTextEdit, QScrollArea, QSizePolicy, QFrame,
        QApplication,
    )
    from qgis.PyQt.QtCore import Qt, pyqtSignal, QCoreApplication
    from qgis.PyQt.QtGui import QColor, QPalette
    _HAS_QT = True
except ImportError:
    _HAS_QT = False
    # Stubs for environments where Qt is not available (e.g., CI without QGIS).
    # All Qt classes used as base classes must be stubbed so class definitions
    # at module scope do not raise NameError on import.
    class QWidget:    # type: ignore[no-redef]
        pass
    class QDialog:    # type: ignore[no-redef]
        pass
    class QListWidgetItem:  # type: ignore[no-redef]
        pass
    pyqtSignal = lambda *a, **kw: None  # noqa: E731


def _tr(msg: str) -> str:
    """Translate string (no-op when Qt unavailable)."""
    if _HAS_QT:
        return QCoreApplication.translate("ModelSelector", msg)
    return msg


# ── Coverage band colours ─────────────────────────────────────────────────────

_BAND_GREEN  = "#2ecc71"   # ≥ 75%
_BAND_YELLOW = "#f1c40f"   # 50–75%
_BAND_ORANGE = "#e67e22"   # 25–50%
_BAND_RED    = "#e74c3c"   # < 25% (BLOCK)

_BAND_GREEN_TEXT  = "#1a7a44"
_BAND_YELLOW_TEXT = "#7d6608"
_BAND_ORANGE_TEXT = "#784212"
_BAND_RED_TEXT    = "#7b241c"

_BLOCK_THRESHOLD  = 0.25
_WARN_THRESHOLD   = 0.50
_GOOD_THRESHOLD   = 0.75


def _coverage_band(fraction: float) -> tuple:
    """Return (bg_colour, text_colour, label) for the given coverage fraction."""
    if fraction >= _GOOD_THRESHOLD:
        return _BAND_GREEN,  _BAND_GREEN_TEXT,  "Good coverage"
    elif fraction >= _WARN_THRESHOLD:
        return _BAND_YELLOW, _BAND_YELLOW_TEXT, "Adequate — minor gaps"
    elif fraction >= _BLOCK_THRESHOLD:
        return _BAND_ORANGE, _BAND_ORANGE_TEXT, "LOW — significant gaps"
    else:
        return _BAND_RED,    _BAND_RED_TEXT,    "CRITICAL — scoring blocked"


# ── Block-state key detail dialog ─────────────────────────────────────────────

class _BlockDetailDialog(QDialog):
    """
    Modal dialog shown in block state (<25% coverage). Lists missing keys
    that individually contribute > 5% of total weight mass, so the user
    knows exactly what data to import from CAGE-IN to unlock scoring.
    """

    def __init__(self, deposit_type: str, coverage_report: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_tr("Coverage Block Details"))
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)

        # Header
        hdr = QLabel(
            f"<b>{deposit_type}</b> — coverage {coverage_report['coverage_fraction']:.0%}<br>"
            "The following missing layers individually contribute &gt;5% of the "
            "model weight mass. Importing them from CAGE-IN will unlock scoring."
        )
        hdr.setWordWrap(True)
        layout.addWidget(hdr)

        # Missing keys contributing > 5% weight
        total = coverage_report.get("total_weight_mass", 1.0) or 1.0
        missing = coverage_report.get("missing_keys", [])
        cage_in = set(coverage_report.get("cage_in_required_keys", []))

        # We need model weights to get per-key weight — retrieve via bridge
        try:
            try:
                from ..core.shared_repo_loader import load_deposit_model
            except ImportError:
                from core.shared_repo_loader import load_deposit_model
            model = load_deposit_model(deposit_type, validate=False)
            weight_map = {w.layer_key: w.weight for w in model.weights}
        except Exception:
            weight_map = {}

        significant: List[tuple] = []
        for key in missing:
            w = weight_map.get(key, 0.0)
            if total > 0 and (w / total) > 0.05:
                significant.append((key, w, key in cage_in))

        significant.sort(key=lambda x: x[1], reverse=True)

        if significant:
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            lines = []
            for key, wt, needs_cage in significant:
                cage_tag = " [CAGE-IN import required]" if needs_cage else " [no Bhumi source]"
                lines.append(f"  • {key}: {wt:.2f} weight ({wt/total:.0%} of total){cage_tag}")
            text_edit.setPlainText("\n".join(lines))
            layout.addWidget(text_edit)
        else:
            layout.addWidget(QLabel(_tr("No single layer exceeds 5% threshold.")))

        # CAGE-IN note
        if cage_in:
            note = QLabel(
                "<i>Layers marked [CAGE-IN import required] can be provided via the "
                "JC-TBD-EVIDENCESTACK-EXPORT ticket. Contact the CAGE-IN team.</i>"
            )
            note.setWordWrap(True)
            layout.addWidget(note)

        # Close button
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)


# ── Main widget ───────────────────────────────────────────────────────────────

class ModelSelectorWidget(QWidget):
    """
    Deposit model selector with Evidence Key Bridge coverage indicator.

    Signals
    -------
    model_selected(str)
        Emitted when the user selects a deposit model.
        Payload is the deposit_type string (e.g., 'orogenic_au').
    """

    if _HAS_QT:
        model_selected = pyqtSignal(str)

    def __init__(self, parent=None, structural_corridors_defined: bool = True):
        """
        Parameters
        ----------
        parent : QWidget, optional
            Qt parent widget.
        structural_corridors_defined : bool
            Pass ``ProjectConfig.structural.corridors_defined()`` here.
            When False, the c6_structural_corridor → fault_proximity PARTIAL
            bridge is demoted to MISSING in the JSON scoring engine — the
            built-in Kayad N28E/N315E geometry is not valid for projects that
            have not defined their own structural corridors.
            (Dr. Prithvi ruling 2, BH-REM-P1 addendum 2026-04-17.)
            Default True for backwards compatibility / test contexts.
        """
        if not _HAS_QT:
            return
        super().__init__(parent)

        self._structural_corridors_defined = structural_corridors_defined
        self._current_deposit_type: Optional[str] = None
        self._current_coverage: Optional[dict] = None
        self._model_entries: List[dict] = []

        self._build_ui()
        self._populate_model_list()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Model list group ──────────────────────────────────────────────────
        list_group = QGroupBox(_tr("Available Deposit Models"))
        list_vbox = QVBoxLayout(list_group)

        self._hint_label = QLabel(
            _tr("Select a model to see Evidence Key Bridge coverage for current Bhumi data.")
        )
        self._hint_label.setWordWrap(True)
        list_vbox.addWidget(self._hint_label)

        self._model_list = QListWidget()
        self._model_list.setMinimumHeight(160)
        self._model_list.currentRowChanged.connect(self._on_row_changed)
        list_vbox.addWidget(self._model_list)

        root.addWidget(list_group)

        # ── Coverage indicator group ──────────────────────────────────────────
        cov_group = QGroupBox(_tr("Evidence Key Bridge Coverage"))
        cov_vbox = QVBoxLayout(cov_group)

        # Progress bar (used for visual width; coloured via stylesheet)
        self._cov_bar = QProgressBar()
        self._cov_bar.setRange(0, 100)
        self._cov_bar.setValue(0)
        self._cov_bar.setTextVisible(True)
        self._cov_bar.setMinimumHeight(24)
        cov_vbox.addWidget(self._cov_bar)

        # Band label (good/warn/block text)
        self._cov_band_label = QLabel()
        self._cov_band_label.setAlignment(Qt.AlignCenter)
        self._cov_band_label.setWordWrap(True)
        cov_vbox.addWidget(self._cov_band_label)

        # Bridge breakdown (native / partial / missing counts)
        self._cov_detail_label = QLabel()
        self._cov_detail_label.setAlignment(Qt.AlignCenter)
        self._cov_detail_label.setWordWrap(True)
        cov_vbox.addWidget(self._cov_detail_label)

        # "Why is it blocked?" button — shown only in red/block state
        self._block_detail_btn = QPushButton(_tr("Why blocked? List missing layers…"))
        self._block_detail_btn.clicked.connect(self._show_block_detail)
        self._block_detail_btn.setVisible(False)
        cov_vbox.addWidget(self._block_detail_btn)

        # Override checkbox — shown only in red/block state
        self._override_check = QCheckBox(
            _tr("I understand the score will be scientifically unreliable — allow anyway")
        )
        self._override_check.setVisible(False)
        self._override_check.setStyleSheet("color: #7b241c; font-weight: bold;")
        cov_vbox.addWidget(self._override_check)

        # Pending Prithvi review warning
        self._prithvi_label = QLabel()
        self._prithvi_label.setWordWrap(True)
        self._prithvi_label.setVisible(False)
        self._prithvi_label.setStyleSheet("color: #7d3c98;")
        cov_vbox.addWidget(self._prithvi_label)

        root.addWidget(cov_group)

        # ── Reset to blank state ──────────────────────────────────────────────
        self._set_coverage_blank()

    # ── Model list population ─────────────────────────────────────────────────

    def _populate_model_list(self):
        """Load UI-ready model entries and populate the list widget."""
        self._model_list.clear()
        self._model_entries = []

        try:
            try:
                from ..core.shared_repo_loader import get_ui_model_list
            except ImportError:
                from core.shared_repo_loader import get_ui_model_list
            entries = get_ui_model_list()
        except Exception as exc:
            item = QListWidgetItem(f"[Shared repo unavailable: {exc}]")
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self._model_list.addItem(item)
            return

        for entry in entries:
            status = entry.get("review_status", "")

            # Hide superseded and not-yet-brainstormed
            if status.startswith("superseded_by_") or status == "not_yet_brainstormed":
                continue

            badge = entry.get("status_badge", "")
            display = entry.get("display_name", entry.get("deposit_type", "?"))
            commodities = entry.get("primary_commodities", "")
            family = entry.get("family", "")

            # Format list label
            label = f"{display}"
            if commodities:
                label += f"  [{commodities}]"
            label += f"  — {badge}"

            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, entry.get("deposit_type", ""))

            # pre_brainstorm_scaffold: grey and italic
            is_preview = status.startswith("pre_brainstorm_scaffold")
            if is_preview:
                item.setForeground(QColor("#888888"))
                font = item.font()
                font.setItalic(True)
                item.setFont(font)

            self._model_list.addItem(item)
            self._model_entries.append(entry)

    # ── Model selection handler ───────────────────────────────────────────────

    def _on_row_changed(self, row: int):
        """Called when user selects a row in the model list."""
        item = self._model_list.item(row)
        if item is None:
            self._set_coverage_blank()
            return

        deposit_type = item.data(Qt.UserRole)
        if not deposit_type:
            self._set_coverage_blank()
            return

        self._current_deposit_type = deposit_type
        self._refresh_coverage(deposit_type)

        if _HAS_QT:
            self.model_selected.emit(deposit_type)

    def _refresh_coverage(self, deposit_type: str):
        """
        Load the deposit model coverage indicator using the lightweight pre-check
        function (BH-06). Does not construct a full JsonScoringEngine — avoids
        schema validation + dataclass build overhead on every row-change event.
        Full engine construction happens only when the user confirms model selection
        and initiates scoring.
        """
        try:
            try:
                from ..modules.m13_json_scoring_engine import get_coverage_report_for_model
            except ImportError:
                from modules.m13_json_scoring_engine import get_coverage_report_for_model
            report = get_coverage_report_for_model(deposit_type)
            self._current_coverage = report
            self._apply_coverage_ui(deposit_type, report)
        except Exception as exc:
            self._set_coverage_error(str(exc))

    def _apply_coverage_ui(self, deposit_type: str, report: dict):
        """Update all coverage indicator elements from a coverage report dict."""
        fraction = report.get("coverage_fraction", 0.0)
        matched  = report.get("matched_weight_mass", 0.0)
        total    = report.get("total_weight_mass", 0.0)
        native   = len(report.get("native_keys", []))
        partial  = len(report.get("partial_keys", []))
        missing  = len(report.get("missing_keys", []))
        is_block = report.get("block", False)
        pending  = report.get("pending_prithvi_review", [])

        # ── Progress bar ──────────────────────────────────────────────────────
        pct = min(100, max(0, int(fraction * 100)))
        self._cov_bar.setValue(pct)
        self._cov_bar.setFormat(f"{pct}%  ({matched:.2f} / {total:.2f} weight mass)")

        bg_col, txt_col, band_text = _coverage_band(fraction)
        self._cov_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {bg_col}; }}"
            f"QProgressBar {{ color: {txt_col}; font-weight: bold; "
            f"border: 1px solid {bg_col}; border-radius: 3px; text-align: center; }}"
        )

        # ── Band label ────────────────────────────────────────────────────────
        self._cov_band_label.setText(
            f"<b style='color:{txt_col};'>{band_text}</b>"
        )
        self._cov_band_label.setStyleSheet(f"background-color: {bg_col}; "
                                            f"padding: 2px; border-radius: 3px;")

        # ── Detail label ──────────────────────────────────────────────────────
        self._cov_detail_label.setText(
            f"{native} NATIVE · {partial} PARTIAL · {missing} MISSING  "
            f"(of {native + partial + missing} total weight entries)"
        )

        # ── Block state controls ──────────────────────────────────────────────
        self._block_detail_btn.setVisible(is_block)
        self._override_check.setVisible(is_block)
        if not is_block:
            self._override_check.setChecked(False)

        # ── Pending Prithvi review warning ────────────────────────────────────
        if pending:
            self._prithvi_label.setText(
                f"\u26a0 {len(pending)} bridge(s) pending Dr. Prithvi geological "
                f"review: {', '.join(pending)}. Use results with caution."
            )
            self._prithvi_label.setVisible(True)
        else:
            self._prithvi_label.setVisible(False)

    def _set_coverage_blank(self):
        """Reset coverage indicator to the 'no selection' blank state."""
        self._current_coverage = None
        self._cov_bar.setValue(0)
        self._cov_bar.setFormat(_tr("Select a model above"))
        self._cov_bar.setStyleSheet(
            "QProgressBar::chunk { background-color: #cccccc; }"
            "QProgressBar { color: #666666; border: 1px solid #cccccc; "
            "border-radius: 3px; text-align: center; }"
        )
        self._cov_band_label.setText("")
        self._cov_detail_label.setText("")
        self._block_detail_btn.setVisible(False)
        self._override_check.setVisible(False)
        self._prithvi_label.setVisible(False)

    def _set_coverage_error(self, error_msg: str):
        """Show an error state in the coverage indicator."""
        self._current_coverage = None
        self._cov_bar.setValue(0)
        self._cov_bar.setFormat(_tr("Error loading model"))
        self._cov_bar.setStyleSheet(
            "QProgressBar::chunk { background-color: #999999; }"
            "QProgressBar { color: #333333; border: 1px solid #999999; "
            "border-radius: 3px; text-align: center; }"
        )
        self._cov_band_label.setText(
            f"<span style='color:#7b241c;'>Could not load model: {error_msg}</span>"
        )
        self._cov_detail_label.setText("")
        self._block_detail_btn.setVisible(False)
        self._override_check.setVisible(False)
        self._prithvi_label.setVisible(False)

    def _show_block_detail(self):
        """Open the block-state detail dialog."""
        if self._current_deposit_type and self._current_coverage:
            dlg = _BlockDetailDialog(
                self._current_deposit_type,
                self._current_coverage,
                parent=self,
            )
            dlg.exec_()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_selected_deposit_type(self) -> Optional[str]:
        """Return the currently selected deposit_type, or None if nothing selected."""
        return self._current_deposit_type

    def override_low_coverage_checked(self) -> bool:
        """
        Return True if the user has acknowledged the block-state override.
        Only True when coverage < 25% AND the override checkbox is visible and checked.
        """
        if not _HAS_QT:
            return False
        if self._override_check.isVisible() and self._override_check.isChecked():
            return True
        return False

    def refresh(self):
        """
        Reload the model list from the shared repo and refresh coverage.
        Call this if the shared repo path changes at runtime.
        """
        self._set_coverage_blank()
        self._current_deposit_type = None
        self._populate_model_list()

    def select_deposit_type(self, deposit_type: str) -> bool:
        """
        Programmatically select a deposit_type in the list.
        Returns True if found and selected, False otherwise.
        """
        for row in range(self._model_list.count()):
            item = self._model_list.item(row)
            if item and item.data(Qt.UserRole) == deposit_type:
                self._model_list.setCurrentRow(row)
                return True
        return False
