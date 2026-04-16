"""
Module 01 — Data Loader & Validator
=====================================
Loads and validates all input datasets from paths defined in ProjectConfig.
Returns standardised pandas DataFrames and numpy arrays.
Works for any project — column names, file formats and CRS are config-driven.
"""
import os, re, glob, warnings
import numpy as np
import pandas as pd
from PIL import Image
warnings.filterwarnings('ignore')

try:
    from core.config import ProjectConfig, DrillDataConfig, GeophysicsConfig
except ImportError:
    import sys; sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from core.config import ProjectConfig, DrillDataConfig, GeophysicsConfig


class DataLoader:
    def __init__(self, config: ProjectConfig):
        self.cfg = config
        self.dc  = config.drill
        self.gc  = config.geophysics
        self._log = []

    def log(self, msg):
        print(msg); self._log.append(msg)

    # ── DRILL DATA ────────────────────────────────────────────────────────────
    def load_collar(self) -> pd.DataFrame:
        df = pd.read_csv(self.dc.collar_csv)
        for col in [self.dc.col_bhid, self.dc.col_xcollar,
                    self.dc.col_ycollar, self.dc.col_zcollar]:
            if col not in df.columns:
                raise ValueError(f"Collar file missing column: {col}")
        for c in [self.dc.col_xcollar, self.dc.col_ycollar,
                  self.dc.col_zcollar, self.dc.col_depth]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        self.log(f"Collar: {len(df)} holes from {self.dc.collar_csv}")
        return df

    def load_assay(self) -> pd.DataFrame:
        df = pd.read_csv(self.dc.assay_csv, low_memory=False)
        for c in [self.dc.col_from, self.dc.col_to,
                  self.dc.col_zn, self.dc.col_pb]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        self.log(f"Assay: {len(df)} intervals from {self.dc.assay_csv}")
        return df

    def load_litho(self) -> pd.DataFrame:
        df = pd.read_csv(self.dc.litho_csv)
        for c in [self.dc.col_from, self.dc.col_to]:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        lc_map = self.cfg.lithology.rock_codes
        df['lcode'] = df[self.dc.col_rockcode].apply(
            lambda x: lc_map.get(str(x).strip().upper(), 0))
        self.log(f"Litho: {len(df)} intervals, "
                 f"{df['lcode'].nunique()} unique codes")
        return df

    def load_survey(self) -> pd.DataFrame:
        df = pd.read_csv(self.dc.survey_csv)
        for c in [self.dc.col_azimuth, self.dc.col_dip]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        self.log(f"Survey: {len(df)} records from {self.dc.survey_csv}")
        return df

    # ── GEOPHYSICS ────────────────────────────────────────────────────────────
    def _load_tif_folder(self, folder: str, scale: float = 1.0,
                          nodata: float = -9999.0) -> dict:
        """Load all TIF files from a folder, keyed by mRL extracted from filename."""
        grids = {}
        for f in sorted(glob.glob(os.path.join(folder, '**', '*.tif'),
                                   recursive=True)):
            m = re.search(r'(-?\d+)\.tif$', os.path.basename(f),
                          re.IGNORECASE)
            if m:
                mrl = int(m.group(1))
                arr = np.array(Image.open(f), dtype=np.float32) * scale
                arr[arr < nodata * 0.9] = np.nan
                grids[mrl] = arr
        return grids

    def load_gravity(self) -> dict:
        if not self.gc.gravity_folder:
            self.log("Gravity folder not set — skipping")
            return {}
        grids = self._load_tif_folder(
            self.gc.gravity_folder, scale=1.0,
            nodata=self.gc.gravity_nodatavalue)
        self.log(f"Gravity: {len(grids)} levels loaded "
                 f"from {self.gc.gravity_folder}")
        return grids

    def load_magnetics(self) -> dict:
        if not self.gc.magnetics_folder:
            self.log("Magnetics folder not set — skipping")
            return {}
        # HS product is ×10⁻⁴ SI → multiply by 1e4 to get µSI
        scale = 1e4 if self.gc.magnetics_units.lower() in ('si','10-4si') else 1.0
        grids = self._load_tif_folder(
            self.gc.magnetics_folder, scale=scale,
            nodata=self.gc.magnetics_nodatavalue)
        self.log(f"Magnetics: {len(grids)} levels loaded "
                 f"from {self.gc.magnetics_folder}")
        return grids

    # ── ORE POLYGONS ──────────────────────────────────────────────────────────
    def load_ore_centroids(self) -> pd.DataFrame:
        """
        Returns DataFrame with columns: mrl, cx, cy, area
        Supports: CSV of centroids OR GPKG polygon files.
        """
        opc = self.cfg.ore_polygons
        if opc.centroids_csv and os.path.exists(opc.centroids_csv):
            df = pd.read_csv(opc.centroids_csv)
            self.log(f"Ore centroids: {len(df)} records from CSV")
            return df
        if opc.polygon_folder and os.path.isdir(opc.polygon_folder):
            return self._parse_polygon_gpkgs(opc.polygon_folder, opc.mrl_pattern)
        self.log("WARNING: No ore polygon data found")
        return pd.DataFrame(columns=['mrl','cx','cy','area'])

    def _parse_polygon_gpkgs(self, folder: str, pattern: str) -> pd.DataFrame:
        import sqlite3, struct
        records = []
        for f in sorted(glob.glob(os.path.join(folder, '*.gpkg'))):
            m = re.search(pattern, os.path.basename(f))
            if not m: continue
            mrl = int(m.group(1))
            try:
                con = sqlite3.connect(f)
                tabs = [r[0] for r in con.execute(
                    "SELECT table_name FROM gpkg_contents").fetchall()]
                for tab in tabs:
                    for (blob,) in con.execute(
                            f"SELECT geom FROM [{tab}]").fetchall():
                        buf = bytes(blob)
                        xs, ys = self._extract_polygon_coords(buf)
                        if xs:
                            records.append({
                                'mrl': mrl,
                                'cx': sum(xs)/len(xs),
                                'cy': sum(ys)/len(ys),
                                'area': len(xs)*25
                            })
                con.close()
            except Exception as e:
                self.log(f"  Warning: could not parse {f}: {e}")
        df = pd.DataFrame(records)
        self.log(f"Ore polygons: {len(df)} records from {folder}")
        return df

    def _extract_polygon_coords(self, buf):
        import struct
        try:
            wkb = buf[40:]
            gt = struct.unpack_from('<I', wkb, 1)[0]
            xs, ys = [], []
            if gt == 3:    # single polygon
                npts = struct.unpack_from('<I', wkb, 9)[0]
                pts  = struct.unpack_from(f'<{npts*2}d', wkb, 13)
                xs, ys = list(pts[::2]), list(pts[1::2])
            elif gt == 6:  # multipolygon
                ng = struct.unpack_from('<I', wkb, 5)[0]; off = 9
                for _ in range(ng):
                    off += 5  # byte order + type
                    nr = struct.unpack_from('<I', wkb, off)[0]; off += 4
                    np2 = struct.unpack_from('<I', wkb, off)[0]; off += 4
                    pts = struct.unpack_from(f'<{np2*2}d', wkb, off)
                    off += np2 * 16
                    xs += list(pts[::2]); ys += list(pts[1::2])
            return xs, ys
        except:
            return [], []

    # ── BLOCK MODEL ───────────────────────────────────────────────────────────
    def load_block_model(self) -> pd.DataFrame:
        bmc = self.cfg.block_model
        frames = []
        for domain, path in bmc.domain_files.items():
            if os.path.exists(path):
                df = pd.read_csv(path, low_memory=False)
                df['domain'] = domain
                frames.append(df)
                self.log(f"Block model domain '{domain}': {len(df)} blocks")
        if not frames:
            self.log("No block model files found")
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    # ── SUMMARY ───────────────────────────────────────────────────────────────
    def validate_all(self) -> bool:
        ok = True
        for label, path in [
            ("Collar", self.dc.collar_csv),
            ("Assay",  self.dc.assay_csv),
            ("Litho",  self.dc.litho_csv),
        ]:
            if not path:
                print(f"  [WARN] {label} path not set"); ok = False
            elif not os.path.exists(path):
                print(f"  [ERROR] {label} file not found: {path}"); ok = False
            else:
                print(f"  [OK] {label}: {path}")
        for label, folder in [
            ("Gravity",   self.gc.gravity_folder),
            ("Magnetics", self.gc.magnetics_folder),
        ]:
            if not folder:
                print(f"  [WARN] {label} folder not set")
            elif not os.path.isdir(folder):
                print(f"  [ERROR] {label} folder not found: {folder}"); ok = False
            else:
                n = len(glob.glob(os.path.join(folder,'**','*.tif'),recursive=True))
                print(f"  [OK] {label}: {folder} ({n} TIF files)")
        return ok


if __name__ == "__main__":
    from core.config import ProjectConfig
    cfg = ProjectConfig.from_json("./configs/kayad_config.json")
    loader = DataLoader(cfg)
    print("Validating data paths...")
    loader.validate_all()
