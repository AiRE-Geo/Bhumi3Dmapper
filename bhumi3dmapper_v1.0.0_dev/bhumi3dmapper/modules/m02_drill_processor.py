"""
Module 02 — Drill Processor
============================
Builds spatial lookups from drill data:
  - Per-hole lithology intervals as (z_top, z_bot, lcode) tuples
  - PG contact z-levels per hole (structural marker contacts)
  - CSR top-surface z-levels per hole (footwall contacts)
  - Coarse-grid (30m) litho / PG-dist / CSR-standoff arrays for any mRL

Config-driven: rock codes, column names, and grid all come from ProjectConfig.
"""
import math, os, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

try:
    from core.config import ProjectConfig
    from modules.m01_data_loader import DataLoader
except ImportError:
    import sys; sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from core.config import ProjectConfig
    from modules.m01_data_loader import DataLoader


class DrillProcessor:
    def __init__(self, config: ProjectConfig):
        self.cfg   = config
        self.dc    = config.drill
        self.grid  = config.grid
        self.lc    = config.lithology
        # The code used as the "structural marker" (defines the primary fold contact)
        # Default: code 3 = Pegmatite at Kayad. Override in config.
        self.structural_marker_code: int = 3
        # The code used as the "footwall horizon" (CSR at Kayad)
        self.footwall_code: int = 4

        # Built by build_lookups()
        self.bhids:      list  = []
        self.hole_E:     np.ndarray = None
        self.hole_N:     np.ndarray = None
        self.hole_litho: dict  = {}
        self.hole_pg:    dict  = {}
        self.hole_csr:   dict  = {}
        self.hole_coords: dict = {}

        # Coarse grid for fast assignment
        self._cx_arr: np.ndarray = None
        self._cy_arr: np.ndarray = None
        self._sorted_idx: np.ndarray = None
        self._near_dist:  np.ndarray = None

    # ── Build all lookups ─────────────────────────────────────────────────────
    def build_lookups(self, collar_df: pd.DataFrame,
                      litho_df: pd.DataFrame) -> None:
        """Call this once after loading data. Builds all spatial lookups."""
        dc  = self.dc
        clup = collar_df.set_index(dc.col_bhid)[
            [dc.col_xcollar, dc.col_ycollar, dc.col_zcollar]
        ].to_dict('index')

        for bhid, grp in litho_df.sort_values(
                [dc.col_bhid, dc.col_from]).groupby(dc.col_bhid):
            c = clup.get(bhid)
            if not c: continue
            zc = c[dc.col_zcollar]
            self.hole_coords[bhid] = (c[dc.col_xcollar], c[dc.col_ycollar])

            intervals, pg_contacts, csr_tops = [], [], []
            prev_code = None
            for _, row in grp.iterrows():
                if pd.isna(row[dc.col_from]) or pd.isna(row[dc.col_to]): continue
                lc   = int(row['lcode'])
                zt   = zc - row[dc.col_from]
                zb   = zc - row[dc.col_to]
                intervals.append((zt, zb, lc))
                # structural marker contacts
                sm = self.structural_marker_code
                if lc == sm and prev_code != sm: pg_contacts.append(zt)
                if prev_code == sm and lc != sm: pg_contacts.append(zt)
                # footwall tops
                fw = self.footwall_code
                if lc == fw and prev_code != fw: csr_tops.append(zt)
                prev_code = lc

            self.hole_litho[bhid] = intervals
            self.hole_pg[bhid]    = pg_contacts
            self.hole_csr[bhid]   = csr_tops

        self.bhids  = list(self.hole_litho.keys())
        self.hole_E = np.array([self.hole_coords[b][0] for b in self.bhids])
        self.hole_N = np.array([self.hole_coords[b][1] for b in self.bhids])
        self._build_coarse_grid()
        print(f"DrillProcessor: {len(self.bhids)} holes with litho data")

    def _build_coarse_grid(self):
        g = self.grid
        CX = g.cell_size_m * 6  # coarse cell = 30m default
        CNX = int((g.nx * g.cell_size_m) / CX) + 1
        CNY = int((g.ny * g.cell_size_m) / CX) + 1
        self._CX = CX; self._CNX = CNX; self._CNY = CNY
        self._cx_arr = np.array([g.xmin + (j+0.5)*CX for j in range(CNX)],
                                  dtype=np.float32)
        self._cy_arr = np.array([g.ymin + (i+0.5)*CX for i in range(CNY)],
                                  dtype=np.float32)
        CXg, CYg = np.meshgrid(self._cx_arr, self._cy_arr)
        cfE = CXg.ravel(); cfN = CYg.ravel()
        NC  = CNX * CNY
        dE  = cfE[:,None] - self.hole_E[None,:]
        dN  = cfN[:,None] - self.hole_N[None,:]
        d2d = np.sqrt(dE**2 + dN**2)
        k   = min(5, len(self.bhids))
        self._sorted_idx = np.argsort(d2d, axis=1)[:, :k]
        self._near_dist  = d2d[np.arange(NC)[:,None], self._sorted_idx]

    # ── Per-level geology arrays (coarse, then upsample) ─────────────────────
    def geology_at_level(self, z_mrl: float) -> tuple:
        """
        Returns (litho_5m, pg_dist_5m, csr_standoff_5m) as flat numpy arrays
        of length NX*NY, each at 5m resolution.
        """
        g = self.grid
        CX = self._CX; CNX = self._CNX; CNY = self._CNY
        NC = CNX * CNY

        lc_c  = np.zeros(NC, dtype=np.uint8)
        pg_c  = np.full(NC, 200.0, dtype=np.float32)
        csr_c = np.full(NC, 200.0, dtype=np.float32)

        for ci in range(NC):
            best_lc = 0; best_pg = 200.0; best_csr = 200.0
            for ki in range(min(5, self._sorted_idx.shape[1])):
                hi  = self._sorted_idx[ci, ki]
                hd  = float(self._near_dist[ci, ki])
                if hd > self.dc.hole_search_radius_m: break
                bhid = self.bhids[hi]

                if best_lc == 0:
                    for (zt, zb, lcc) in self.hole_litho.get(bhid, []):
                        if zb <= z_mrl <= zt:
                            best_lc = lcc; break

                for pg in self.hole_pg.get(bhid, []):
                    d3 = math.sqrt(hd**2 + (pg - z_mrl)**2)
                    if d3 < best_pg: best_pg = d3

                csrs = self.hole_csr.get(bhid, [])
                if csrs:
                    ca  = np.array(csrs)
                    bel = ca[ca <= z_mrl]
                    if len(bel) > 0:
                        so = float(z_mrl - bel.max())
                        if so < best_csr: best_csr = so

            lc_c[ci] = best_lc; pg_c[ci] = best_pg; csr_c[ci] = best_csr

        factor = int(CX / g.cell_size_m)
        from numpy import kron
        def up(a):
            return kron(a.reshape(CNY, CNX),
                        np.ones((factor, factor), dtype=a.dtype))[:g.ny, :g.nx].ravel()

        return (up(lc_c).astype(np.uint8),
                up(pg_c).astype(np.float32),
                up(csr_c).astype(np.float32))

    # ── Convenience: ore polygon centroid distances ───────────────────────────
    def ore_centroid_distances(self, cell_E: np.ndarray,
                                cell_N: np.ndarray,
                                ore_E:  np.ndarray,
                                ore_N:  np.ndarray) -> np.ndarray:
        """Min 2D distance from each grid cell to any known ore centroid."""
        dE = cell_E[:, None] - ore_E[None, :]
        dN = cell_N[:, None] - ore_N[None, :]
        return np.sqrt(dE**2 + dN**2).min(axis=1).astype(np.float32)


if __name__ == "__main__":
    from core.config import ProjectConfig
    cfg = ProjectConfig.from_json("./configs/kayad_config.json")
    loader = DataLoader(cfg)
    collar = loader.load_collar()
    litho  = loader.load_litho()
    dp = DrillProcessor(cfg)
    dp.build_lookups(collar, litho)
    lv, pg, csr = dp.geology_at_level(185.0)
    print(f"mRL 185: litho codes = {np.unique(lv)}, "
          f"pg_dist range = [{pg.min():.1f}, {pg.max():.1f}]m, "
          f"csr range = [{csr.min():.1f}, {csr.max():.1f}]m")
