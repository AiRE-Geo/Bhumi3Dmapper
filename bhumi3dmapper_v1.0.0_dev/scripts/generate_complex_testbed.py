# -*- coding: utf-8 -*-
"""
Generate a complex test bed for Bhumi3DMapper with:
- 80 deviated drill holes (including S-curves) — desurvey required for correct placement
- Realistic SEDEX stratigraphy placed in 3D world (ore lens dipping 70°)
- Ore polygon GPKG at 3 levels
- Block model with 2 domains
- Gravity and magnetic grids with real anomaly signatures
- Scenarios that should produce Very High prospectivity cells

Outputs to: bhumi3dmapper/examples/complex_testbed/
"""
import os
import json
import math
import sqlite3
import struct
import numpy as np
import pandas as pd
from PIL import Image

np.random.seed(2026)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'bhumi3dmapper', 'examples', 'complex_testbed')

# Clean previous output
import shutil
if os.path.isdir(OUT):
    shutil.rmtree(OUT)
os.makedirs(os.path.join(OUT, 'data'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'geophysics', 'gravity'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'geophysics', 'magnetics'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'ore_polygons'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'block_model'), exist_ok=True)

# ══════════════════════════════════════════════════════════════════════
# Grid: 100×100 cells at 5m = 500m × 500m area
# ══════════════════════════════════════════════════════════════════════
NX, NY = 100, 100
CELL = 5.0
XMIN, YMIN = 469500.0, 2935000.0
XMAX, YMAX = XMIN + NX*CELL, YMIN + NY*CELL  # 470000, 2935500

# Ore body: dipping ore lens centred at (469750, 2935250), depth 100m,
# striking N28°E, dipping 70° to SE. Plunging 30°/075°E.
ORE_CENTRE_E = 469750.0
ORE_CENTRE_N = 2935250.0
ORE_CENTRE_Z = 400.0           # top of ore at 400 mRL (collar area ~460)
ORE_STRIKE_DEG = 28.0          # N28°E
ORE_DIP_DEG = 70.0             # 70° SE
ORE_PLUNGE_AZI = 75.0
ORE_PLUNGE_DIP = 30.0
ORE_WIDTH = 40.0               # thickness across strike
ORE_LENGTH = 300.0             # along strike
ORE_DEPTH_EXTENT = 250.0       # from top of ore down-dip

# ══════════════════════════════════════════════════════════════════════
# Helper: minimum-curvature desurvey (used for test-bed generation)
# ══════════════════════════════════════════════════════════════════════
def desurvey(stations):
    """stations: list of (depth, azi_deg, dip_deg). Returns list of (depth, x, y, z).
    X/Y/Z starting at (0,0,0); offset by collar later."""
    result = [(0.0, 0.0, 0.0, 0.0)]
    x = y = z = 0.0
    prev_inc = math.radians(90 - abs(stations[0][2]))
    prev_azi = math.radians(stations[0][1])
    prev_depth = 0.0
    for d, azi_deg, dip_deg in stations:
        if d <= prev_depth:
            continue
        curr_inc = math.radians(90 - abs(dip_deg))
        curr_azi = math.radians(azi_deg)
        md = d - prev_depth
        cos_dl = (math.cos(curr_inc - prev_inc) -
                  math.sin(prev_inc)*math.sin(curr_inc)*(1 - math.cos(curr_azi - prev_azi)))
        cos_dl = max(-1.0, min(1.0, cos_dl))
        dl = math.acos(cos_dl)
        rf = 1.0 if abs(dl) < 1e-7 else (2.0/dl)*math.tan(dl/2.0)
        dx = 0.5*md*(math.sin(prev_inc)*math.sin(prev_azi) +
                      math.sin(curr_inc)*math.sin(curr_azi))*rf
        dy = 0.5*md*(math.sin(prev_inc)*math.cos(prev_azi) +
                      math.sin(curr_inc)*math.cos(curr_azi))*rf
        dz = -0.5*md*(math.cos(prev_inc) + math.cos(curr_inc))*rf
        x += dx; y += dy; z += dz
        result.append((d, x, y, z))
        prev_inc = curr_inc
        prev_azi = curr_azi
        prev_depth = d
    return result


