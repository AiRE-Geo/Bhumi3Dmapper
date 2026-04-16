"""
Module 05 — GeoPackage Writer
================================
Writes 2D per-level prospectivity GeoPackage files.
Handles both proximity and blind models.
Geometry is 5×5m polygon cells. CRS is config-driven.
"""
import sqlite3, struct, os, numpy as np
from typing import Optional

try:
    from ..core.config import ProjectConfig
except ImportError:
    from core.config import ProjectConfig

LITHO_NAMES  = {0:'Unknown',1:'QMS',2:'Amphibolite',3:'Pegmatite',4:'CSR',5:'Quartzite'}
REGIME_NAMES = {0:'Lower mine',1:'Transition',2:'Upper mine'}
CLASS_NAMES  = {0:'Very Low',1:'Low',2:'Moderate',3:'High',4:'Very High'}


def _cell_geom_blob(x0: float, y0: float, dx: float, dy: float,
                    epsg: int) -> bytes:
    x1, y1 = x0 + dx, y0 + dy
    hdr = b'GP' + struct.pack('<BBi4d', 0, 0x03, epsg, x0, x1, y0, y1)
    wkb = struct.pack('<BII', 1, 3, 1) + struct.pack(
        '<I10d', 5, x0,y0, x1,y0, x1,y1, x0,y1, x0,y0)
    return hdr + wkb


def _init_gpkg(path: str, table: str, crs_def: str, epsg: int,
               extra_cols: list) -> sqlite3.Connection:
    if os.path.exists(path): os.remove(path)
    con = sqlite3.connect(path)
    con.execute("PRAGMA application_id = 1196444487")
    con.execute("PRAGMA user_version = 10300")
    con.executescript("""
    CREATE TABLE gpkg_spatial_ref_sys(srs_name TEXT, srs_id INTEGER PRIMARY KEY,
      organization TEXT, organization_coordsys_id INTEGER,
      definition TEXT, description TEXT);
    CREATE TABLE gpkg_contents(table_name TEXT PRIMARY KEY, data_type TEXT,
      identifier TEXT, description TEXT, last_change TEXT,
      min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER);
    CREATE TABLE gpkg_geometry_columns(table_name TEXT, column_name TEXT,
      geometry_type_name TEXT, srs_id INTEGER, z TINYINT, m TINYINT,
      PRIMARY KEY(table_name, column_name));
    """)
    con.execute(f"""INSERT INTO gpkg_spatial_ref_sys VALUES(
        'CRS_{epsg}',{epsg},'EPSG',{epsg},'{crs_def}',NULL)""")

    # Build CREATE TABLE SQL
    base_cols = [
        "fid INTEGER PRIMARY KEY AUTOINCREMENT",
        "geom BLOB NOT NULL",
        "mrl REAL", "regime INTEGER", "regime_name TEXT",
        "litho_code INTEGER", "litho_name TEXT",
        "pg_dist_m REAL", "csr_standoff REAL",
        "grav_mGal REAL", "grav_gradient REAL", "grav_laplacian REAL",
        "mag_uSI REAL", "mag_gradient REAL", "dist_ore_m REAL",
    ]
    base_names = {x.split()[0] for x in base_cols}
    deduped = []
    seen = set(base_names)
    for c in extra_cols:
        col_name = c.split()[0]
        if col_name in seen:
            continue
        seen.add(col_name)
        # If c already includes a type spec (e.g. "prox_class TEXT"), keep as-is
        if len(c.split()) >= 2:
            deduped.append(c)
        else:
            deduped.append(f"{c} REAL")
    all_cols = base_cols + deduped
    con.execute(f"CREATE TABLE {table} ({', '.join(all_cols)})")
    con.execute(f"INSERT INTO gpkg_geometry_columns VALUES "
                f"('{table}','geom','POLYGON',{epsg},0,0)")
    return con


