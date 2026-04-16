# -*- coding: utf-8 -*-
"""Algorithm: Load & Validate Data — first step in any prospectivity run."""
import os
import traceback
import glob

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterFile,
    QgsProcessingParameterBoolean,
    QgsProcessingOutputString,
    Qgis,
)


def tr(msg):
    return QCoreApplication.translate('LoadDataAlgorithm', msg)


class LoadDataAlgorithm(QgsProcessingAlgorithm):
    CONFIG   = 'CONFIG'
    STRICT   = 'STRICT'
    RESULT   = 'RESULT'
    SUMMARY  = 'SUMMARY'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            self.CONFIG,
            tr('Project configuration file (.json)'),
            QgsProcessingParameterFile.File,
            extension='json',
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.STRICT,
            tr('Strict mode — fail on any warning (recommended for production)'),
            defaultValue=False,
        ))
        self.addOutput(QgsProcessingOutputString(self.RESULT, tr('Result status')))
        self.addOutput(QgsProcessingOutputString(self.SUMMARY, tr('Validation summary')))

    def processAlgorithm(self, parameters, context, feedback):
        config_path = self.parameterAsFile(parameters, self.CONFIG, context)
        strict = self.parameterAsBoolean(parameters, self.STRICT, context)
        feedback.setProgress(0)

        # ── Load config ───────────────────────────────────────────────────
        try:
            from ..core.config import ProjectConfig
            cfg = ProjectConfig.from_json(config_path)
        except Exception as e:
            feedback.reportError(
                tr(f'Cannot load configuration: {e}\n'
                   f'Check that the file exists and is valid JSON.'), fatalError=True)
            return {self.RESULT: 'FAILED', self.SUMMARY: str(e)}

        feedback.setProgress(20)
        if feedback.isCanceled():
            return {}

        # ── Validate data ─────────────────────────────────────────────────
        try:
            issues = []

            # Validate drill files
            for label, path in [
                ('Collar CSV', cfg.drill.collar_csv),
                ('Assay CSV',  cfg.drill.assay_csv),
                ('Litho CSV',  cfg.drill.litho_csv),
            ]:
                if not path:
                    issues.append(f'WARNING: {label} path not set')
                elif not os.path.exists(path):
                    issues.append(f'ERROR: {label} file not found: {path}')
                else:
                    feedback.pushInfo(f'✓ {label}: {os.path.basename(path)}')

            feedback.setProgress(50)
            if feedback.isCanceled():
                return {}

            # Validate geophysics
            for label, folder in [
                ('Gravity TIF folder',   cfg.geophysics.gravity_folder),
                ('Magnetics TIF folder', cfg.geophysics.magnetics_folder),
            ]:
                if not folder:
                    issues.append(f'WARNING: {label} not set')
                elif not os.path.isdir(folder):
                    issues.append(f'ERROR: {label} not found: {folder}')
                else:
                    tifs = glob.glob(os.path.join(folder, '**', '*.tif'),
                                     recursive=True)
                    if not tifs:
                        issues.append(
                            f'WARNING: {label} contains no .tif files: {folder}')
                    else:
                        feedback.pushInfo(f'✓ {label}: {len(tifs)} TIF files')

            feedback.setProgress(80)
            if feedback.isCanceled():
                return {}

            # Report issues
            errors   = [i for i in issues if i.startswith('ERROR')]
            warnings = [i for i in issues if i.startswith('WARNING')]

            for w in warnings:
                feedback.pushWarning(w)
            for e in errors:
                feedback.reportError(e)

            if errors or (strict and warnings):
                status = 'FAILED'
                feedback.reportError(
                    tr(f'Validation FAILED with {len(errors)} errors, '
                       f'{len(warnings)} warnings.'), fatalError=False)
            else:
                status = 'PASSED'
                feedback.pushInfo(
                    tr(f'✓ Validation PASSED ({len(warnings)} warnings)'))

            feedback.setProgress(100)
            summary = f'{len(errors)} errors, {len(warnings)} warnings'
            return {self.RESULT: status, self.SUMMARY: summary}

        except Exception as e:
            feedback.reportError(
                tr(f'Unexpected error during validation: {e}'), fatalError=True)
            feedback.pushWarning(traceback.format_exc())
            return {self.RESULT: 'ERROR', self.SUMMARY: str(e)}

    def name(self):           return 'loaddata'
    def displayName(self):    return tr('1 — Load & Validate Data')
    def group(self):          return 'Bhumi3DMapper'
    def groupId(self):        return 'bhumi3dmapper'
    def shortHelpString(self):
        return tr('Validates all input data files (drill CSVs, geophysics TIFs) '
                  'and reports any missing or invalid inputs before running the '
                  'prospectivity analysis.')
    def createInstance(self): return LoadDataAlgorithm()
