# -*- coding: utf-8 -*-
"""Quick Start Wizard — step-by-step guided prospectivity mapping workflow."""
import os

from qgis.PyQt.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QLabel,
    QFileDialog, QLineEdit, QPushButton, QComboBox, QGroupBox,
    QFormLayout, QTextEdit, QProgressBar, QMessageBox,
)
from qgis.PyQt.QtCore import Qt, QCoreApplication


def tr(msg):
    return QCoreApplication.translate('BhumiWizard', msg)


class BhumiWizard(QWizard):
    """3-page wizard: Config → Data → Run."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('Bhumi3DMapper — Quick Start'))
        self.setMinimumSize(600, 500)

        self.addPage(WelcomePage())
        self.addPage(DataPage())
        self.addPage(RunPage())

    def get_config_path(self):
        return self.field('config_path')


class WelcomePage(QWizardPage):
    """Page 1: Choose or create a config file."""

    def __init__(self):
        super().__init__()
        self.setTitle(tr('Welcome to Bhumi3DMapper'))
        self.setSubTitle(tr(
            'This wizard will guide you through setting up and running '
            'a prospectivity analysis. Start by loading or creating a '
            'project configuration file.'))

        layout = QVBoxLayout(self)

        info = QLabel(tr(
            '<p>A <b>configuration file</b> (.json) defines your project: '
            'data paths, grid settings, scoring weights, and output options.</p>'
            '<p>If this is your first time, click <b>New Config</b> to create a template.</p>'))
        info.setWordWrap(True)
        layout.addWidget(info)

        row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(tr('Path to project_config.json'))
        row.addWidget(self.path_edit)
        btn_load = QPushButton(tr('Load…'))
        btn_load.clicked.connect(self._browse_config)
        row.addWidget(btn_load)
        btn_new = QPushButton(tr('New Config'))
        btn_new.clicked.connect(self._new_config)
        row.addWidget(btn_new)
        layout.addLayout(row)

        self.status_label = QLabel('')
        layout.addWidget(self.status_label)

        self.registerField('config_path*', self.path_edit)

    def _browse_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr('Select Configuration'), '', 'JSON (*.json)')
        if path:
            self.path_edit.setText(path)
            self.status_label.setText(tr(f'✓ Loaded: {os.path.basename(path)}'))

    def _new_config(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr('Save New Config'), 'project_config.json', 'JSON (*.json)')
        if path:
            try:
                from ..core.config import ProjectConfig
                cfg = ProjectConfig()
                cfg.to_json(path)
                self.path_edit.setText(path)
                self.status_label.setText(
                    tr(f'✓ Template created: {os.path.basename(path)}\n'
                       f'  Edit data paths in the JSON, then proceed.'))
            except Exception as e:
                QMessageBox.warning(self, 'Error', str(e))


class DataPage(QWizardPage):
    """Page 2: Quick data path editor."""

    def __init__(self):
        super().__init__()
        self.setTitle(tr('Data Paths'))
        self.setSubTitle(tr(
            'Verify or set the paths to your input data. '
            'These are stored in the config file.'))
        self._built = False

    def initializePage(self):
        if self._built:
            return
        layout = QVBoxLayout(self)
        from .config_widget import ConfigWidget
        self.config_widget = ConfigWidget()
        layout.addWidget(self.config_widget)
        self._built = True

        # Load config into widget
        config_path = self.wizard().get_config_path()
        if config_path and os.path.exists(config_path):
            try:
                from ..core.config import ProjectConfig
                cfg = ProjectConfig.from_json(config_path)
                self.config_widget.load_from_config(cfg)
            except Exception:
                pass

    def validatePage(self):
        """Save edited config before advancing."""
        config_path = self.wizard().get_config_path()
        if config_path:
            try:
                from ..core.config import ProjectConfig
                cfg = ProjectConfig.from_json(config_path)
                self.config_widget.save_to_config(cfg)
                cfg.to_json(config_path)
            except Exception as e:
                QMessageBox.warning(self, 'Warning',
                    tr(f'Could not save config changes: {e}'))
        return True


class RunPage(QWizardPage):
    """Page 3: Run the pipeline."""

    def __init__(self):
        super().__init__()
        self.setTitle(tr('Run Analysis'))
        self.setSubTitle(tr(
            'Click Run to compute prospectivity scores. '
            'Results will be loaded into QGIS automatically.'))

        layout = QVBoxLayout(self)

        self.model_combo = QComboBox()
        self.model_combo.addItems([
            tr('Both (Proximity + Blind)'),
            tr('Proximity only'),
            tr('Blind only'),
        ])
        layout.addWidget(QLabel(tr('Model:')))
        layout.addWidget(self.model_combo)

        self.run_btn = QPushButton(tr('▶ Run Prospectivity Analysis'))
        f = self.run_btn.font()
        f.setPointSize(f.pointSize() + 2)
        f.setBold(True)
        self.run_btn.setFont(f)
        self.run_btn.clicked.connect(self._run)
        layout.addWidget(self.run_btn)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

    def _run(self):
        config_path = self.wizard().get_config_path()
        if not config_path:
            return

        self.run_btn.setEnabled(False)
        self.log.clear()
        self.log.append(tr('Starting analysis…'))

        try:
            from qgis import processing

            # Step 1: Validate
            self.progress.setValue(10)
            self.log.append(tr('Validating data…'))
            result = processing.run('bhumi3dmapper:loaddata', {
                'CONFIG': config_path, 'STRICT': False,
            })
            self.log.append(f"  Validation: {result.get('RESULT', '?')}")

            if result.get('RESULT') == 'FAILED':
                self.log.append(tr('✗ Validation failed. Check your data paths.'))
                self.run_btn.setEnabled(True)
                return

            # Step 2: Score
            self.progress.setValue(30)
            self.log.append(tr('Running scoring engine…'))
            result = processing.run('bhumi3dmapper:runscoring', {
                'CONFIG': config_path,
                'MODEL': self.model_combo.currentIndex(),
                'LEVELS': '',
            })
            self.log.append(f"  Scoring: {result.get('RESULT', '?')}")

            # Step 3: Load
            self.progress.setValue(80)
            self.log.append(tr('Loading results into QGIS…'))

            from ..core.config import ProjectConfig
            cfg = ProjectConfig.from_json(config_path)
            gpkg_dir = os.path.join(cfg.outputs.output_dir, 'gpkg')

            if os.path.isdir(gpkg_dir):
                result = processing.run('bhumi3dmapper:loadresults', {
                    'GPKG_DIR': gpkg_dir,
                    'SCORE_FIELD': 0,
                    'ADD_ALL': True,
                })
                self.log.append(f"  Load: {result.get('RESULT', '?')}")

            self.progress.setValue(100)
            self.log.append(tr('✓ Analysis complete!'))

        except Exception as e:
            self.log.append(f'ERROR: {e}')
        finally:
            self.run_btn.setEnabled(True)
