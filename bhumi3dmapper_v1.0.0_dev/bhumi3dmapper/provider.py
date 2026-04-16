# -*- coding: utf-8 -*-
"""Processing provider — registers all Bhumi3DMapper algorithms."""
import os
from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon


class Bhumi3DProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        from .algorithms.alg_load_data import LoadDataAlgorithm
        from .algorithms.alg_run_scoring import RunScoringAlgorithm
        from .algorithms.alg_gpkg_export import GpkgExportAlgorithm
        from .algorithms.alg_voxel_build import VoxelBuildAlgorithm
        from .algorithms.alg_load_results import LoadResultsAlgorithm
        for alg_class in [LoadDataAlgorithm, RunScoringAlgorithm,
                           GpkgExportAlgorithm, VoxelBuildAlgorithm,
                           LoadResultsAlgorithm]:
            self.addAlgorithm(alg_class())

    def id(self):        return 'bhumi3dmapper'
    def name(self):      return 'Bhumi3DMapper'
    def longName(self):  return '3D Mineral Prospectivity Mapper'
    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), 'icon.png'))
    def versionInfo(self): return '1.0.0'