def distance_to_ore_lens(x, y, z):
    """Return (perpendicular_distance, along_dip_position, along_strike_position)
    from the dipping ore plane.
    ore_lens: strike N28°E, dip 70°SE, centre at (ORE_CENTRE_E, ORE_CENTRE_N, ORE_CENTRE_Z).
    """
    strike_rad = math.radians(ORE_STRIKE_DEG)
    dip_rad = math.radians(ORE_DIP_DEG)
    # Strike direction unit vector (horizontal)
    us = (math.sin(strike_rad), math.cos(strike_rad), 0.0)
    # Dip direction (perpendicular to strike, pointing down-dip SE)
    dip_az_rad = strike_rad + math.pi/2
    ud_horiz = (math.sin(dip_az_rad), math.cos(dip_az_rad))
    ud = (ud_horiz[0]*math.cos(dip_rad), ud_horiz[1]*math.cos(dip_rad), -math.sin(dip_rad))
    # Plane normal
    n = (us[1]*ud[2] - us[2]*ud[1],
         us[2]*ud[0] - us[0]*ud[2],
         us[0]*ud[1] - us[1]*ud[0])
    # Vector from centre to point
    v = (x - ORE_CENTRE_E, y - ORE_CENTRE_N, z - ORE_CENTRE_Z)
    # Perpendicular distance to plane
    perp = abs(v[0]*n[0] + v[1]*n[1] + v[2]*n[2])
    # Along-strike coordinate
    along_s = v[0]*us[0] + v[1]*us[1] + v[2]*us[2]
    # Along-dip coordinate (depth along dip)
    along_d = v[0]*ud[0] + v[1]*ud[1] + v[2]*ud[2]
    return perp, along_s, along_d


def litho_at_point(x, y, z):
    """Return rock code at a true XYZ position.
    Inside the dipping ore lens: QMS (1). Halo: Pegmatite (3).
    Footwall: CSR (4). Hanging wall beyond halo: Amphibolite (2).
    Surface region: Quartzite (5).
    """
    perp, along_s, along_d = distance_to_ore_lens(x, y, z)

    # Out of strike-length envelope? Use Amphibolite (host) or surface Quartzite
    if abs(along_s) > ORE_LENGTH / 2:
        if z > 420:
            return 'QZ'  # Quartzite near surface
        return 'AMPH'

    # Out of dip extent? Amphibolite
    if along_d < -ORE_DEPTH_EXTENT / 2 or along_d > ORE_DEPTH_EXTENT / 2:
        return 'AMPH'

    if perp < ORE_WIDTH / 2:
        # Inside ore lens — QMS host
        return 'QMS'
    if perp < ORE_WIDTH / 2 + 15:
        # Contact halo
        return 'PG'
    if perp < ORE_WIDTH / 2 + 30 and along_d > 0:
        # Footwall side
        return 'CSR'
    return 'AMPH'


# ══════════════════════════════════════════════════════════════════════
# Generate 80 holes — mix of vertical, inclined, and S-curved
# ══════════════════════════════════════════════════════════════════════
print("Generating 80 holes with realistic drilling patterns...")
collar_rows = []
litho_rows = []
assay_rows = []
survey_rows = []

