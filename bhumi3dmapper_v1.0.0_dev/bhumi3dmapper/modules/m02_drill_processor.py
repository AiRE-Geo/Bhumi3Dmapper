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
import math, os
import numpy as np
import pandas as pd
try:
    from ..core.config import ProjectConfig
    from .m01_data_loader import DataLoader
except ImportError:
    from core.config import ProjectConfig
    from modules.m01_data_loader import DataLoader


def _interp_station(stations, depth):
    """Linear interp XYZ at a given depth along the desurveyed station list.
    stations is a sorted list of (depth, x, y, z) tuples.
    Returns (x, y, z)."""
    if not stations:
        return (0.0, 0.0, 0.0)
    if depth <= stations[0][0]:
        return (stations[0][1], stations[0][2], stations[0][3])
    if depth >= stations[-1][0]:
        return (stations[-1][1], stations[-1][2], stations[-1][3])
    for i in range(len(stations) - 1):
        d0, x0, y0, z0 = stations[i]
        d1, x1, y1, z1 = stations[i + 1]
        if d0 <= depth <= d1:
            if d1 == d0:
                return (x0, y0, z0)
            t = (depth - d0) / (d1 - d0)
            return (x0 + t*(x1-x0), y0 + t*(y1-y0), z0 + t*(z1-z0))
    return (stations[-1][1], stations[-1][2], stations[-1][3])


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

    def _col(self, field_name: str) -> str:
        """Return actual column name for a required field, honouring column_mapping (JC-24)."""
        cm = getattr(self.dc, 'column_mapping', None)
        if cm and field_name in cm:
            return cm[field_name]
        return getattr(self.dc, field_name)

    # ── Build all lookups ─────────────────────────────────────────────────────
    def build_lookups(self, collar_df: pd.DataFrame,
                      litho_df: pd.DataFrame,
                      survey_df: 'pd.DataFrame' = None) -> None:
        """
        Call this once after loading data. Builds all spatial lookups.

        If survey_df is provided, uses minimum-curvature desurvey (JC-07)
        to compute true XYZ per interval — critical for deviated holes.
        Without survey_df, falls back to vertical projection from collar.
        """
        dc  = self.dc
        _bhid  = self._col('col_bhid')
        _xc    = self._col('col_xcollar')
        _yc    = self._col('col_ycollar')
        _zc    = self._col('col_zcollar')
        _from  = self._col('col_from')
        _to    = self._col('col_to')
        clup = collar_df.set_index(_bhid)[
            [_xc, _yc, _zc]
        ].to_dict('index')

        # ── JC-07 wiring: compute desurveyed stations if survey is present ──
        desurvey_stations = {}  # {bhid: [(depth, x, y, z), ...]}
        self._desurvey_used = False
        if survey_df is not None and not survey_df.empty:
            try:
                from .m07_desurvey import minimum_curvature_desurvey
            except ImportError:
                try:
                    from modules.m07_desurvey import minimum_curvature_desurvey
                except ImportError:
                    minimum_curvature_desurvey = None
            if minimum_curvature_desurvey is not None:
                try:
                    _b = self._col('col_bhid')
                    _d = self._col('col_depth')
                    _az = self._col('col_azimuth')
                    _di = self._col('col_dip')
                    _xc2 = self._col('col_xcollar')
                    _yc2 = self._col('col_ycollar')
                    _zc2 = self._col('col_zcollar')
                    ds_df = minimum_curvature_desurvey(
                        survey_df, collar_df,
                        col_bhid=_b, col_depth=_d,
                        col_azi=_az, col_dip=_di,
                        col_x=_xc2, col_y=_yc2, col_z=_zc2,
                    )
                    for bhid, grp in ds_df.groupby(_b):
                        stations = [
                            (float(r[_d]), float(r['X']),
                             float(r['Y']), float(r['Z']))
                            for _, r in grp.sort_values(_d).iterrows()
                        ]
                        desurvey_stations[str(bhid)] = stations
                    self._desurvey_used = True
                except Exception as e:
                    # Desurvey failed — fall back to vertical projection
                    print(f"DrillProcessor: desurvey failed ({e}), "
                          f"falling back to vertical projection")
                    desurvey_stations = {}

        # Per-interval 3D positions: self.hole_intervals_3d[bhid] =
        #   [(depth_top, depth_bot, x_mid, y_mid, z_top, z_bot, lcode), ...]
        self.hole_intervals_3d = {}

        for bhid, grp in litho_df.sort_values(
                [_bhid, _from]).groupby(_bhid):
            bhid_key = str(bhid)
            c = clup.get(bhid)
            if not c: continue
            zc = c[_zc]
            xc = c[_xc]
            yc = c[_yc]
            self.hole_coords[bhid_key] = (xc, yc)

            intervals, pg_contacts, csr_tops = [], [], []
            intervals_3d = []
            prev_code = None
            stations = desurvey_stations.get(bhid_key)

            for _, row in grp.iterrows():
                if pd.isna(row[_from]) or pd.isna(row[_to]): continue
                lc      = int(row['lcode'])
                dfrom   = float(row[_from])
                dto     = float(row[_to])

                if stations is not None:
                    # JC-07: desurveyed XYZ per interval
                    x_top, y_top, z_top = _interp_station(stations, dfrom)
                    x_bot, y_bot, z_bot = _interp_station(stations, dto)
                    x_mid = 0.5 * (x_top + x_bot)
                    y_mid = 0.5 * (y_top + y_bot)
                else:
                    # Fallback: vertical projection from collar
                    z_top = zc - dfrom
                    z_bot = zc - dto
                    x_mid = xc
                    y_mid = yc

                intervals.append((z_top, z_bot, lc))
                intervals_3d.append((dfrom, dto, x_mid, y_mid,
                                      z_top, z_bot, lc))

                # structural marker contacts
                sm = self.structural_marker_code
                if lc == sm and prev_code != sm: pg_contacts.append(z_top)
                if prev_code == sm and lc != sm: pg_contacts.append(z_top)
                # footwall tops
                fw = self.footwall_code
                if lc == fw and prev_code != fw: csr_tops.append(z_top)
                prev_code = lc

            self.hole_litho[bhid_key]       = intervals
            self.hole_pg[bhid_key]          = pg_contacts
            self.hole_csr[bhid_key]         = csr_tops
            self.hole_intervals_3d[bhid_key] = intervals_3d

        self.bhids  = list(self.hole_litho.keys())
        self.hole_E = np.array([self.hole_coords[b][0] for b in self.bhids])
        self.hole_N = np.array([self.hole_coords[b][1] for b in self.bhids])
        self._build_coarse_grid()
        mode = 'desurveyed' if self._desurvey_used else 'vertical-projection'
        print(f"DrillProcessor: {len(self.bhids)} holes with litho data ({mode})")

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

        When self._desurvey_used is True, uses true 3D interval positions
        (JC-07). When False, falls back to collar-projected positions.
        """
        if getattr(self, '_desurvey_used', False):
            return self._geology_at_level_3d(z_mrl)
        return self._geology_at_level_2d(z_mrl)

    def _geology_at_level_3d(self, z_mrl: float) -> tuple:
        """JC-07: true 3D lookup using desurveyed interval midpoints."""
        g = self.grid
        CX = self._CX; CNX = self._CNX; CNY = self._CNY
        NC = CNX * CNY

        # Collect all intervals that straddle z_mrl, with their true XY position
        int_x = []; int_y = []; int_lc = []
        for bhid, ints in self.hole_intervals_3d.items():
            for (dfrom, dto, x_mid, y_mid, z_top, z_bot, lc) in ints:
                if z_bot <= z_mrl <= z_top:
                    int_x.append(x_mid); int_y.append(y_mid); int_lc.append(lc)
        int_x = np.array(int_x, dtype=np.float32)
        int_y = np.array(int_y, dtype=np.float32)
        int_lc = np.array(int_lc, dtype=np.uint8)

        # Pre-compute PG and CSR contact 3D positions at this mRL
        pg_x = []; pg_y = []
        csr_x = []; csr_y = []; csr_z = []
        for bhid, ints in self.hole_intervals_3d.items():
            prev_lc = None
            for (dfrom, dto, x_mid, y_mid, z_top, z_bot, lc) in ints:
                if prev_lc is not None and prev_lc != lc:
                    # contact at z_top
                    if lc == self.structural_marker_code or prev_lc == self.structural_marker_code:
                        pg_x.append(x_mid); pg_y.append(y_mid)
                    if lc == self.footwall_code and prev_lc != self.footwall_code:
                        csr_x.append(x_mid); csr_y.append(y_mid); csr_z.append(z_top)
                prev_lc = lc
        pg_x = np.array(pg_x, dtype=np.float32) if pg_x else np.empty(0, dtype=np.float32)
        pg_y = np.array(pg_y, dtype=np.float32) if pg_y else np.empty(0, dtype=np.float32)
        csr_x = np.array(csr_x, dtype=np.float32) if csr_x else np.empty(0, dtype=np.float32)
        csr_y = np.array(csr_y, dtype=np.float32) if csr_y else np.empty(0, dtype=np.float32)
        csr_z = np.array(csr_z, dtype=np.float32) if csr_z else np.empty(0, dtype=np.float32)

        lc_c  = np.zeros(NC, dtype=np.uint8)
        pg_c  = np.full(NC, 200.0, dtype=np.float32)
        csr_c = np.full(NC, 200.0, dtype=np.float32)

        # Coarse cell centres
        for ci in range(NC):
            cx = float(self._cx_arr[ci % CNX])
            cy = float(self._cy_arr[ci // CNX])

            # Lithology: nearest interval straddling this z
            if len(int_x) > 0:
                d2 = (int_x - cx)**2 + (int_y - cy)**2
                imin = int(np.argmin(d2))
                if float(np.sqrt(d2[imin])) <= self.dc.hole_search_radius_m:
                    lc_c[ci] = int(int_lc[imin])

            # PG halo: 3D distance to nearest PG contact
            if len(pg_x) > 0:
                d2 = (pg_x - cx)**2 + (pg_y - cy)**2
                # At this level; z-offset = 0 (contact already at this level)
                best = float(np.sqrt(d2.min()))
                if best < pg_c[ci]:
                    pg_c[ci] = best

            # CSR standoff: distance to closest CSR top AT OR BELOW this level
            if len(csr_x) > 0:
                mask = csr_z <= z_mrl
                if mask.any():
                    dlat = np.sqrt((csr_x[mask] - cx)**2 + (csr_y[mask] - cy)**2)
                    dvert = z_mrl - csr_z[mask]
                    d3 = np.sqrt(dlat**2 + dvert**2)
                    best = float(d3.min())
                    if best < csr_c[ci]:
                        csr_c[ci] = best

        factor = int(CX / g.cell_size_m)
        from numpy import kron
        def up(a):
            return kron(a.reshape(CNY, CNX),
                        np.ones((factor, factor), dtype=a.dtype))[:g.ny, :g.nx].ravel()
        return (up(lc_c).astype(np.uint8),
                up(pg_c).astype(np.float32),
                up(csr_c).astype(np.float32))

    def _geology_at_level_2d(self, z_mrl: float) -> tuple:
        """Legacy vertical-projection path (no survey data)."""
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
