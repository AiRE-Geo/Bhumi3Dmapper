"""
Module 06 — Voxel Builder
==========================
Assembles the full 3D voxel from all modules.
Iterates over Z levels, calls DrillProcessor + GeophysicsProcessor + ScoringEngine,
packs into numpy structured arrays, saves compressed .npz archives.
Fully config-driven — grid, CRS, Z range, slab size all from ProjectConfig.
"""
import numpy as np, os, time, json

try:
    from ..core.config import ProjectConfig
    from .m02_drill_processor import DrillProcessor
    from .m03_geophys_processor import GeophysicsProcessor
    from .m04_scoring_engine import compute_proximity, compute_blind
except ImportError:
    from core.config import ProjectConfig
    from modules.m02_drill_processor import DrillProcessor
    from modules.m03_geophys_processor import GeophysicsProcessor
    from modules.m04_scoring_engine import compute_proximity, compute_blind

VOXEL_DTYPE = np.dtype([
    ('x_center',      np.float32), ('y_center',     np.float32), ('z_mrl', np.float32),
    ('litho_code',    np.uint8),   ('regime',        np.uint8),
    ('pg_dist_m',     np.float32), ('csr_standoff',  np.float32),
    ('grav_mGal',     np.float32), ('grav_gradient', np.float32), ('grav_laplacian', np.float32),
    ('mag_uSI',       np.float32), ('mag_gradient',  np.float32), ('dist_ore_m',    np.float32),
    ('prox_c1',  np.float32), ('prox_c2',  np.float32), ('prox_c3',  np.float32),
    ('prox_c4',  np.float32), ('prox_c5',  np.float32), ('prox_c6',  np.float32),
    ('prox_c7',  np.float32), ('prox_c9',  np.float32), ('prox_c10', np.float32),
    ('prox_score',    np.float32), ('prox_class',    np.uint8),
    ('blind_c1', np.float32), ('blind_c2', np.float32), ('blind_c3', np.float32),
    ('blind_c4', np.float32), ('blind_c5', np.float32), ('blind_c6', np.float32),
    ('blind_c7b',np.float32), ('blind_c8', np.float32),
    ('blind_c9_lap',  np.float32), ('blind_c10',     np.float32),
    ('blind_score',   np.float32), ('blind_class',   np.uint8),
])