N_HOLES = 80
for i in range(N_HOLES):
    bhid = f'CMP{i+1:03d}'
    xc = np.random.uniform(XMIN + 20, XMAX - 20)
    yc = np.random.uniform(YMIN + 20, YMAX - 20)
    zc = np.random.uniform(455, 475)

    # Drilling pattern varies — 40% vertical, 40% inclined, 20% curved
    pattern = np.random.choice(['vertical', 'inclined', 'curved'],
                                 p=[0.4, 0.4, 0.2])

    # Aim the hole toward or near the ore lens
    # Vector from collar to ore centre
    dx = ORE_CENTRE_E - xc
    dy = ORE_CENTRE_N - yc
    target_azi = math.degrees(math.atan2(dx, dy)) % 360

    max_depth = np.random.uniform(200, 400)

    if pattern == 'vertical':
        stations_local = [(0, 0, -90), (max_depth, 0, -90)]
    elif pattern == 'inclined':
        azi = target_azi + np.random.uniform(-30, 30)
        dip = np.random.uniform(-80, -55)
        stations_local = [(0, azi, dip), (max_depth, azi, dip)]
    else:  # curved — S-curve
        azi1 = target_azi + np.random.uniform(-20, 20)
        dip1 = -60
        azi2 = azi1 + np.random.uniform(-25, 25)
        dip2 = -75
        azi3 = azi2 + np.random.uniform(-15, 15)
        dip3 = -85
        mid = max_depth / 2
        stations_local = [
            (0, azi1, dip1),
            (mid * 0.7, azi1, dip1),
            (mid, azi2, dip2),
            (mid * 1.5, azi2, dip2),
            (max_depth, azi3, dip3),
        ]

    # Desurvey to get true XYZ trajectory (relative to collar)
    traj = desurvey(stations_local)

    collar_rows.append((bhid, xc, yc, zc, max_depth))
    for d, azi, dip in stations_local:
        survey_rows.append((bhid, d, azi, dip))

    # Determine rock code along the hole at 5m intervals
    # Use linear interp between station XYZ
    interval_len = 5.0
    current_rock = None
    interval_start = 0.0

    depths = sorted(set(list(np.arange(0, max_depth + 1, interval_len)) + [max_depth]))
    positions = []
    for d in depths:
        # Linear interpolation in traj (which is sorted by depth)
        for j in range(len(traj) - 1):
            d0, x0, y0, z0 = traj[j]
            d1, x1, y1, z1 = traj[j + 1]
            if d0 <= d <= d1:
                if d1 == d0:
                    t = 0
                else:
                    t = (d - d0) / (d1 - d0)
                x_rel = x0 + t*(x1 - x0)
                y_rel = y0 + t*(y1 - y0)
                z_rel = z0 + t*(z1 - z0)
                positions.append((d, xc + x_rel, yc + y_rel, zc + z_rel))
                break
        else:
            positions.append((d, xc, yc, zc - d))

    # Build litho intervals, grouping consecutive same-rock positions
    depth_rocks = [(d, litho_at_point(x, y, z)) for d, x, y, z in positions]

    for j in range(len(depth_rocks)):
        d, rock = depth_rocks[j]
        if current_rock is None:
            current_rock = rock
            interval_start = 0.0
            continue
        if rock != current_rock:
            litho_rows.append((bhid, interval_start, d, current_rock))
            current_rock = rock
            interval_start = d
    # Final interval
    if current_rock is not None:
        litho_rows.append((bhid, interval_start, max_depth, current_rock))

    # Assay — sample every 2m. Zn grade varies with distance to ore lens.
    for fr in np.arange(0, max_depth, 2.0):
        to = min(fr + 2.0, max_depth)
        mid = (fr + to) / 2.0
        for d, x, y, z in positions:
            if abs(d - mid) < 2.5:
                perp, _, along_d = distance_to_ore_lens(x, y, z)
                if perp < ORE_WIDTH / 2 and abs(along_d) < ORE_DEPTH_EXTENT / 2:
                    zn = np.random.uniform(8, 18)
                    pb = np.random.uniform(2, 6)
                elif perp < ORE_WIDTH / 2 + 15:
                    zn = np.random.uniform(2, 6)
                    pb = np.random.uniform(0.5, 2)
                else:
                    zn = np.random.uniform(0.01, 0.5)
                    pb = np.random.uniform(0.01, 0.2)
                assay_rows.append((bhid, fr, to, zn, pb))
                break

