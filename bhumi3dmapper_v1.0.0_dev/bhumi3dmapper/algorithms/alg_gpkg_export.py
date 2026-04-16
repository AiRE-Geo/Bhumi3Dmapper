# -*- coding: utf-8 -*-
"""Algorithm: GPKG Export — convert voxel .npz slabs to QGIS-loadable GPKGs."""
import os
import traceback
import glob
import numpy as np

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterFile,
    QgsProcessingParameterString,
    QgsProcessingParameterFolderDestination,
    QgsProcessingOutputString,
    Qgis,
)


def tr(msg):
    return QCoreApplication.translate('GpkgExportAlgorithm', msg)


class GpkgExportAlgorithm(QgsProcessingAlgorithm):
    CONFIG      = 'CONFIG'
    VOXEL_DIR   = 'VOXEL_DIR'
    LEVELS      = 'LEVELS'
    OUTPUT_DIR  = 'OUTPUT_DIR'
    RESULT      = 'RESULT'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            self.CONFIG, tr('Project configuration file (.json)'),
            QgsProcessingParameterFile.File, extension='json'))
        self.addParameter(QgsProcessingParameterFile(
            self.VOXEL_DIR, tr('Folder containing .npz voxel archives'),
            behavior=QgsProcessingParameterFile.Folder))
        self.addParameter(QgsProcessingParameterString(
            self.LEVELS, tr('mRL levels to export (comma-separated)'),
            defaultValue='185,210,235'))
        self.addParameter(QgsProcessingParameterFolderDestination(
            self.OUTPUT_DIR, tr('Output folder for GPKG files')))
        self.addOutput(QgsProcessingOutputString(self.RESULT, tr('Result')))

    def processAlgorithm(self, parameters, context, feedback):
        config_path = self.parameterAsFile(parameters, self.CONFIG, context)
        voxel_dir   = self.parameterAsFile(parameters, self.VOXEL_DIR, context)
        levels_str  = self.parameterAsString(parameters, self.LEVELS, context)
        output_dir  = self.parameterAsString(parameters, self.OUTPUT_DIR, context)
        feedback.setProgress(0)

        try:
            from ..core.config import ProjectConfig
            from ..modules.m05_gpkg_writer import write_level_gpkg

            cfg = ProjectConfig.from_json(config_path)
            levels = [float(l.strip()) for l in levels_str.split(',') if l.strip()]
            archives = sorted(glob.glob(os.path.join(voxel_dir, '*.npz')))

            if not archives:
                feedback.reportError(tr(f'No .npz archives found in {voxel_dir}'))
                return {self.RESULT: 'FAILED: no archives'}

            os.makedirs(output_dir, exist_ok=True)
            exported = 0

            for zi, z in enumerate(levels):
                if feedback.isCanceled(): return {}
                feedback.setProgress(int(100 * zi / max(len(levels), 1)))
                key = f"z{int(z):+04d}"

                found = False
                for arch in archives:
                    d = np.load(arch)
                    if key in d:
                        slab = d[key]
                        path = os.path.join(output_dir,
                            f"{cfg.outputs.project_name}_Voxel_QGIS_mRL{int(z):+04d}.gpkg")

                        # Reconstruct for write_level_gpkg
                        n = len(slab)
                        geo = {
                            'lv': slab['litho_code'], 'pg': slab['pg_dist_m'],
                            'csr': slab['csr_standoff'],
                            'grav': slab['grav_mGal'], 'grav_raw': slab['grav_mGal'],
                            'grav_gradient': slab['grav_gradient'],
                            'grav_laplacian': slab['grav_laplacian'],
                            'mag': slab['mag_uSI'], 'mag_gradient': slab['mag_gradient'],
                            'dist_ore': slab['dist_ore_m'],
                            'regime_id': int(slab['regime'][0]),
                            'grav_mean': 0, 'grav_std': 1,
                            'mag_mean': 0, 'mag_std': 1,
                            'gg_mean': 0, 'gg_std': 1,
                            'lap_std': 1, 'mg_p50': 0.05,
                        }
                        prox = {k.replace('prox_', ''): slab[k]
                                for k in slab.dtype.names
                                if k.startswith('prox_') and k not in ('prox_score', 'prox_class')}
                        prox['score'] = slab['prox_score']
                        prox['class'] = slab['prox_class']
                        blind = {k.replace('blind_', ''): slab[k]
                                 for k in slab.dtype.names
                                 if k.startswith('blind_') and k not in ('blind_score', 'blind_class')}
                        blind['score'] = slab['blind_score']
                        blind['class'] = slab['blind_class']

                        write_level_gpkg(path, z, prox, blind, geo,
                                         slab['x_center'], slab['y_center'], cfg)
                        feedback.pushInfo(f'mRL{int(z):+4d} → {os.path.basename(path)}')
                        exported += 1
                        found = True
                        break

                if not found:
                    feedback.pushWarning(f'mRL {z} not found in any archive')

            feedback.setProgress(100)
            return {self.RESULT: f'OK: {exported} GPKGs exported'}

        except Exception as e:
            feedback.reportError(tr(f'Export failed: {e}'), fatalError=True)
            feedback.pushWarning(traceback.format_exc())
            return {self.RESULT: f'ERROR: {e}'}

    def name(self):           return 'gpkgexport'
    def displayName(self):    return tr('3 — Export Voxel Levels to GPKG')
    def group(self):          return 'Bhumi3DMapper'
    def groupId(self):        return 'bhumi3dmapper'
    def shortHelpString(self):
        return tr('Converts selected mRL levels from voxel .npz archives '
                  'to GeoPackage files loadable in QGIS.')
    def createInstance(self): return GpkgExportAlgorithm()
