# -*- coding: utf-8 -*-
"""Algorithm: Run Scoring — compute proximity and blind model scores."""
import os
import traceback
import numpy as np

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterFile,
    QgsProcessingParameterEnum,
    QgsProcessingParameterString,
    QgsProcessingOutputString,
    Qgis,
)


def tr(msg):
    return QCoreApplication.translate('RunScoringAlgorithm', msg)


class RunScoringAlgorithm(QgsProcessingAlgorithm):
    CONFIG  = 'CONFIG'
    MODEL   = 'MODEL'
    LEVELS  = 'LEVELS'
    RESULT  = 'RESULT'

    MODELS = ['Both (Proximity + Blind)', 'Proximity only', 'Blind only']

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            self.CONFIG,
            tr('Project configuration file (.json)'),
            QgsProcessingParameterFile.File, extension='json'))
        self.addParameter(QgsProcessingParameterEnum(
            self.MODEL, tr('Prospectivity model to run'),
            options=self.MODELS, defaultValue=0))
        self.addParameter(QgsProcessingParameterString(
            self.LEVELS, tr('mRL levels (comma-separated, empty=all)'),
            defaultValue='', optional=True))
        self.addOutput(QgsProcessingOutputString(self.RESULT, tr('Result')))

    def processAlgorithm(self, parameters, context, feedback):
        config_path = self.parameterAsFile(parameters, self.CONFIG, context)
        model_idx   = self.parameterAsEnum(parameters, self.MODEL, context)
        levels_str  = self.parameterAsString(parameters, self.LEVELS, context)
        feedback.setProgress(0)

        try:
            from ..core.config import ProjectConfig
            from ..modules.m01_data_loader import DataLoader
            from ..modules.m02_drill_processor import DrillProcessor
            from ..modules.m03_geophys_processor import GeophysicsProcessor
            from ..modules.m04_scoring_engine import compute_proximity, compute_blind
            from ..modules.m05_gpkg_writer import write_level_gpkg

            cfg = ProjectConfig.from_json(config_path)
            feedback.pushInfo(f'Project: {cfg.project_name}')

            # Parse levels
            if levels_str.strip():
                z_levels = [float(l.strip()) for l in levels_str.split(',')]
            else:
                z_levels = cfg.grid.z_levels
            feedback.pushInfo(f'Processing {len(z_levels)} levels')

            # Load data
            feedback.setProgress(5)
            loader = DataLoader(cfg)
            collar_df = loader.load_collar()
            litho_df  = loader.load_litho()
            ore_df    = loader.load_ore_centroids()

            if feedback.isCanceled(): return {}

            # Drill lookups
            feedback.setProgress(15)
            dp = DrillProcessor(cfg)
            dp.build_lookups(collar_df, litho_df)

            # Geophysics
            feedback.setProgress(25)
            gp = GeophysicsProcessor(cfg)
            gp.load(loader.load_gravity(), loader.load_magnetics())

            if feedback.isCanceled(): return {}

            # Cell coords & ore distances
            g = cfg.grid
            cols = np.arange(g.nx); rows = np.arange(g.ny)
            CC, CR = np.meshgrid(cols, rows)
            cell_E = (g.xmin + (CC + 0.5) * g.cell_size_m).astype(np.float32).ravel()
            cell_N = (g.ymin + (CR + 0.5) * g.cell_size_m).astype(np.float32).ravel()

            ore_E = ore_df['cx'].values.astype(np.float32) if not ore_df.empty else np.array([0.])
            ore_N = ore_df['cy'].values.astype(np.float32) if not ore_df.empty else np.array([0.])
            if len(ore_E) > 1:
                dE = cell_E[:, None] - ore_E[None, :]
                dN = cell_N[:, None] - ore_N[None, :]
                dist_ore = np.sqrt(dE**2 + dN**2).min(axis=1).astype(np.float32)
            else:
                dist_ore = np.full(len(cell_E), 9999.0, dtype=np.float32)

            poly_lu = {int(r['mrl']): (r['cx'], r['cy'], r['area'])
                       for _, r in ore_df.iterrows()} if not ore_df.empty else {}

            # Block model (optional)
            bm_df = None
            try:
                bm_df = loader.load_block_model()
            except Exception:
                pass

            # Process levels
            gpkg_dir = os.path.join(cfg.outputs.output_dir, 'gpkg')
            os.makedirs(gpkg_dir, exist_ok=True)
            run_prox  = model_idx in (0, 1)
            run_blind = model_idx in (0, 2)

            for zi, z in enumerate(z_levels):
                if feedback.isCanceled(): return {}
                pct = 30 + int(70 * zi / max(len(z_levels), 1))
                feedback.setProgress(pct)

                rid = 0
                for rd in cfg.regimes.regimes:
                    if rd['z_min'] <= z <= rd['z_max']:
                        rid = rd['id']; break

                lv, pg, csr = dp.geology_at_level(z)
                gf = gp.at_level(z)
                nm = min(poly_lu.keys(), key=lambda k: abs(k - int(z))) if poly_lu else int(z)
                oa = poly_lu.get(nm, (0, 0, 50000))[2]

                inputs = {
                    'lv': lv, 'pg': pg, 'csr': csr,
                    'grav': gf['grav'], 'grav_raw': gf.get('grav_raw', gf['grav']),
                    'grav_gradient': gf['grav_gradient'],
                    'grav_laplacian': gf['grav_laplacian'],
                    'mag': gf['mag'], 'mag_gradient': gf['mag_gradient'],
                    'cell_E': cell_E, 'cell_N': cell_N,
                    'z_mrl': z, 'regime_id': rid,
                    'dist_ore': dist_ore, 'ore_area': oa,
                    'grav_mean': gf['grav_mean'], 'grav_std': gf['grav_std'],
                    'mag_mean': gf['mag_mean'], 'mag_std': gf['mag_std'],
                    'gg_mean': gf['gg_mean'], 'gg_std': gf['gg_std'],
                    'lap_std': gf['lap_std'], 'mg_p50': gf['mg_p50'],
                    'block_model_df': bm_df,
                }

                pr = compute_proximity(inputs, cfg) if run_prox else None
                br = compute_blind(inputs, cfg) if run_blind else None

                geo = {**gf, 'lv': lv, 'pg': pg, 'csr': csr,
                       'dist_ore': dist_ore, 'regime_id': rid}
                path = os.path.join(gpkg_dir,
                    f"{cfg.outputs.project_name}_Prospectivity_mRL{int(z):+04d}.gpkg")
                write_level_gpkg(path, z, pr, br, geo, cell_E, cell_N, cfg)

                pvh = int((pr['score'] >= 75).sum()) if pr else 0
                bvh = int((br['score'] >= 75).sum()) if br else 0
                feedback.pushInfo(
                    f'mRL{int(z):+4d}: PVH={pvh} BVH={bvh} → {os.path.basename(path)}')

            feedback.setProgress(100)
            feedback.pushInfo(f'✓ Scoring complete — {len(z_levels)} GPKGs in {gpkg_dir}')
            return {self.RESULT: f'OK: {len(z_levels)} levels'}

        except Exception as e:
            feedback.reportError(tr(f'Scoring failed: {e}'), fatalError=True)
            feedback.pushWarning(traceback.format_exc())
            return {self.RESULT: f'ERROR: {e}'}

    def name(self):           return 'runscoring'
    def displayName(self):    return tr('2 — Run Prospectivity Scoring')
    def group(self):          return 'Bhumi3DMapper'
    def groupId(self):        return 'bhumi3dmapper'
    def shortHelpString(self):
        return tr('Runs the prospectivity scoring engine on loaded data. '
                  'Generates GeoPackage files for each mRL level with '
                  'both Proximity and Blind model scores.')
    def createInstance(self): return RunScoringAlgorithm()