# ── Add 2 holes with data quality issues (intentional, to test DQ gate) ──
# Duplicate BHID
collar_rows.append(('CMP001', 469600.0, 2935100.0, 460.0, 150.0))  # DUPLICATE BHID!
# Hole with negative assay (below detection limit issue)
litho_rows.append(('CMP001_BAD', 0, 50, 'QMS'))
assay_rows.append(('CMP001_BAD', 0, 2, -1.5, 0.2))  # NEGATIVE Zn!

# ── Write CSVs with non-standard column names (to test JC-24 mapping) ──
with open(os.path.join(OUT, 'data', 'collar.csv'), 'w') as f:
    f.write('HOLE_ID,EAST,NORTH,RL,MAX_DEPTH\n')  # non-standard names
    for r in collar_rows:
        f.write(f'{r[0]},{r[1]:.2f},{r[2]:.2f},{r[3]:.2f},{r[4]:.1f}\n')

with open(os.path.join(OUT, 'data', 'litho.csv'), 'w') as f:
    f.write('HOLE_ID,FROM_M,TO_M,ROCK_TYPE\n')  # non-standard names
    for r in litho_rows:
        f.write(f'{r[0]},{r[1]:.1f},{r[2]:.1f},{r[3]}\n')

with open(os.path.join(OUT, 'data', 'assay.csv'), 'w') as f:
    f.write('HOLE_ID,FROM_M,TO_M,Zn_pct,Pb_pct\n')
    for r in assay_rows:
        f.write(f'{r[0]},{r[1]:.1f},{r[2]:.1f},{r[3]:.3f},{r[4]:.3f}\n')

with open(os.path.join(OUT, 'data', 'survey.csv'), 'w') as f:
    # Use MAX_DEPTH to match collar column (col_depth in mapping)
    f.write('HOLE_ID,MAX_DEPTH,AZIMUTH,INCL\n')
    for r in survey_rows:
        f.write(f'{r[0]},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}\n')

print(f"  Holes: {N_HOLES} (+1 duplicate for DQ test)")
print(f"  Litho intervals: {len(litho_rows)}")
print(f"  Assay intervals: {len(assay_rows)} (includes 1 negative for DQ test)")
print(f"  Survey stations: {len(survey_rows)}")

# ══════════════════════════════════════════════════════════════════════
# Generate geophysics — anomalies coincide with ore lens projection
# ══════════════════════════════════════════════════════════════════════
print("\nGenerating geophysics TIFs...")
for mrl in [350, 375, 400, 425]:
    # Project ore lens to this depth level
    grav = np.zeros((NY, NX), dtype=np.float32) + 0.10  # background positive
    mag = np.zeros((10, 10), dtype=np.float32) + 30.0   # background positive (30 uSI)

    # Compute ore intersection with this mRL plane
    yy_g, xx_g = np.meshgrid(np.arange(NY), np.arange(NX), indexing='ij')
    cell_E = XMIN + (xx_g + 0.5) * CELL
    cell_N = YMIN + (yy_g + 0.5) * CELL
    cell_Z = np.full_like(cell_E, float(mrl))

    # Vectorised distance to ore lens
    for i in range(NY):
        for j in range(NX):
            perp, als, alddp = distance_to_ore_lens(cell_E[i, j], cell_N[i, j], cell_Z[i, j])
            if perp < ORE_WIDTH / 2 + 25 and abs(als) < ORE_LENGTH / 2 + 30:
                anom = -0.25 * math.exp(-perp**2 / 400)  # density-negative ore
                grav[i, j] += anom

    # Add random noise
    grav += np.random.normal(0, 0.015, (NY, NX)).astype(np.float32)

    # Magnetics — coarser grid, bigger cell (30m → 10x10 for 300m area)
    # But grid is 500m so use 17x17 or simply 10x10 covering extent
    for i in range(10):
        for j in range(10):
            # 10x10 grid covers 500m x 500m at 50m pixel
            me = XMIN + (j + 0.5) * 50
            mn = YMIN + (i + 0.5) * 50
            perp, als, alddp = distance_to_ore_lens(me, mn, float(mrl))
            if perp < ORE_WIDTH / 2 + 30 and abs(als) < ORE_LENGTH / 2 + 40:
                mag[i, j] -= 40 * math.exp(-perp**2 / 800)

    mag += np.random.normal(0, 2, (10, 10)).astype(np.float32)

    # Save TIFs
    Image.fromarray(grav, mode='F').save(
        os.path.join(OUT, 'geophysics', 'gravity', f'grav_{mrl}.tif'))
    Image.fromarray(mag, mode='F').save(
        os.path.join(OUT, 'geophysics', 'magnetics', f'mag_{mrl}.tif'))

