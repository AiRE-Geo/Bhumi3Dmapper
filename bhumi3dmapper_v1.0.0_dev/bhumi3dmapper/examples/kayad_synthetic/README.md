# Bhumi3DMapper Example Project — Synthetic SEDEX

## ⚠️ EXAMPLE DATA — NOT YOUR PROJECT

This is **synthetic data** designed to demonstrate that Bhumi3DMapper runs correctly on your machine. All numbers are made up. Do not use these outputs for real exploration decisions.

## What this demonstrates

A realistic-looking SEDEX Pb-Zn scenario inspired by the Kayad Mine (Rajasthan, India):

- **50 synthetic boreholes** drilled in a 250×250m area
- **5 lithologies** — QMS (host), Pegmatite (structural marker), CSR (footwall), Amphibolite (veto), Quartzite (other)
- **Gravity** — density-negative anomaly in centre (typical SEDEX signature)
- **Magnetics** — persistent magnetic low coincident with ore (Kayad signature)
- **5 depth levels** — mRL 270, 295, 320, 345, 370 (QMS host-rock target zone)
- **Stratigraphic context** — collars at ~mRL 440–470; QMS host zone mRL 270–450;
  CSR footwall mRL 230–270; Amphibolite basement below mRL 230 (hard-vetoed)

## What the tool should produce

When you run the full pipeline on this example:
- 5 GeoPackage files (one per mRL level)
- Proximity scores 72–82 (High class) for centre cells at mRL 295–320
  (QMS + strong negative gravity + diamagnetic magnetic low + N28E corridor)
- Blind model scores 78–88 (High–Very High) for the same zone
- Amphibolite cells (none at these levels) would be capped at 20 if present
- Total runtime < 60 seconds on a 2020-era laptop

## Files

```
kayad_synthetic/
├── config.json                  ← Project configuration (paths are rewritten on copy)
├── README.md                    ← This file
├── gen_tifs_bh12.py             ← Script used to regenerate synthetic TIFs (BH-12 fix)
├── data/
│   ├── collar.csv               ← 50 boreholes
│   ├── litho.csv                ← 224 litho intervals
│   ├── assay.csv                ← 6,247 assay intervals (2m samples)
│   └── survey.csv               ← Drill hole orientations
└── geophysics/
    ├── gravity/                 ← 5 TIFs at 5m pixel (mRL 270-370)
    │   ├── grav_270.tif
    │   ├── grav_295.tif
    │   ├── grav_320.tif
    │   ├── grav_345.tif
    │   └── grav_370.tif
    └── magnetics/               ← 5 TIFs at 30m pixel (mRL 270-370)
        ├── mag_270.tif
        ├── mag_295.tif
        ├── mag_320.tif
        ├── mag_345.tif
        └── mag_370.tif
```

## Using the example

The "Try Example Project" button in the plugin:
1. Copies this folder to a location you choose
2. Rewrites `config.json` with absolute paths
3. Runs the full pipeline
4. Loads the results into QGIS with a banner marking them as EXAMPLE DATA

## Adapting to your project

Once you've confirmed the tool works:
1. Start a new project using the "New Project" or "Scan Project Folder" workflow
2. Choose your deposit type (SEDEX, VMS, Epithermal, Porphyry)
3. Point at your actual drill and geophysics data
4. Use the column mapping dialog if your CSVs use different column names
5. Review the data quality report before running scoring
