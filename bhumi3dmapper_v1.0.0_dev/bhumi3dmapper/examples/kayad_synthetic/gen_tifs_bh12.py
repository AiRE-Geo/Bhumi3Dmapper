"""
BH-12: Generate synthetic geophysics TIFs for QMS target zone (mRL 270-370).

Replaces the old footwall TIFs (185, 210, 235) with five levels in the
QMS host-rock target zone where scores should reach 75-85 (High).

Run with: python gen_tifs_bh12.py  (from the kayad_synthetic directory)
Requires: numpy, Pillow
"""
import os
import sys
import numpy as np
from PIL import Image

# ── Grid parameters ────────────────────────────────────────────────────────────
XMIN       = 469490.0
YMIN       = 2934890.0
NX_G       = 50         # gravity: 50 cols at 5m = 250m
NY_G       = 50         # gravity: 50 rows at 5m = 250m
CS_G       = 5.0        # gravity pixel size (m)
NX_M       = 10         # magnetics: 10 cols at 30m = 300m (slightly over-covers)
NY_M       = 10         # magnetics: 10 rows at 30m = 300m
CS_M       = 30.0       # magnetics pixel size (m)

# ── Row ordering: row 0 = SOUTH (smallest N), matching VoxelBuilder meshgrid ──
# col c → E = XMIN + (c + 0.5) * CS
# row r → N = YMIN + (r + 0.5) * CS   (row 0 = southernmost)

# ── Ore pod and structural corridor ───────────────────────────────────────────
# Primary ore pod centre (matched to N28E corridor centroid at QMS levels)
ORE_E      = 469583.0   # easting
ORE_N      = 2935014.0  # northing
# Secondary pod slightly NE (bimodal pattern inherited from corridor geometry)
ORE_E2     = 469618.0
ORE_N2     = 2935062.0

# ── Depth levels ──────────────────────────────────────────────────────────────
LEVELS = [270, 295, 320, 345, 370]

# Gravity anomaly design (mGal)
#   Background: Gaussian regional, mean ~0 mGal (residual field)
#   Ore anomaly: negative Gaussian (density deficit — SEDEX hallmark)
#   Peak at mRL 295 (deepest QMS / mineralised interval)
GRAV_AMP1 = {270: -0.22, 295: -0.32, 320: -0.30, 345: -0.20, 370: -0.12}
GRAV_AMP2 = {270: -0.18, 295: -0.26, 320: -0.24, 345: -0.15, 370: -0.08}
GRAV_SIG1 = {270:  50.0, 295:  62.0, 320:  58.0, 345:  50.0, 370:  42.0}  # σ in m
GRAV_SIG2 = {270:  38.0, 295:  45.0, 320:  42.0, 345:  36.0, 370:  30.0}
GRAV_NOISE = 0.010      # σ of random noise (mGal)
GRAV_BG    = 0.02       # gentle positive regional background

# Magnetics anomaly design (µSI)
#   Background: ~13 µSI (consistent with Kayad Amphibolite/footwall data)
#   Ore anomaly: strongly negative (diamagnetic QMS / sulphide)
#   Peak at mRL 295
MAG_AMP1  = {270: -13.0, 295: -18.0, 320: -16.0, 345: -11.0, 370:  -7.0}
MAG_AMP2  = {270:  -9.0, 295: -13.0, 320: -11.0, 345:  -7.0, 370:  -4.0}
MAG_SIG1  = {270:  50.0, 295:  62.0, 320:  58.0, 345:  50.0, 370:  42.0}
MAG_SIG2  = {270:  38.0, 295:  45.0, 320:  42.0, 345:  36.0, 370:  30.0}
MAG_NOISE  = 1.2        # σ of random noise (µSI)
MAG_BG     = 13.0       # background susceptibility (µSI)


def gaussian_2d(E_arr, N_arr, cx, cy, sigma):
    """Isotropic Gaussian centred at (cx, cy) with σ = sigma metres. Max = 1."""
    d2 = (E_arr - cx)**2 + (N_arr - cy)**2
    return np.exp(-d2 / (2.0 * sigma**2))


