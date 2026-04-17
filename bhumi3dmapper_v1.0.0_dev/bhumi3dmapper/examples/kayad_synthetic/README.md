# Bhumi3DMapper Example Project — Synthetic SEDEX

## ⚠️ EXAMPLE DATA — NOT YOUR PROJECT

This is **synthetic data** designed to demonstrate that Bhumi3DMapper runs correctly on your machine. All numbers are made up. Do not use these outputs for real exploration decisions.

## What this demonstrates

A realistic-looking SEDEX Pb-Zn scenario inspired by the Kayad Mine (Rajasthan, India):

- **50 synthetic boreholes** drilled in a 250×250m area
- **5 lithologies** — QMS (host), Pegmatite (structural marker), CSR (footwall), Amphibolite (veto), Quartzite (other)
- **Gravity** — density-negative anomaly in centre (typical SEDEX signature)
- **Magnetics** — persistent magnetic low coincident with ore (Kayad signature)
- **3 depth levels** — mRL 185, 210, 235 (upper mine regime)

## What the tool should produce

When you run the full pipeline on this example:
- 3 GeoPackage files (one per mRL level)
- Prospectivity scores in range 70-95 for centre cells (QMS + negative gravity + magnetic low)
- Amphibolite cells capped at 20 (hard veto)
- Total runtime < 30 seconds on a 2020-era laptop

## Files

```
kayad_synthetic/
├── config.json                  ← Project configuration (paths are rewritten on copy)
├── README.md                    ← This file
├── data/
│   ├── collar.csv               ← 50 boreholes
│   ├── litho.csv                ← 224 litho intervals
│   ├── assay.csv                ← 6,247 assay intervals (2m samples)
│   └── survey.csv               ← Drill hole orientations
└── geophysics/
    ├── gravity/                 ← 3 TIFs at 5m pixel
    │   ├── grav_185.tif
    │   ├── grav_210.tif
    │   └── grav_235.tif
    └── magnetics/               ← 3 TIFs at 30m pixel
        ├── mag_185.tif
        ├── mag_210.tif
        └── mag_235.tif
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