print(f"  Gravity: 4 levels @ 100×100 (5m pixel)")
print(f"  Magnetics: 4 levels @ 10×10 (50m pixel)")

# ══════════════════════════════════════════════════════════════════════
# Ore polygon GPKG — one per level, single polygon outlining ore at that level
# ══════════════════════════════════════════════════════════════════════
print("\nGenerating ore polygon GPKGs...")

def make_simple_polygon_gpkg(path, vertices_xy, level_mrl, epsg=32643):
    """Create a minimal GPKG with one polygon. vertices_xy list of (x, y) tuples."""
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    c = con.cursor()
    c.execute("PRAGMA application_id = 1196444487;")
    c.execute("PRAGMA user_version = 10300;")
    c.execute('''CREATE TABLE gpkg_spatial_ref_sys(
        srs_name TEXT NOT NULL, srs_id INTEGER NOT NULL PRIMARY KEY,
        organization TEXT NOT NULL, organization_coordsys_id INTEGER NOT NULL,
        definition TEXT NOT NULL, description TEXT)''')
    c.execute("INSERT INTO gpkg_spatial_ref_sys VALUES ('UTM43N',32643,'EPSG',32643,'','')")
    c.execute("INSERT INTO gpkg_spatial_ref_sys VALUES ('Undefined Cartesian',-1,'NONE',-1,'undefined','')")
    c.execute("INSERT INTO gpkg_spatial_ref_sys VALUES ('Undefined Geographic',0,'NONE',0,'undefined','')")
    c.execute('''CREATE TABLE gpkg_contents(
        table_name TEXT NOT NULL PRIMARY KEY, data_type TEXT NOT NULL,
        identifier TEXT UNIQUE, description TEXT DEFAULT '',
        last_change DATETIME, min_x DOUBLE, min_y DOUBLE, max_x DOUBLE, max_y DOUBLE,
        srs_id INTEGER)''')
    c.execute('''CREATE TABLE gpkg_geometry_columns(
        table_name TEXT NOT NULL PRIMARY KEY, column_name TEXT NOT NULL,
        geometry_type_name TEXT NOT NULL, srs_id INTEGER NOT NULL,
        z TINYINT NOT NULL, m TINYINT NOT NULL)''')

    table = f'ore_{int(level_mrl):+04d}'.replace('+', 'p').replace('-', 'n')
    xs = [v[0] for v in vertices_xy]
    ys = [v[1] for v in vertices_xy]
    c.execute(f'''CREATE TABLE [{table}](
        fid INTEGER PRIMARY KEY AUTOINCREMENT, geom BLOB, level REAL)''')
    c.execute("INSERT INTO gpkg_contents VALUES (?, 'features', ?, ?, '2026-04-17', ?, ?, ?, ?, ?)",
               (table, table, f'Ore at mRL {level_mrl}', min(xs), min(ys), max(xs), max(ys), 32643))
    c.execute("INSERT INTO gpkg_geometry_columns VALUES (?, 'geom', 'POLYGON', ?, 0, 0)",
               (table, 32643))

    # Build GPKG geometry: header + WKB
    header = struct.pack('<BBBB', 0x47, 0x50, 0x00, 0x00)  # magic 'GP\0\0'
    envelope_flag = 0x01  # envelope indicator bit pattern: 0x01 = XY envelope (4 doubles)
    header += struct.pack('<BBi', envelope_flag, 0, 32643)
    envelope = struct.pack('<dddd', min(xs), max(xs), min(ys), max(ys))

    # WKB: 1 byte byte order + 4 byte type + 4 byte numRings + 4 byte numPoints + points
    wkb = struct.pack('<BI', 1, 3)  # little-endian, Polygon
    wkb += struct.pack('<I', 1)     # 1 ring
    wkb += struct.pack('<I', len(vertices_xy))
    for x, y in vertices_xy:
        wkb += struct.pack('<dd', x, y)
    geom_blob = header + envelope + wkb

    c.execute(f'INSERT INTO [{table}] (geom, level) VALUES (?, ?)', (geom_blob, level_mrl))
    con.commit()
    con.close()


