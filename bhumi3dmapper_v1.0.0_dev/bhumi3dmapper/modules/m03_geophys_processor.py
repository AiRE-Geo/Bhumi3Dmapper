"""
Module 03 — Geophysics Processor
==================================
Computes derived geophysical fields and provides level interpolation:
  - Gravity gradient magnitude (1st spatial derivative)
  - Gravity Laplacian (2nd spatial derivative — closed density deficit detector)
  - Magnetic susceptibility gradient magnitude
  - Linear interpolation between available depth slices
  - Contextual z-score normalisation (for blind model)
  - Nearest-neighbour upsampling to fine grid

All pixel sizes and grid extents come from ProjectConfig — fully portable.
"""
import numpy as np
import os, warnings
warnings.filterwarnings('ignore')

try:
    from core.config import ProjectConfig, GeophysicsConfig, GridConfig
except ImportError:
    import sys; sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from core.config import ProjectConfig, GeophysicsConfig, GridConfig


class GeophysicsProcessor:
    def __init__(self, config: ProjectConfig):
        self.cfg   = config
        self.gc    = config.geophysics
        self.grid  = config.grid

        # Populated by load()
        self.grav_grids:  dict = {}
        self.mag_grids:   dict = {}
        self.grav_grad:   dict = {}
        self.grav_lap:    dict = {}
        self.mag_grad:    dict = {}
        self.grav_levels: list = []
        self.mag_levels:  list = []

    # ── Load and derive ───────────────────────────────────────────────────────
    def load(self, grav_grids: dict, mag_grids: dict) -> None:
        """Pass in the raw dicts from DataLoader, compute all derivatives."""
        self.grav_grids = grav_grids
        self.mag_grids  = mag_grids
        self.grav_levels = sorted(grav_grids.keys())
        self.mag_levels  = sorted(mag_grids.keys())
        dx = self.gc.gravity_pixel_size_m
        cx = self.gc.magnetics_pixel_size_m

        print(f"GeophysicsProcessor: computing derivatives for "
              f"{len(self.grav_levels)} gravity levels, "
              f"{len(self.mag_levels)} mag levels...")

        for mrl, arr in grav_grids.items():
            mv = float(np.nanmean(arr)) if np.isfinite(arr).any() else 0.0
            ac = np.where(np.isfinite(arr), arr, mv)
            gx = np.gradient(ac, axis=1) / dx
            gy = np.gradient(ac, axis=0) / dx
            gm = np.sqrt(gx**2 + gy**2)
            gm[~np.isfinite(arr)] = np.nan
            self.grav_grad[mrl] = gm

            lap = (np.gradient(np.gradient(ac, axis=0), axis=0) +
                   np.gradient(np.gradient(ac, axis=1), axis=1))
            lap[~np.isfinite(arr)] = np.nan
            self.grav_lap[mrl] = lap

        for mrl, arr in mag_grids.items():
            mv = float(np.nanmean(arr)) if np.isfinite(arr).any() else 0.0
            ac = np.where(np.isfinite(arr), arr, mv)
            gx = np.gradient(ac, axis=1) / cx
            gy = np.gradient(ac, axis=0) / cx
            gm = np.sqrt(gx**2 + gy**2)
            gm[~np.isfinite(arr)] = np.nan
            self.mag_grad[mrl] = gm

        print("  Derivatives computed.")

    # ── Interpolation ─────────────────────────────────────────────────────────
    def _interp(self, z: float, gd: dict, sl: list,
                shape: tuple, default=np.nan) -> np.ndarray:
        """Linear interpolation between two nearest levels."""
        if int(z) in gd: return gd[int(z)].copy()
        lo = [l for l in sl if l <= z]
        hi = [l for l in sl if l >= z]
        if not lo and not hi:
            return np.full(shape, default, dtype=np.float32)
        if not lo: return gd[hi[0]].copy()
        if not hi: return gd[lo[-1]].copy()
        lo, hi = lo[-1], hi[0]
        if lo == hi: return gd[lo].copy()
        t  = (z - lo) / (hi - lo)
        gl = gd[lo]; gh = gd[hi]
        out = np.where(np.isfinite(gl) & np.isfinite(gh),
                       (1-t)*gl + t*gh, default)
        return out.astype(np.float32)

    # ── Public: all fields at a given mRL ────────────────────────────────────
    def at_level(self, z_mrl: float) -> dict:
        """
        Returns dict of all geophysical 2D arrays at z_mrl, all at fine grid
        resolution (NX×NY after upsampling), ready to be ravelled to 1D.

        Keys: grav, grav_gradient, grav_laplacian,
              mag, mag_gradient,
              plus contextual statistics for scoring.
        """
        g     = self.grid
        grav_shape = self._infer_grav_shape()
        mag_shape  = self._infer_mag_shape()

        grav_raw  = self._interp(z_mrl, self.grav_grids, self.grav_levels,
                                  grav_shape)
        gg_raw    = self._interp(z_mrl, self.grav_grad, self.grav_levels,
                                  grav_shape, default=0.0)
        glap_raw  = self._interp(z_mrl, self.grav_lap, self.grav_levels,
                                  grav_shape, default=0.0)
        mag_raw   = self._interp(z_mrl, self.mag_grids, self.mag_levels,
                                  mag_shape)
        mg_raw    = self._interp(z_mrl, self.mag_grad, self.mag_levels,
                                  mag_shape, default=0.0)

        # Upsample coarse mag to fine gravity grid
        mag_5m    = self._upsample(
            np.where(np.isfinite(mag_raw), mag_raw, 5.0),
            g.ny, g.nx)
        mg_5m     = self._upsample(mg_raw, g.ny, g.nx)

        grav_mean = float(np.nanmean(grav_raw)) if np.isfinite(grav_raw).any() else 0.0
        grav_std  = float(np.nanstd(grav_raw))  if np.isfinite(grav_raw).any() else 0.01
        mag_mean  = float(np.nanmean(mag_5m));  mag_std  = float(np.nanstd(mag_5m))
        gg_mean   = float(np.nanmean(gg_raw));  gg_std   = float(np.nanstd(gg_raw))
        lap_std   = float(np.nanstd(glap_raw.ravel()))
        mg_p50    = float(np.nanpercentile(mg_5m, 50))

        grav_clean = np.where(np.isfinite(grav_raw), grav_raw, grav_mean)

        return {
            'grav':          grav_clean.ravel().astype(np.float32),
            'grav_raw':      grav_raw.ravel().astype(np.float32),
            'grav_gradient': gg_raw.ravel().astype(np.float32),
            'grav_laplacian':glap_raw.ravel().astype(np.float32),
            'mag':           mag_5m.ravel().astype(np.float32),
            'mag_gradient':  mg_5m.ravel().astype(np.float32),
            # Statistics for contextual scoring
            'grav_mean': grav_mean, 'grav_std': grav_std,
            'mag_mean':  mag_mean,  'mag_std':  mag_std,
            'gg_mean':   gg_mean,   'gg_std':   gg_std,
            'lap_std':   lap_std,   'mg_p50':   mg_p50,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _upsample(self, arr_coarse: np.ndarray, ny: int, nx: int) -> np.ndarray:
        """Nearest-neighbour upsample from coarse to fine grid."""
        from numpy import kron
        cy, cx = arr_coarse.shape
        fy = int(np.ceil(ny / cy)); fx = int(np.ceil(nx / cx))
        f  = max(fy, fx)
        return kron(arr_coarse, np.ones((f, f), dtype=arr_coarse.dtype))[:ny, :nx]

    def _infer_grav_shape(self) -> tuple:
        if self.grav_grids:
            arr = next(iter(self.grav_grids.values()))
            return arr.shape
        g = self.grid
        return (g.ny, g.nx)

    def _infer_mag_shape(self) -> tuple:
        if self.mag_grids:
            arr = next(iter(self.mag_grids.values()))
            return arr.shape
        # Fallback: estimate from pixel size ratio
        g   = self.grid
        rat = int(self.gc.magnetics_pixel_size_m / self.gc.gravity_pixel_size_m)
        return (g.ny // rat + 1, g.nx // rat + 1)


if __name__ == "__main__":
    from core.config import ProjectConfig
    from modules.m01_data_loader import DataLoader
    cfg    = ProjectConfig.from_json("./configs/kayad_config.json")
    loader = DataLoader(cfg)
    grav   = loader.load_gravity()
    mag    = loader.load_magnetics()
    gp     = GeophysicsProcessor(cfg)
    gp.load(grav, mag)
    fields = gp.at_level(185.0)
    print(f"mRL 185 geophysics: grav mean={fields['grav_mean']:.4f} mGal, "
          f"mag mean={fields['mag_mean']:.2f} µSI")