def write_level_gpkg(
    path: str,
    z_mrl: float,
    prox_results: Optional[dict],
    blind_results: Optional[dict],
    geo_fields: dict,
    cell_E: np.ndarray,
    cell_N: np.ndarray,
    cfg: ProjectConfig,
    batch_size: int = 10000,
) -> None:
    """
    Write one GeoPackage for a single mRL level.

    geo_fields: dict with keys matching what GeophysicsProcessor.at_level() returns
                plus 'lv', 'pg', 'csr', 'dist_ore', 'regime_id'
    """
    g      = cfg.grid
    epsg   = g.epsg
    dx     = g.cell_size_m
    table  = f"prospectivity_mRL_{int(z_mrl):+04d}".replace('+','p').replace('-','n')

    # Determine columns
    extra  = []
    if prox_results:
        extra += ['prox_c1','prox_c2','prox_c3','prox_c4','prox_c5',
                  'prox_c6','prox_c7','prox_c9','prox_c10',
                  'prox_score','prox_class TEXT','prox_class_id']
    if blind_results:
        extra += ['blind_c1','blind_c2','blind_c3','blind_c4','blind_c5',
                  'blind_c6','blind_c7b','blind_c8','blind_c9_lap','blind_c10',
                  'blind_score','blind_class TEXT','blind_class_id',
                  'novel_target INTEGER']

    crs_def = (f'PROJCS["UTM_{epsg}",GEOGCS["WGS_1984",'
               f'DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
               f'PRIMEM["Greenwich",0],UNIT["Degree",0.01745329251994]]]')

    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    con = _init_gpkg(path, table, crs_def, epsg, extra)

    n      = len(cell_E)
    lv     = geo_fields['lv']
    pg     = geo_fields['pg']
    csr    = geo_fields['csr']
    gv     = geo_fields.get('grav', np.zeros(n))
    ggv    = geo_fields.get('grav_gradient', np.zeros(n))
    glv    = geo_fields.get('grav_laplacian', np.zeros(n))
    mv     = geo_fields.get('mag', np.full(n, 5.0))
    mgv    = geo_fields.get('mag_gradient', np.zeros(n))
    dorv   = geo_fields.get('dist_ore', np.full(n, 9999.0))
    rid    = int(geo_fields.get('regime_id', 0))

    nd     = cfg.scoring.novelty_distance_m

    batch  = []
    for i in range(n):
        x0    = float(cell_E[i]) - dx/2
        y0    = float(cell_N[i]) - dx/2
        geom  = _cell_geom_blob(x0, y0, dx, dx, epsg)
        lci   = int(lv[i]); pgi = float(pg[i]); csri = float(csr[i])
        gvi   = float(gv[i]); ggvi = float(ggv[i]); glvi = float(glv[i])
        mvi   = float(mv[i]); mgvi = float(mgv[i]); dori = float(dorv[i])

        row   = [None,  # fid — autoincrement
                 geom, z_mrl, rid, REGIME_NAMES.get(rid,'?'),
                 lci, LITHO_NAMES.get(lci,'?'),
                 round(pgi,1), round(csri,1),
                 round(gvi,4), round(ggvi,6), round(glvi,6),
                 round(mvi,2), round(mgvi,4), round(dori,1)]

        if prox_results:
            pc = prox_results
            row += [round(float(pc['c1'][i]),3), round(float(pc['c2'][i]),3),
                    round(float(pc['c3'][i]),3), round(float(pc['c4'][i]),3),
                    round(float(pc['c5'][i]),3), round(float(pc['c6'][i]),3),
                    round(float(pc['c7'][i]),3), round(float(pc['c9'][i]),3),
                    round(float(pc['c10'][i]),3),
                    round(float(pc['score'][i]),1),
                    CLASS_NAMES.get(int(pc['class'][i]),'?'),
                    int(pc['class'][i])]

        if blind_results:
            bc  = blind_results
            nov = 1 if dori > nd else 0
            row += [round(float(bc['c1'][i]),3), round(float(bc['c2'][i]),3),
                    round(float(bc['c3'][i]),3), round(float(bc['c4'][i]),3),
                    round(float(bc['c5'][i]),3), round(float(bc['c6'][i]),3),
                    round(float(bc['c7b'][i]),3),round(float(bc['c8'][i]),3),
                    round(float(bc['c9_lap'][i]),3),round(float(bc['c10'][i]),3),
                    round(float(bc['score'][i]),1),
                    CLASS_NAMES.get(int(bc['class'][i]),'?'),
                    int(bc['class'][i]),
                    nov]

        batch.append(tuple(row))
        if len(batch) >= batch_size:
            _insert_batch(con, table, batch, prox_results is not None,
                          blind_results is not None)
            batch = []

    if batch:
        _insert_batch(con, table, batch,
                      prox_results is not None, blind_results is not None)

    # gpkg_contents
    min_x = float(cell_E.min()) - dx/2; max_x = float(cell_E.max()) + dx/2
    min_y = float(cell_N.min()) - dx/2; max_y = float(cell_N.max()) + dx/2
    con.execute("INSERT INTO gpkg_contents VALUES (?,?,?,?,?,?,?,?,?,?)",
        (table,'features',table,f'Prospectivity mRL {z_mrl:.0f}',
         '2026-01-01', min_x, min_y, max_x, max_y, epsg))
    con.commit(); con.close()


def _insert_batch(con, table, batch, has_prox, has_blind):
    # Build ? placeholders from first row length
    ph = ','.join(['?'] * len(batch[0]))
    # Strip column type specs for INSERT
    con.executemany(f"INSERT INTO {table} VALUES ({ph})", batch)