# Generate one ore polygon per level — polygon is the XY footprint of the dipping lens at that mRL
for mrl in [350, 375, 400, 425]:
    # Find polygon of ore at this level
    strike_rad = math.radians(ORE_STRIKE_DEG)
    # Ore lens intersects mRL plane at: points where perp==0 and z==mrl
    # Along strike: ±ORE_LENGTH/2 on strike line
    # Compute the strike line at this level (displaced by dip from centre)
    dz = mrl - ORE_CENTRE_Z  # vertical offset from ore centre
    # Down-dip horizontal offset for vertical change dz: dx = dz / tan(dip)
    dip_rad = math.radians(ORE_DIP_DEG)
    h_offset = dz / math.tan(dip_rad) if abs(dip_rad) > 0.001 else 0
    # Strike azimuth direction
    dip_az_rad = strike_rad + math.pi/2
    cx_lvl = ORE_CENTRE_E + h_offset * math.sin(dip_az_rad)
    cy_lvl = ORE_CENTRE_N + h_offset * math.cos(dip_az_rad)

    # Build polygon: rectangle along strike × across strike (thickness), at this level
    half_len = ORE_LENGTH / 2
    half_wid = ORE_WIDTH / 2
    us = (math.sin(strike_rad), math.cos(strike_rad))
    un = (math.sin(dip_az_rad), math.cos(dip_az_rad))

    corners = [
        (cx_lvl + half_len*us[0] + half_wid*un[0], cy_lvl + half_len*us[1] + half_wid*un[1]),
        (cx_lvl - half_len*us[0] + half_wid*un[0], cy_lvl - half_len*us[1] + half_wid*un[1]),
        (cx_lvl - half_len*us[0] - half_wid*un[0], cy_lvl - half_len*us[1] - half_wid*un[1]),
        (cx_lvl + half_len*us[0] - half_wid*un[0], cy_lvl + half_len*us[1] - half_wid*un[1]),
        (cx_lvl + half_len*us[0] + half_wid*un[0], cy_lvl + half_len*us[1] + half_wid*un[1]),  # close
    ]

    make_simple_polygon_gpkg(
        os.path.join(OUT, 'ore_polygons', f'ore_{mrl}.gpkg'),
        corners, float(mrl))

print(f"  Ore polygons: 4 levels")

# ══════════════════════════════════════════════════════════════════════
# Block model — 2 domains (main_lens + deep_extension)
# ══════════════════════════════════════════════════════════════════════
print("\nGenerating block model...")
main_lens_rows = []
for i in range(200):
    e = np.random.uniform(ORE_CENTRE_E - 100, ORE_CENTRE_E + 100)
    n = np.random.uniform(ORE_CENTRE_N - 150, ORE_CENTRE_N + 150)
    rl = np.random.uniform(350, 425)
    zn = np.random.uniform(4, 15)
    main_lens_rows.append((e, n, rl, zn, zn * 0.3))

deep_ext_rows = []
for i in range(100):
    e = np.random.uniform(ORE_CENTRE_E + 50, ORE_CENTRE_E + 200)
    n = np.random.uniform(ORE_CENTRE_N + 50, ORE_CENTRE_N + 250)
    rl = np.random.uniform(280, 370)
    zn = np.random.uniform(2, 8)
    deep_ext_rows.append((e, n, rl, zn, zn * 0.25))

