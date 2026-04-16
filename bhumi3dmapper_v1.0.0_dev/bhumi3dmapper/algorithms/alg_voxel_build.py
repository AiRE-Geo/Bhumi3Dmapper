# -*- coding: utf-8 -*-
"""Algorithm: Voxel Build — full 3D voxel .npz archive builder."""
import os
import traceback
import numpy as np

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterFile,
    QgsProcessingParameterFolderDestination,
    QgsProcessingOutputString,
    Qgis,
)


def tr(msg):
    return QCoreApplication.translate('VoxelBuildAlgorithm', msg)


class VoxelBuildAlgorithm(QgsProcessingAlgorithm):
    CONFIG     = 'CONFIG'
    OUTPUT_DIR = 'OUTPUT_DIR'
    RESULT     = 'RESULT'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            self.CONFIG, tr('Project configuration file (.json)'),
            QgsProcessingParameterFile.File, extension='json'))
        self.addParameter(QgsProcessingParameterFolderDestination(
            self.OUTPUT_DIR, tr('Output folder for voxel archives')))
        self.addOutput(QgsProcessingOutputString(self.RESULT, tr('Result')))

    def processAlgorithm(self, parameters, context, feedback):
        config_path = self.parameterAsFile(parameters, self.CONFIG, context)
        output_dir  = self.parameterAsString(parameters, self.OUTPUT_DIR, context)
        feedback.setProgress(0)

        try:
            from ..core.config import ProjectConfig
            from ..modules.m01_data_loader import DataLoader
            from ..modules.m02_drill_processor import DrillProcessor
            from ..modules.m03_geophys_processor import GeophysicsProcessor
            from ..modules.m06_voxel_builder import VoxelBuilder

            cfg = ProjectConfig.from_json(config_path)
            cfg.outputs.output_dir = output_dir
            feedback.pushInfo(f'Building voxel for {cfg.project_name}')

            # Load
            feedback.setProgress(5)
            loader = DataLoader(cfg)
            collar_df = loader.load_collar()
            litho_df  = loader.load_litho()
            ore_df    = loader.load_ore_centroids()

            if feedback.isCanceled(): return {}

            # Drill
            feedback.setProgress(15)
            dp = DrillProcessor(cfg)
            dp.build_lookups(collar_df, litho_df)

            # Geophysics
            feedback.setProgress(25)
            gp = GeophysicsProcessor(cfg)
            gp.load(loader.load_gravity(), loader.load_magnetics())

            if feedback.isCanceled(): return {}

            # Ore centroids
            ore_E = ore_df['cx'].values.astype(np.float32) if not ore_df.empty else np.array([0.])
            ore_N = ore_df['cy'].values.astype(np.float32) if not ore_df.empty else np.array([0.])
            poly_lu = {int(r['mrl']): (r['cx'], r['cy'], r['area'])
                       for _, r in ore_df.iterrows()} if not ore_df.empty else {}

            bm_df = None
            try:
                bm_df = loader.load_block_model()
            except Exception:
                pass

            # Build
            vb = VoxelBuilder(cfg, dp, gp, ore_E, ore_N, poly_lu, bm_df)

            def progress_cb(zi, total, z_mrl):
                if feedback.isCanceled():
                    raise KeyboardInterrupt('Cancelled')
                pct = 30 + int(70 * zi / max(total, 1))
                feedback.setProgress(pct)
                feedback.pushInfo(f'  [{zi+1}/{total}] mRL {int(z_mrl):+d}')

            archives = vb.build(progress_callback=progress_cb)
            feedback.setProgress(100)
            feedback.pushInfo(f'✓ Voxel complete: {len(archives)} archives')
            return {self.RESULT: f'OK: {len(archives)} archives'}

        except KeyboardInterrupt:
            return {self.RESULT: 'CANCELLED'}
        except Exception as e:
            feedback.reportError(tr(f'Voxel build failed: {e}'), fatalError=True)
            feedback.pushWarning(traceback.format_exc())
            return {self.RESULT: f'ERROR: {e}'}

    def name(self):           return 'voxelbuild'
    def displayName(self):    return tr('4 — Build 3D Voxel')
    def group(self):          return 'Bhumi3DMapper'
    def groupId(self):        return 'bhumi3dmapper'
    def shortHelpString(self):
        return tr('Builds the full 3D voxel model from loaded data. '
                  'Outputs compressed .npz archives with all criterion scores. '
                  'Warning: this can take several hours for large grids.')
    def createInstance(self): return VoxelBuildAlgorithm()