class VoxelBuilder:
    def __init__(self, config: ProjectConfig,
                 drill_proc: DrillProcessor,
                 geophys_proc: GeophysicsProcessor,
                 ore_E: np.ndarray, ore_N: np.ndarray,
                 poly_lu: dict, block_model_df=None):
        self.cfg      = config
        self.dp       = drill_proc
        self.gp       = geophys_proc
        self.ore_E    = ore_E
        self.ore_N    = ore_N
        self.poly_lu  = poly_lu  # {mrl: (cx,cy,area)}
        self.bm_df    = block_model_df

        g = config.grid
        cols = np.arange(g.nx); rows = np.arange(g.ny)
        CC, CR = np.meshgrid(cols, rows)
        self.cell_E = (g.xmin + (CC + 0.5) * g.cell_size_m).astype(np.float32).ravel()
        self.cell_N = (g.ymin + (CR + 0.5) * g.cell_size_m).astype(np.float32).ravel()
        self.N      = g.nx * g.ny

        # Pre-compute fixed distance to nearest ore centroid
        print("Pre-computing ore centroid distances...")
        dE = self.cell_E[:,None] - ore_E[None,:]
        dN = self.cell_N[:,None] - ore_N[None,:]
        self.dist_ore = np.sqrt(dE**2 + dN**2).min(axis=1).astype(np.float32)

    def build(self, progress_callback=None) -> list:
        """
        Build all slabs. Returns list of archive paths written.
        progress_callback(zi, total, z_mrl) called after each level.
        """
        cfg         = self.cfg
        g           = cfg.grid
        out_dir     = cfg.outputs.output_dir
        slab_size   = cfg.outputs.voxel_slab_size
        z_levels    = g.z_levels
        NZ          = len(z_levels)

        os.makedirs(out_dir, exist_ok=True)
        archives    = []
        current_block: dict = {}
        block_z_start = None

        print(f"Building voxel: {g.nx}×{g.ny}×{NZ} = {g.nx*g.ny*NZ:,} cells")
        t0 = time.time()

        for zi, z in enumerate(z_levels):
            z_int = int(z)
            t1    = time.time()

            # Regime
            rid = 2 if z >= 160 else (1 if z >= 60 else 0)
            for regime_def in cfg.regimes.regimes:
                if regime_def['z_min'] <= z <= regime_def['z_max']:
                    rid = regime_def['id']; break

            # Geology
            lv, pg, csr = self.dp.geology_at_level(z)

            # Geophysics
            gf = self.gp.at_level(z)

            # Ore area at nearest available polygon level
            nm_pl   = min(self.poly_lu.keys(), key=lambda k: abs(k - z_int)) \
                      if self.poly_lu else z_int
            ore_area = self.poly_lu.get(nm_pl, (0, 0, 50000))[2]

            inputs = {
                'lv': lv, 'pg': pg, 'csr': csr,
                'grav':           gf['grav'],
                'grav_raw':       gf['grav_raw'],
                'grav_gradient':  gf['grav_gradient'],
                'grav_laplacian': gf['grav_laplacian'],
                'mag':            gf['mag'],
                'mag_gradient':   gf['mag_gradient'],
                'cell_E':         self.cell_E,
                'cell_N':         self.cell_N,
                'z_mrl':          z,
                'regime_id':      rid,
                'dist_ore':       self.dist_ore,
                'ore_area':       ore_area,
                'grav_mean':      gf['grav_mean'],
                'grav_std':       gf['grav_std'],
                'mag_mean':       gf['mag_mean'],
                'mag_std':        gf['mag_std'],
                'gg_mean':        gf['gg_mean'],
                'gg_std':         gf['gg_std'],
                'lap_std':        gf['lap_std'],
                'mg_p50':         gf['mg_p50'],
                'block_model_df': self.bm_df,
            }

            pr = compute_proximity(inputs, cfg)
            br = compute_blind(inputs, cfg)

            # Pack slab
            slab = np.empty(self.N, dtype=VOXEL_DTYPE)
            slab['x_center']      = self.cell_E
            slab['y_center']      = self.cell_N
            slab['z_mrl']         = np.float32(z)
            slab['litho_code']    = lv
            slab['regime']        = np.uint8(rid)
            slab['pg_dist_m']     = np.round(pg,  1)
            slab['csr_standoff']  = np.round(csr, 1)
            slab['grav_mGal']     = np.round(gf['grav_raw'], 4)
            slab['grav_gradient'] = np.round(gf['grav_gradient'], 6)
            slab['grav_laplacian']= np.round(gf['grav_laplacian'], 6)
            slab['mag_uSI']       = np.round(gf['mag'], 2)
            slab['mag_gradient']  = np.round(gf['mag_gradient'], 4)
            slab['dist_ore_m']    = np.round(self.dist_ore, 1)
            for k in ['c1','c2','c3','c4','c5','c6','c7','c9','c10']:
                if k in pr: slab[f'prox_{k}'] = np.round(pr[k], 3)
            slab['prox_score']    = pr['score']
            slab['prox_class']    = pr['class']
            for k in ['c1','c2','c3','c4','c5','c6','c7b','c8','c9_lap','c10']:
                if k in br: slab[f'blind_{k}'] = np.round(br[k], 3)
            slab['blind_score']   = br['score']
            slab['blind_class']   = br['class']

            key = f"z{z_int:+04d}"
            current_block[key] = slab
            if block_z_start is None: block_z_start = z_int

            # Flush slab when block is full or last level
            if (len(current_block) >= slab_size or
                    zi == NZ - 1):
                z_end   = z_int
                name    = f"{cfg.outputs.project_name}_Voxel_z{block_z_start:+04d}_to_{z_end:+04d}.npz"
                arch    = os.path.join(out_dir, name)
                np.savez_compressed(arch, **current_block)
                archives.append(arch)
                sz = os.path.getsize(arch)
                print(f"  Saved {name}: {sz/1e6:.1f} MB "
                      f"({len(current_block)} levels)")
                current_block  = {}
                block_z_start  = None

            if progress_callback:
                progress_callback(zi, NZ, z)
            elif zi % 10 == 0 or zi < 3:
                pvh = int((pr['score'] >= 75).sum())
                bvh = int((br['score'] >= 75).sum())
                print(f"  [{zi+1:3d}/{NZ}] mRL{z_int:+4d}  "
                      f"PVH={pvh:4d}  BVH={bvh:4d}  {time.time()-t1:.0f}s")

        # Write metadata JSON
        self._write_metadata(archives, out_dir)
        print(f"\nVoxel complete: {len(archives)} archives, "
              f"{(time.time()-t0)/60:.1f} min total")
        return archives

    def _write_metadata(self, archives: list, out_dir: str):
        g   = self.cfg.grid
        meta = {
            'project':    self.cfg.project_name,
            'created':    time.strftime('%Y-%m-%d'),
            'grid':       {'nx': g.nx, 'ny': g.ny,
                           'z_min': g.z_bot_mrl, 'z_max': g.z_top_mrl,
                           'cell_size_m': g.cell_size_m,
                           'xmin': g.xmin, 'ymin': g.ymin,
                           'epsg': g.epsg},
            'dtype_fields': list(VOXEL_DTYPE.names),
            'archives': [os.path.basename(a) for a in archives],
            'score_thresholds': self.cfg.scoring.thresholds,
            'proximity_weights': self.cfg.scoring.proximity,
            'blind_weights':     self.cfg.scoring.blind,
        }
        path = os.path.join(out_dir, f"{self.cfg.outputs.project_name}_Voxel_Metadata.json")
        with open(path, 'w') as f:
            json.dump(meta, f, indent=2)
        print(f"  Metadata: {path}")
