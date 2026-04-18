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
# TIF loading backends — prefer GDAL (always in QGIS), fallback to rasterio, then PIL
_TIF_BACKEND = None
try:
    from osgeo import gdal
    gdal.UseExceptions()
    _TIF_BACKEND = 'gdal'
except ImportError:
    try:
        import rasterio
        _TIF_BACKEND = 'rasterio'
    except ImportError:
        from PIL import Image
        _TIF_BACKEND = 'pil'

try:
    from ..core.config import ProjectConfig, DrillDataConfig, GeophysicsConfig
except ImportError:
    from core.config import ProjectConfig, DrillDataConfig, GeophysicsConfig


def _detect_encoding(path: str) -> str:
    """
    Try common encodings until one works. Returns encoding name.
    Prefers charset-normalizer if installed, else heuristic trial.
    """
    try:
        with open(path, 'rb') as f:
            raw = f.read(min(100_000, os.path.getsize(path)))
    except Exception:
        return 'utf-8'

    # Try charset-normalizer (optional, best quality)
    try:
        from charset_normalizer import from_bytes
        result = from_bytes(raw).best()
        if result and result.encoding:
            return result.encoding
    except ImportError:
        pass

    # Fallback: trial common encodings
    for enc in ['utf-8-sig', 'utf-8', 'cp1252', 'latin-1', 'shift_jis', 'utf-16']:
        try:
            raw.decode(enc)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return 'latin-1'  # always decodes something


def _read_csv_smart(path: str, **kwargs) -> 'pd.DataFrame':
    """Read CSV with auto-detected encoding. Raises clear error on failure."""
    enc = _detect_encoding(path)
    try:
        return pd.read_csv(path, encoding=enc, **kwargs)
    except UnicodeDecodeError as e:
        raise ValueError(
            f"Cannot read {os.path.basename(path)} — unusual text encoding.\n"
            f"Tried encoding '{enc}' but it failed.\n"
            f"Fix: open the file in Excel and re-save as 'CSV UTF-8 (Comma delimited)'."
        ) from e


def _polygon_area(xs, ys):
    """Shoelace formula for polygon area from coordinate arrays."""
    xs = np.asarray(xs, dtype=np.float64)
    ys = np.asarray(ys, dtype=np.float64)
    return 0.5 * abs(float(np.dot(xs, np.roll(ys, -1)) - np.dot(ys, np.roll(xs, -1))))


