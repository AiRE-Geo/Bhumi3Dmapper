# -*- coding: utf-8 -*-
"""Bhumi3DMapper dockable project panel — main control interface."""
import os
import traceback

from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QFileDialog, QProgressBar, QComboBox,
    QLineEdit, QTextEdit, QMessageBox, QSizePolicy,
)
from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.PyQt.QtGui import QFont
from qgis.core import QgsApplication, Qgis


def tr(msg):
    return QCoreApplication.translate('BhumiDockWidget', msg)


class BhumiDockWidget(QDockWidget):
    """Dockable panel for Bhumi3DMapper project control."""

    def __init__(self, iface, parent=None):
        super().__init__(tr('Bhumi3DMapper'), parent)
        self.iface = iface
        self.config_path = ''
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self._setup_ui()

    def _setup_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Title ──────────────────────────────────────────────────────
        title = QLabel('Bhumi3DMapper')
        title.setFont(QFont('', 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(tr('3D Mineral Prospectivity Mapper'))
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        # ── Config Group ───────────────────────────────────────────────
        cfg_group = QGroupBox(tr('Project Configuration'))
        cfg_layout = QVBoxLayout(cfg_group)

        row = QHBoxLayout()
        self.config_label = QLabel(tr('No config loaded'))
        self.config_label.setWordWrap(True)
        self.config_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row.addWidget(self.config_label)
        btn_load = QPushButton(tr('Load…'))
        btn_load.setToolTip(tr('Load a project configuration JSON file'))
        btn_load.clicked.connect(self._load_config)
        row.addWidget(btn_load)
        cfg_layout.addLayout(row)

        btn_new = QPushButton(tr('New Config Template'))
        btn_new.setToolTip(tr('Create a new blank configuration file as a starting point'))
        btn_new.clicked.connect(self._new_config)
        cfg_layout.addWidget(btn_new)

        layout.addWidget(cfg_group)

        # ── Model Selection ────────────────────────────────────────────
        model_group = QGroupBox(tr('Model'))
        model_layout = QVBoxLayout(model_group)
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            tr('Both (Proximity + Blind)'),
            tr('Proximity only'),
            tr('Blind only'),
        ])
        self.model_combo.setToolTip(
            tr('Proximity = extend known ore. Blind = find new ore.'))
        model_layout.addWidget(self.model_combo)

        lvl_row = QHBoxLayout()
        lvl_row.addWidget(QLabel(tr('Levels:')))
        self.levels_edit = QLineEdit()
        self.levels_edit.setPlaceholderText(tr('e.g. 185,210,235 (empty=all)'))
        self.levels_edit.setToolTip(
            tr('Comma-separated mRL levels. Leave empty for all levels in config.'))
        lvl_row.addWidget(self.levels_edit)
        model_layout.addLayout(lvl_row)

        layout.addWidget(model_group)

        # ── Actions ────────────────────────────────────────────────────
        action_group = QGroupBox(tr('Pipeline'))
        action_layout = QVBoxLayout(action_group)

        btn_validate = QPushButton(tr('1. Validate Data'))
        btn_validate.setToolTip(tr('Check all input files exist and are readable'))
        btn_validate.clicked.connect(self._run_validate)
        action_layout.addWidget(btn_validate)

        btn_score = QPushButton(tr('2. Run Scoring'))
        btn_score.setToolTip(tr('Compute prospectivity scores and write GPKGs'))
        btn_score.clicked.connect(self._run_scoring)
        action_layout.addWidget(btn_score)

        btn_load_results = QPushButton(tr('3. Load Results'))
        btn_load_results.setToolTip(
            tr('Add scored GPKGs to QGIS with colour symbology'))
        btn_load_results.clicked.connect(self._load_results)
        action_layout.addWidget(btn_load_results)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        action_layout.addWidget(self.progress)

        layout.addWidget(action_group)

        # ── Log ────────────────────────────────────────────────────────
        log_group = QGroupBox(tr('Log'))
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)

        layout.addStretch()
        self.setWidget(container)

    # ── Handlers ──────────────────────────────────────────────────────
    def _log(self, msg):
        self.log_text.append(msg)

    def _load_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr('Select Configuration File'), '',
            tr('JSON files (*.json);;All files (*)'))
        if path:
            try:
                from .core.config import ProjectConfig
                cfg = ProjectConfig.from_json(path)
                self.config_path = path
                self.config_label.setText(f'{cfg.project_name}\n{os.path.basename(path)}')
                self._log(f'✓ Loaded: {cfg.project_name} ({path})')
            except Exception as e:
                QMessageBox.warning(self, 'Bhumi3DMapper',
                    tr(f'Could not load config:\n{e}'))

    def _new_config(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr('Save New Config Template'), 'project_config.json',
            tr('JSON files (*.json)'))
        if path:
            try:
                from .core.config import ProjectConfig
                cfg = ProjectConfig()
                cfg.to_json(path)
                self.config_path = path
                self.config_label.setText(f'New template\n{os.path.basename(path)}')
                self._log(f'✓ Template saved: {path}')
                self._log('  Edit the JSON to set your data paths, then reload.')
            except Exception as e:
                QMessageBox.warning(self, 'Bhumi3DMapper',
                    tr(f'Could not save template:\n{e}'))

    def _check_config(self):
        if not self.config_path:
            QMessageBox.information(self, 'Bhumi3DMapper',
                tr('Please load a configuration file first.'))
            return False
        return True

    def _run_validate(self):
        if not self._check_config():
            return
        try:
            from qgis import processing
            result = processing.run('bhumi3dmapper:loaddata', {
                'CONFIG': self.config_path,
                'STRICT': False,
            })
            status = result.get('RESULT', '?')
            summary = result.get('SUMMARY', '')
            self._log(f'Validation: {status} ({summary})')
        except Exception as e:
            self._log(f'ERROR: {e}')

    def _run_scoring(self):
        if not self._check_config():
            return
        try:
            from qgis import processing
            result = processing.run('bhumi3dmapper:runscoring', {
                'CONFIG': self.config_path,
                'MODEL': self.model_combo.currentIndex(),
                'LEVELS': self.levels_edit.text(),
            })
            self._log(f'Scoring: {result.get("RESULT", "?")}')
        except Exception as e:
            self._log(f'ERROR: {e}')

    def _load_results(self):
        if not self._check_config():
            return
        try:
            from .core.config import ProjectConfig
            cfg = ProjectConfig.from_json(self.config_path)
            gpkg_dir = os.path.join(cfg.outputs.output_dir, 'gpkg')
            if not os.path.isdir(gpkg_dir):
                QMessageBox.information(self, 'Bhumi3DMapper',
                    tr(f'GPKG output folder not found:\n{gpkg_dir}\n'
                       f'Run scoring first.'))
                return
            from qgis import processing
            result = processing.run('bhumi3dmapper:loadresults', {
                'GPKG_DIR': gpkg_dir,
                'SCORE_FIELD': 0,
                'ADD_ALL': True,
            })
            self._log(f'Load results: {result.get("RESULT", "?")}')
        except Exception as e:
            self._log(f'ERROR: {e}')