def make_grav_grid(mrl, seed):
    """Generate a gravity anomaly grid (NY_G × NX_G) for the given mRL."""
    rng  = np.random.default_rng(seed)
    cols = np.arange(NX_G)
    rows = np.arange(NY_G)
    CC, CR = np.meshgrid(cols, rows)
    E_g  = XMIN + (CC + 0.5) * CS_G   # row 0 = south
    N_g  = YMIN + (CR + 0.5) * CS_G

    # Regional background: gentle N-S gradient + random noise
    arr  = GRAV_BG * np.ones((NY_G, NX_G), dtype=np.float32)
    arr -= 0.005 * (N_g - (YMIN + NY_G * CS_G / 2)) / (NY_G * CS_G / 2)  # subtle regional
    arr += rng.normal(0, GRAV_NOISE, (NY_G, NX_G)).astype(np.float32)

    # Primary and secondary ore pod anomalies
    g1   = gaussian_2d(E_g, N_g, ORE_E, ORE_N, GRAV_SIG1[mrl])
    g2   = gaussian_2d(E_g, N_g, ORE_E2, ORE_N2, GRAV_SIG2[mrl])
    arr += (GRAV_AMP1[mrl] * g1).astype(np.float32)
    arr += (GRAV_AMP2[mrl] * g2).astype(np.float32)

    return arr.astype(np.float32)


def make_mag_grid(mrl, seed):
    """Generate a magnetics grid (NY_M × NX_M) for the given mRL."""
    rng  = np.random.default_rng(seed + 1000)
    cols = np.arange(NX_M)
    rows = np.arange(NY_M)
    CC, CR = np.meshgrid(cols, rows)
    E_m  = XMIN + (CC + 0.5) * CS_M   # row 0 = south
    N_m  = YMIN + (CR + 0.5) * CS_M

    arr  = MAG_BG * np.ones((NY_M, NX_M), dtype=np.float32)
    arr += rng.normal(0, MAG_NOISE, (NY_M, NX_M)).astype(np.float32)

    g1   = gaussian_2d(E_m, N_m, ORE_E, ORE_N, MAG_SIG1[mrl])
    g2   = gaussian_2d(E_m, N_m, ORE_E2, ORE_N2, MAG_SIG2[mrl])
    arr += (MAG_AMP1[mrl] * g1).astype(np.float32)
    arr += (MAG_AMP2[mrl] * g2).astype(np.float32)

    # Clip: no physically unrealistic negatives for magnetics
    # Small negatives OK (diamagnetic minerals), but cap at -20 µSI
    arr = np.clip(arr, -20.0, 40.0)

    return arr.astype(np.float32)


def write_float_tif(arr: np.ndarray, path: str) -> None:
    """Write a 32-bit float TIFF using PIL mode 'F'."""
    img = Image.fromarray(arr, mode='F')
    img.save(path, format='TIFF')


def delete_old_tifs(folder: str, old_levels: list) -> None:
    for lvl in old_levels:
        for stem in ['grav', 'mag']:
            p = os.path.join(folder, f'{stem}_{lvl}.tif')
            if os.path.exists(p):
                os.remove(p)
                print(f"  Removed: {p}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    grav_dir   = os.path.join(script_dir, 'geophysics', 'gravity')
    mag_dir    = os.path.join(script_dir, 'geophysics', 'magnetics')

    print("BH-12 — Generating synthetic QMS-zone geophysics TIFs")
    print(f"  Gravity dir : {grav_dir}")
    print(f"  Magnetics dir: {mag_dir}")
    print()

    # 1. Remove old footwall TIFs
    print("Step 1: Removing old footwall TIFs (mRL 185, 210, 235)...")
    for lvl in [185, 210, 235]:
        for folder, stem in [(grav_dir, 'grav'), (mag_dir, 'mag')]:
            p = os.path.join(folder, f'{stem}_{lvl}.tif')
            if os.path.exists(p):
                os.remove(p)
                print(f"  Removed: {os.path.basename(p)}")

    # 2. Generate new QMS-zone TIFs
    print()
    print("Step 2: Generating QMS-zone TIFs (mRL 270, 295, 320, 345, 370)...")
    np.random.seed(42)   # keep outputs reproducible
    for i, mrl in enumerate(LEVELS):
        seed = 100 + i * 7

        grav = make_grav_grid(mrl, seed)
        grav_path = os.path.join(grav_dir, f'grav_{mrl}.tif')
        write_float_tif(grav, grav_path)
        print(f"  grav_{mrl}.tif : shape={grav.shape}, "
              f"min={grav.min():.3f}, max={grav.max():.3f}, mean={grav.mean():.4f} mGal")

        mag = make_mag_grid(mrl, seed)
        mag_path = os.path.join(mag_dir, f'mag_{mrl}.tif')
        write_float_tif(mag, mag_path)
        print(f"  mag_{mrl}.tif  : shape={mag.shape}, "
              f"min={mag.min():.2f}, max={mag.max():.2f}, mean={mag.mean():.3f} µSI")

    print()
    print("Done. Update config.json: z_top_mrl=370, z_bot_mrl=270, dz_m=25")
    print("Expected: 5 levels → 6,250 cells total")
    print("Expected score range: proximity 72-82 (High) for central QMS cells")