class DataLoader:
    def __init__(self, config: ProjectConfig):
        self.cfg = config
        self.dc  = config.drill
        self.gc  = config.geophysics
        self._log = []

    def log(self, msg):
        print(msg); self._log.append(msg)

    def _col(self, field_name: str) -> str:
        """Return the actual column name for a required field, using column_mapping override if set."""
        if getattr(self.dc, 'column_mapping', None) and field_name in self.dc.column_mapping:
            return self.dc.column_mapping[field_name]
        return getattr(self.dc, field_name)

    def _classify_rock_code(self, code: str) -> int:
        """Map a rock code string to an integer lithology code. Unknown codes return 0."""
        return self.cfg.lithology.rock_codes.get(code.upper(), 0)

    # ── DRILL DATA ────────────────────────────────────────────────────────────
    def load_collar(self) -> pd.DataFrame:
        df = _read_csv_smart(self.dc.collar_csv)
        for col in [self._col('col_bhid'), self._col('col_xcollar'),
                    self._col('col_ycollar'), self._col('col_zcollar')]:
            if col not in df.columns:
                raise ValueError(f"Collar file missing column: {col}")
        for c in [self._col('col_xcollar'), self._col('col_ycollar'),
                  self._col('col_zcollar'), self._col('col_depth')]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        self.log(f"Collar: {len(df)} holes from {self.dc.collar_csv}")
        return df

    def load_assay(self) -> pd.DataFrame:
        df = _read_csv_smart(self.dc.assay_csv, low_memory=False)
        for c in [self._col('col_from'), self._col('col_to'),
                  self._col('col_zn'), self._col('col_pb'), self._col('col_ag')]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        self.log(f"Assay: {len(df)} intervals from {self.dc.assay_csv}")
        return df

    def load_litho(self) -> pd.DataFrame:
        df = _read_csv_smart(self.dc.litho_csv)
        for c in [self._col('col_from'), self._col('col_to')]:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        lc_map = self.cfg.lithology.rock_codes
        df['lcode'] = df[self._col('col_rockcode')].apply(
            lambda x: self._classify_rock_code(str(x).strip()))
        self.log(f"Litho: {len(df)} intervals, "
                 f"{df['lcode'].nunique()} unique codes")
        return df

    def load_survey(self) -> pd.DataFrame:
        df = _read_csv_smart(self.dc.survey_csv)
        for c in [self._col('col_azimuth'), self._col('col_dip'), self._col('col_depth')]:
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
            if not m:
                continue
            mrl = int(m.group(1))

            if _TIF_BACKEND == 'gdal':
                ds = gdal.Open(f, gdal.GA_ReadOnly)
                if ds is None:
                    self.log(f"  WARNING: Cannot open {f}")
                    continue
                band = ds.GetRasterBand(1)
                arr = band.ReadAsArray().astype(np.float32) * scale
                nd = band.GetNoDataValue()
                if nd is not None:
                    arr[np.isclose(arr, nd * scale)] = np.nan
                else:
                    arr[np.isclose(arr, nodata * scale)] = np.nan
                ds = None  # close dataset
            elif _TIF_BACKEND == 'rasterio':
                with rasterio.open(f) as src:
                    arr = src.read(1).astype(np.float32) * scale
                    nd = src.nodata
                    if nd is not None:
                        arr[np.isclose(arr, nd * scale)] = np.nan
                    else:
                        arr[np.isclose(arr, nodata * scale)] = np.nan
            else:  # PIL fallback
                arr = np.array(Image.open(f), dtype=np.float32) * scale
                arr[np.isclose(arr, nodata * scale)] = np.nan

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
        # BH-11: detect likely unit scale mismatch (nT or raw 10⁻⁴ SI loaded as µSI).
        # C5/C8 scoring thresholds are calibrated for µSI (typical range −60 to +200).
        # nT values for Indian airborne surveys run 25 000–75 000 — 3 orders of magnitude off.
        if grids:
            sample_arrays = [v[np.isfinite(v)].ravel()
                             for v in grids.values()
                             if np.isfinite(v).any()]
            if sample_arrays:
                all_vals = np.concatenate(sample_arrays)
                p95_abs  = float(np.percentile(np.abs(all_vals), 95))
                if p95_abs > 5_000:
                    warnings.warn(
                        f"BH-11 — Magnetics unit scale suspect: 95th-percentile |value| = "
                        f"{p95_abs:,.0f} (current setting: magnetics_units="
                        f"'{self.gc.magnetics_units}'). "
                        f"C5/C8 thresholds assume µSI (typical |range| < 200). "
                        f"If data is in nT or 10⁻⁴ SI, set magnetics_units in config and "
                        f"confirm the scale factor applied in load_magnetics(). "
                        f"Scoring results will be incorrect at this scale.",
                        stacklevel=2,
                    )
        return grids

    # ── ORE POLYGONS ──────────────────────────────────────────────────────────
    def load_ore_centroids(self) -> pd.DataFrame:
        """
        Returns DataFrame with columns: mrl, cx, cy, area
        Supports: CSV of centroids OR GPKG polygon files.
        """
        opc = self.cfg.ore_polygons
        if opc.centroids_csv and os.path.exists(opc.centroids_csv):
            df = _read_csv_smart(opc.centroids_csv)
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
                                'area': _polygon_area(xs, ys)
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
                df = _read_csv_smart(path, low_memory=False)
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