for name, rows in [('main_lens', main_lens_rows), ('deep_extension', deep_ext_rows)]:
    with open(os.path.join(OUT, 'block_model', f'{name}.csv'), 'w') as f:
        f.write('XC,YC,ZC,ZN,PB\n')
        for r in rows:
            f.write(f'{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.3f},{r[4]:.3f}\n')

print(f"  Block model: 2 domains ({len(main_lens_rows)} + {len(deep_ext_rows)} blocks)")

# ══════════════════════════════════════════════════════════════════════
# Config.json — with non-default column mapping
# ══════════════════════════════════════════════════════════════════════
config = {
    'project_name': 'Complex Test Bed (SEDEX with curving holes)',
    'project_description': 'Synthetic SEDEX ore lens with 80 deviated drill holes. '
                           'Tests desurvey correctness and full pipeline.',
    'deposit_type': 'SEDEX Pb-Zn',
    'location': 'Synthetic complex test bed',
    'crs_epsg': 32643,
    'grid': {
        'xmin': XMIN, 'ymin': YMIN,
        'cell_size_m': 5.0,
        'nx': NX, 'ny': NY,
        'epsg': 32643,
        'z_top_mrl': 425.0, 'z_bot_mrl': 350.0, 'dz_m': 25.0,
    },
    'drill': {
        'collar_csv': os.path.join(OUT, 'data', 'collar.csv'),
        'litho_csv':  os.path.join(OUT, 'data', 'litho.csv'),
        'assay_csv':  os.path.join(OUT, 'data', 'assay.csv'),
        'survey_csv': os.path.join(OUT, 'data', 'survey.csv'),
        # JC-24 column mapping for non-standard names
        'column_mapping': {
            'col_bhid':    'HOLE_ID',
            'col_xcollar': 'EAST',
            'col_ycollar': 'NORTH',
            'col_zcollar': 'RL',
            'col_depth':   'MAX_DEPTH',
            'col_from':    'FROM_M',
            'col_to':      'TO_M',
            'col_rockcode':'ROCK_TYPE',
            'col_azimuth': 'AZIMUTH',
            'col_dip':     'INCL',
            'col_zn':      'Zn_pct',
            'col_pb':      'Pb_pct',
        },
    },
    'geophysics': {
        'gravity_folder':  os.path.join(OUT, 'geophysics', 'gravity'),
        'magnetics_folder': os.path.join(OUT, 'geophysics', 'magnetics'),
        'gravity_pixel_size_m': 5.0,
        'magnetics_pixel_size_m': 50.0,
    },
    'ore_polygons': {
        'polygon_folder': os.path.join(OUT, 'ore_polygons'),
        'mrl_pattern': r'(-?\d+)',
    },
    'block_model': {
        'domain_files': {
            'main_lens': os.path.join(OUT, 'block_model', 'main_lens.csv'),
            'deep_extension': os.path.join(OUT, 'block_model', 'deep_extension.csv'),
        }
    },
    'outputs': {
        'output_dir': os.path.join(OUT, 'outputs'),
        'project_name': 'ComplexTestBed',
    }
}
with open(os.path.join(OUT, 'config.json'), 'w') as f:
    json.dump(config, f, indent=2)

print(f"\n✓ Complex test bed generated at: {OUT}")
print(f"\nKey stress tests built in:")
print(f"  1. 16 S-curved holes (curved drilling requires desurvey)")
print(f"  2. 1 duplicate BHID (DQ gate must catch)")
print(f"  3. 1 negative Zn value (DQ gate must catch)")
print(f"  4. Non-standard column names (JC-24 mapping required)")
print(f"  5. Ore lens dipping 70° — vertical projection places ore wrong")
print(f"  6. 4 depth levels of gravity + magnetics + ore polygons")
print(f"  7. Block model with 2 domains for C9 grade endorsement")
