# -*- coding: utf-8 -*-
"""Reusable configuration editor widget for Bhumi3DMapper."""
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QSpinBox, QDoubleSpinBox, QFileDialog, QPushButton,
    QLabel, QComboBox, QScrollArea,
)
from qgis.PyQt.QtCore import QCoreApplication


def tr(msg):
    return QCoreApplication.translate('ConfigWidget', msg)


class ConfigWidget(QWidget):
    """Editable form for ProjectConfig fields with file pickers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = None
        self._deposit_type = 'generic'
        self._setup_ui()
        self._apply_tooltips()  # JC-30 — wire geological tooltips

    def _on_deposit_changed(self, new_type: str):
        """JC-30 — refresh tooltips when user picks different deposit type."""
        self._deposit_type = new_type or 'generic'
        self._apply_tooltips()

    def _apply_tooltips(self):
        """JC-30 — populate setToolTip on every widget from core/tooltips.json.
        Refreshes when deposit type changes."""
        try:
            try:
                from ..core.tooltips import get_tooltip
            except ImportError:
                from core.tooltips import get_tooltip
        except Exception:
            return  # tooltip file missing; silently skip
        dt = self._deposit_type or 'generic'

        def tt(param):
            t = get_tooltip(param, dt)
            return t if t else None

        # Apply where we have documented parameters
        mapping = [
            (self.deposit_type, 'deposit_type'),
            (self.crs_epsg, 'crs_epsg'),
            (self.grid_nx, 'grid_nx'),
            (self.grid_ny, 'grid_ny'),
            (self.grid_cell, 'grid_cell_size'),
            (self.grid_ztop, 'grid_z_top'),
            (self.grid_zbot, 'grid_z_bot'),
        ]
        for widget, param in mapping:
            t = tt(param)
            if t:
                widget.setToolTip(t)

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        self.form = QVBoxLayout(inner)
        self.form.setContentsMargins(4, 4, 4, 4)

        # ── Project Info ──────────────────────────────────────────
        grp = QGroupBox(tr('Project'))
        fl = QFormLayout(grp)
        self.proj_name = QLineEdit()
        self.proj_name.setToolTip(tr('Name of the project (e.g. Kayad Pb-Zn Mine)'))
        fl.addRow(tr('Project name:'), self.proj_name)
        self.deposit_type = QComboBox()
        self.deposit_type.addItems(['SEDEX Pb-Zn', 'VMS Cu-Zn', 'Porphyry Cu-Au',
                                     'Epithermal Au', 'IOCG', 'Other'])
        self.deposit_type.setEditable(True)
        self.deposit_type.setToolTip(tr('Deposit type controls default scoring parameters'))
        # JC-30 — refresh tooltips when deposit type changes
        self.deposit_type.currentTextChanged.connect(self._on_deposit_changed)
        fl.addRow(tr('Deposit type:'), self.deposit_type)
        self.crs_epsg = QSpinBox()
        self.crs_epsg.setRange(1000, 99999)
        self.crs_epsg.setValue(32643)
        self.crs_epsg.setToolTip(tr('EPSG code for the project CRS (e.g. 32643 = UTM 43N)'))
        fl.addRow(tr('CRS EPSG:'), self.crs_epsg)
        self.form.addWidget(grp)

        # ── Drill Data ────────────────────────────────────────────
        grp = QGroupBox(tr('Drill Data'))
        fl = QFormLayout(grp)
        self.collar_csv = self._file_row(fl, tr('Collar CSV:'),
            tr('CSV file with BHID, XCOLLAR, YCOLLAR, ZCOLLAR, DEPTH'))
        self.assay_csv = self._file_row(fl, tr('Assay CSV:'),
            tr('CSV file with BHID, FROM, TO, ZN, PB'))
        self.litho_csv = self._file_row(fl, tr('Litho CSV:'),
            tr('CSV file with BHID, FROM, TO, ROCKCODE'))
        self.form.addWidget(grp)

        # ── Geophysics ────────────────────────────────────────────
        grp = QGroupBox(tr('Geophysics'))
        fl = QFormLayout(grp)
        self.grav_folder = self._folder_row(fl, tr('Gravity folder:'),
            tr('Folder of gravity TIF files (one per depth level)'))
        self.mag_folder = self._folder_row(fl, tr('Magnetics folder:'),
            tr('Folder of magnetic susceptibility TIF files'))
        self.form.addWidget(grp)

        # ── Grid ──────────────────────────────────────────────────
        grp = QGroupBox(tr('Grid'))
        fl = QFormLayout(grp)
        self.grid_nx = QSpinBox(); self.grid_nx.setRange(1, 99999); self.grid_nx.setValue(482)
        self.grid_ny = QSpinBox(); self.grid_ny.setRange(1, 99999); self.grid_ny.setValue(722)
        self.grid_cell = QDoubleSpinBox(); self.grid_cell.setRange(0.1, 1000); self.grid_cell.setValue(5.0)
        self.grid_ztop = QDoubleSpinBox(); self.grid_ztop.setRange(-9999, 9999); self.grid_ztop.setValue(460)
        self.grid_zbot = QDoubleSpinBox(); self.grid_zbot.setRange(-9999, 9999); self.grid_zbot.setValue(-260)
        fl.addRow(tr('nx:'), self.grid_nx)
        fl.addRow(tr('ny:'), self.grid_ny)
        fl.addRow(tr('Cell size (m):'), self.grid_cell)
        fl.addRow(tr('Z top (mRL):'), self.grid_ztop)
        fl.addRow(tr('Z bottom (mRL):'), self.grid_zbot)
        self.form.addWidget(grp)

        # ── Output ────────────────────────────────────────────────
        grp = QGroupBox(tr('Output'))
        fl = QFormLayout(grp)
        self.output_dir = self._folder_row(fl, tr('Output folder:'),
            tr('Folder for GPKG and voxel output files'))
        self.form.addWidget(grp)

        self.form.addStretch()
        scroll.setWidget(inner)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _file_row(self, form_layout, label, tooltip):
        row = QHBoxLayout()
        edit = QLineEdit()
        edit.setToolTip(tooltip)
        row.addWidget(edit)
        btn = QPushButton('…')
        btn.setFixedWidth(30)
        btn.setToolTip(tr('Browse'))
        btn.clicked.connect(lambda: self._pick_file(edit))
        row.addWidget(btn)
        form_layout.addRow(label, row)
        return edit

    def _folder_row(self, form_layout, label, tooltip):
        row = QHBoxLayout()
        edit = QLineEdit()
        edit.setToolTip(tooltip)
        row.addWidget(edit)
        btn = QPushButton('…')
        btn.setFixedWidth(30)
        btn.setToolTip(tr('Browse'))
        btn.clicked.connect(lambda: self._pick_folder(edit))
        row.addWidget(btn)
        form_layout.addRow(label, row)
        return edit

    def _pick_file(self, edit):
        path, _ = QFileDialog.getOpenFileName(self, tr('Select file'))
        if path:
            edit.setText(path)

    def _pick_folder(self, edit):
        path = QFileDialog.getExistingDirectory(self, tr('Select folder'))
        if path:
            edit.setText(path)

    def load_from_config(self, cfg):
        """Populate form from a ProjectConfig object."""
        self._config = cfg
        self._deposit_type = cfg.deposit_type or 'generic'
        self._apply_tooltips()  # refresh for new deposit type
        self.proj_name.setText(cfg.project_name)
        idx = self.deposit_type.findText(cfg.deposit_type)
        if idx >= 0:
            self.deposit_type.setCurrentIndex(idx)
        else:
            self.deposit_type.setEditText(cfg.deposit_type)
        self.crs_epsg.setValue(cfg.crs_epsg)
        self.collar_csv.setText(cfg.drill.collar_csv)
        self.assay_csv.setText(cfg.drill.assay_csv)
        self.litho_csv.setText(cfg.drill.litho_csv)
        self.grav_folder.setText(cfg.geophysics.gravity_folder)
        self.mag_folder.setText(cfg.geophysics.magnetics_folder)
        self.grid_nx.setValue(cfg.grid.nx)
        self.grid_ny.setValue(cfg.grid.ny)
        self.grid_cell.setValue(cfg.grid.cell_size_m)
        self.grid_ztop.setValue(cfg.grid.z_top_mrl)
        self.grid_zbot.setValue(cfg.grid.z_bot_mrl)
        self.output_dir.setText(cfg.outputs.output_dir)

    def save_to_config(self, cfg):
        """Write form values back to a ProjectConfig object."""
        cfg.project_name = self.proj_name.text()
        cfg.deposit_type = self.deposit_type.currentText()
        cfg.crs_epsg = self.crs_epsg.value()
        cfg.drill.collar_csv = self.collar_csv.text()
        cfg.drill.assay_csv = self.assay_csv.text()
        cfg.drill.litho_csv = self.litho_csv.text()
        cfg.geophysics.gravity_folder = self.grav_folder.text()
        cfg.geophysics.magnetics_folder = self.mag_folder.text()
        cfg.grid.nx = self.grid_nx.value()
        cfg.grid.ny = self.grid_ny.value()
        cfg.grid.cell_size_m = self.grid_cell.value()
        cfg.grid.z_top_mrl = self.grid_ztop.value()
        cfg.grid.z_bot_mrl = self.grid_zbot.value()
        cfg.outputs.output_dir = self.output_dir.text()
        return cfg
