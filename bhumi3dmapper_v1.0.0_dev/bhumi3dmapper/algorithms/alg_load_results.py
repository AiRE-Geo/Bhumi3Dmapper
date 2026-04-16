# -*- coding: utf-8 -*-
"""Algorithm: Load Results — add scored GPKGs to QGIS with colour symbology."""
import os
import glob
import traceback

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterFile,
    QgsProcessingParameterEnum,
    QgsProcessingParameterBoolean,
    QgsProcessingOutputString,
    QgsVectorLayer,
    QgsProject,
    QgsRendererCategory,
    QgsCategorizedSymbolRenderer,
    QgsSymbol,
    QgsFillSymbol,
    Qgis,
)


def tr(msg):
    return QCoreApplication.translate('LoadResultsAlgorithm', msg)


# Colour ramp: VL→VH  (grey, blue, yellow, orange, red)
CLASS_COLOURS = {
    0: ('#cccccc', 'Very Low'),
    1: ('#4575b4', 'Low'),
    2: ('#fee090', 'Moderate'),
    3: ('#f46d43', 'High'),
    4: ('#d73027', 'Very High'),
}


class LoadResultsAlgorithm(QgsProcessingAlgorithm):
    GPKG_DIR    = 'GPKG_DIR'
    SCORE_FIELD = 'SCORE_FIELD'
    ADD_ALL     = 'ADD_ALL'
    RESULT      = 'RESULT'

    SCORE_OPTIONS = ['prox_class_id', 'blind_class_id']

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            self.GPKG_DIR, tr('Folder containing scored GPKG files'),
            behavior=QgsProcessingParameterFile.Folder))
        self.addParameter(QgsProcessingParameterEnum(
            self.SCORE_FIELD, tr('Classification field to symbolise'),
            options=self.SCORE_OPTIONS, defaultValue=0))
        self.addParameter(QgsProcessingParameterBoolean(
            self.ADD_ALL, tr('Add all levels (uncheck to add top/bottom only)'),
            defaultValue=True))
        self.addOutput(QgsProcessingOutputString(self.RESULT, tr('Result')))

    def processAlgorithm(self, parameters, context, feedback):
        gpkg_dir    = self.parameterAsFile(parameters, self.GPKG_DIR, context)
        field_idx   = self.parameterAsEnum(parameters, self.SCORE_FIELD, context)
        add_all     = self.parameterAsBoolean(parameters, self.ADD_ALL, context)
        feedback.setProgress(0)

        try:
            score_field = self.SCORE_OPTIONS[field_idx]
            gpkgs = sorted(glob.glob(os.path.join(gpkg_dir, '*.gpkg')))

            if not gpkgs:
                feedback.reportError(tr(f'No GPKG files found in {gpkg_dir}'))
                return {self.RESULT: 'FAILED: no GPKGs'}

            if not add_all and len(gpkgs) > 2:
                gpkgs = [gpkgs[0], gpkgs[-1]]

            loaded = 0
            for gi, gpkg_path in enumerate(gpkgs):
                if feedback.isCanceled(): return {}
                feedback.setProgress(int(100 * gi / max(len(gpkgs), 1)))

                basename = os.path.splitext(os.path.basename(gpkg_path))[0]
                layer = QgsVectorLayer(gpkg_path, basename, 'ogr')

                if not layer.isValid():
                    feedback.pushWarning(f'Could not load: {gpkg_path}')
                    continue

                # Apply categorised symbology
                if score_field in [f.name() for f in layer.fields()]:
                    self._apply_class_symbology(layer, score_field)

                QgsProject.instance().addMapLayer(layer)
                loaded += 1
                feedback.pushInfo(f'✓ Loaded: {basename}')

            feedback.setProgress(100)
            feedback.pushInfo(f'✓ {loaded} layers loaded with {score_field} symbology')
            return {self.RESULT: f'OK: {loaded} layers'}

        except Exception as e:
            feedback.reportError(tr(f'Load failed: {e}'), fatalError=True)
            feedback.pushWarning(traceback.format_exc())
            return {self.RESULT: f'ERROR: {e}'}

    def _apply_class_symbology(self, layer, field_name):
        """Apply colour-coded categorised renderer."""
        categories = []
        for class_id, (colour, label) in CLASS_COLOURS.items():
            symbol = QgsFillSymbol.createSimple({
                'color': colour,
                'outline_style': 'no',
            })
            cat = QgsRendererCategory(class_id, symbol, label)
            categories.append(cat)

        renderer = QgsCategorizedSymbolRenderer(field_name, categories)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def name(self):           return 'loadresults'
    def displayName(self):    return tr('5 — Load Results into QGIS')
    def group(self):          return 'Bhumi3DMapper'
    def groupId(self):        return 'bhumi3dmapper'
    def shortHelpString(self):
        return tr('Loads scored GeoPackage files into the current QGIS project '
                  'with colour-coded prospectivity symbology. '
                  'Red = Very High, Orange = High, Yellow = Moderate, '
                  'Blue = Low, Grey = Very Low.')
    def createInstance(self): return LoadResultsAlgorithm()
