"""
Module 07 — Drill Hole Desurvey
=================================
Minimum curvature method for computing true 3D positions of downhole intervals
from survey data (azimuth + dip at each station).

Pure numpy/pandas — no QGIS dependencies.
"""
import numpy as np
import pandas as pd


def minimum_curvature_desurvey(survey_df: pd.DataFrame,
                                collar_df: pd.DataFrame,
                                col_bhid: str = 'BHID',
                                col_depth: str = 'DEPTH',
                                col_azi: str = 'BRG',
                                col_dip: str = 'DIP',
                                col_x: str = 'XCOLLAR',
                                col_y: str = 'YCOLLAR',
                                col_z: str = 'ZCOLLAR') -> pd.DataFrame:
    """
    Compute true 3D coordinates at each survey station using minimum curvature.

    Parameters
    ----------
    survey_df : DataFrame with columns [BHID, DEPTH, BRG, DIP]
        DIP convention: negative = downward (e.g., -90 = vertical down)
    collar_df : DataFrame with columns [BHID, XCOLLAR, YCOLLAR, ZCOLLAR]

    Returns
    -------
    DataFrame with columns [BHID, DEPTH, X, Y, Z] for each survey station
    """
    results = []
    collar_lookup = collar_df.set_index(col_bhid)[[col_x, col_y, col_z]].to_dict('index')

    for bhid, grp in survey_df.groupby(col_bhid):
        collar = collar_lookup.get(bhid)
        if collar is None:
            continue

        x, y, z = float(collar[col_x]), float(collar[col_y]), float(collar[col_z])
        grp = grp.sort_values(col_depth).reset_index(drop=True)

        # First station at collar
        results.append({col_bhid: bhid, col_depth: 0.0, 'X': x, 'Y': y, 'Z': z})

        # Convert first station angles
        # Inclination from vertical: dip=-90 (down) -> inc=0, dip=0 (horiz) -> inc=90
        prev_inc = np.radians(90.0 - abs(float(grp.iloc[0][col_dip])))
        prev_azi = np.radians(float(grp.iloc[0][col_azi]))
        prev_depth = 0.0

        for i in range(len(grp)):
            curr_depth = float(grp.iloc[i][col_depth])
            curr_inc = np.radians(90.0 - abs(float(grp.iloc[i][col_dip])))
            curr_azi = np.radians(float(grp.iloc[i][col_azi]))

            md = curr_depth - prev_depth
            if md <= 0 and i > 0:
                continue

            if md > 0:
                # Dogleg angle
                cos_dl = (np.cos(curr_inc - prev_inc) -
                          np.sin(prev_inc) * np.sin(curr_inc) *
                          (1 - np.cos(curr_azi - prev_azi)))
                cos_dl = np.clip(cos_dl, -1.0, 1.0)
                dl = np.arccos(cos_dl)

                # Ratio factor
                if abs(dl) < 1e-7:
                    rf = 1.0
                else:
                    rf = 2.0 / dl * np.tan(dl / 2.0)

                # Increments (note: Z positive up, depth positive down)
                dx = 0.5 * md * (np.sin(prev_inc) * np.sin(prev_azi) +
                                  np.sin(curr_inc) * np.sin(curr_azi)) * rf
                dy = 0.5 * md * (np.sin(prev_inc) * np.cos(prev_azi) +
                                  np.sin(curr_inc) * np.cos(curr_azi)) * rf
                dz = -0.5 * md * (np.cos(prev_inc) + np.cos(curr_inc)) * rf

                x += dx
                y += dy
                z += dz

            results.append({col_bhid: bhid, col_depth: curr_depth, 'X': x, 'Y': y, 'Z': z})
            prev_inc = curr_inc
            prev_azi = curr_azi
            prev_depth = curr_depth

    return pd.DataFrame(results)


def interpolate_at_depth(desurvey_df: pd.DataFrame, bhid: str,
                          target_depth: float,
                          col_bhid: str = 'BHID',
                          col_depth: str = 'DEPTH') -> tuple:
    """
    Interpolate X, Y, Z at an arbitrary depth along a desurveyed hole.

    Returns (X, Y, Z) or None if bhid not found.
    """
    hole = desurvey_df[desurvey_df[col_bhid] == bhid].sort_values(col_depth)
    if hole.empty:
        return None

    depths = hole[col_depth].values
    xs = hole['X'].values
    ys = hole['Y'].values
    zs = hole['Z'].values

    if target_depth <= depths[0]:
        return (xs[0], ys[0], zs[0])
    if target_depth >= depths[-1]:
        return (xs[-1], ys[-1], zs[-1])

    # Find bracketing stations
    idx = np.searchsorted(depths, target_depth) - 1
    idx = max(0, min(idx, len(depths) - 2))

    d0, d1 = depths[idx], depths[idx + 1]
    if d1 == d0:
        t = 0.0
    else:
        t = (target_depth - d0) / (d1 - d0)

    return (
        xs[idx] + t * (xs[idx + 1] - xs[idx]),
        ys[idx] + t * (ys[idx + 1] - ys[idx]),
        zs[idx] + t * (zs[idx + 1] - zs[idx]),
    )
