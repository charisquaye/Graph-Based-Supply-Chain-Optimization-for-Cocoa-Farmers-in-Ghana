# Graph-Based Supply Chain Optimization for Cocoa Farmers in Ghana

Reproducible computational pipeline accompanying the thesis of **Emmanuel Mensah Quaye** (research methodology and results chapters).

## Overview

This repository contains the complete analysis pipeline that:

1. Generates a synthetic, calibrated representation of Ghana’s cocoa supply chain (900 farmers, 45 buying points, 10 depots, 2 ports).
2. Builds a weighted, multi-relational directed graph.
3. Applies centrality analysis, Dijkstra least-cost routing, and Louvain community detection (resolution = 1.0).
4. Trains Random Forest and XGBoost models for farm-gate price with and without network-derived features (5-fold CV, held-out test evaluation).
5. Runs a 5,000-iteration Monte Carlo simulation of baseline vs. consolidated marketing configurations.
6. Supports a prototype decision-support interface (Cocoa Network).

All stochastic components are governed by the fixed master seed **20250115**. Re-running the pipeline regenerates the numerical results reported in Chapter 4 exactly.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python analysis_chapter4_pipeline.py
python tune_models.py
```

`analysis_chapter4_pipeline.py` rebuilds the study and overwrites `results.json` on every run. `tune_models.py` rebuilds the same dataset (master seed 20250115), grid-searches Random Forest and XGBoost on the training split only, and writes `tuned_results.json`. The tuning script does not modify `results.json`; tuned scores stay in that separate file.

Outputs:

- `results.json` – numeric summaries from the main pipeline (overwritten each time that script runs)
- `tuned_results.json` – tuned Random Forest and XGBoost scores from `tune_models.py` (Tables 4.3 and 4.4)
- intermediate pickles / npy files used for figures

## Key parameters (see also Table 4.1 of the thesis)

| Parameter | Value |
|-----------|-------|
| Master seed | 20250115 |
| Farmers / buying / depots / ports | 900 / 45 / 10 / 2 |
| Edge-weight coefficients (α, β, γ, δ) | 1.0, 0.8, 0.6, 25.0 |
| Louvain resolution | 1.0 |
| Cross-validation folds | 5 |
| Monte Carlo iterations | 5 000 |
| Central consolidation saving / premium | 35 % / 0.30 GHS kg⁻¹ |

## Prototype decision-support tool (live)

**Cocoa Network** – interactive decision-support prototype aligned with Chapters 3–4:

- **Live URL:** https://cocoa-network-decision-support.vercel.app/

Sections include evidence overview, network explorer (routes & intermediaries), model evidence, scenario lab, and methods & limits. Results reflect the frozen study run (seed 20250115, 5-fold CV, 5,000 Monte Carlo iterations).

The read-only Flask service is part of this repository root. `server/app.py` defines `app`. Vercel loads it through `tool.vercel.entrypoint = "server.app:app"` in `pyproject.toml`, and `api/index.py` re-exports that same object. The Vercel function installs the `pyproject.toml` dependencies (`Flask==3.1.2` and `fpdf2==2.8.4`). `requirements.txt` remains the local analysis environment and also includes Flask and fpdf2. The service reads the frozen snapshot in `src/results.json`. The interface is `src/index.html`, `src/app.js`, and `src/styles.css`. `public/` holds the icon and social image. Pipeline outputs stay in `results.json` and `tuned_results.json`.

**Export PDF** in the top bar downloads `/api/report.pdf`. That file is built with fpdf2 from the frozen snapshot and uses the same displayed figures. It does not rerun the pipeline.

For the `charis5` Vercel project `cocoa-network-decision-support`, keep **Root Directory** as the repository root and keep the Framework Preset as Flask. The production alias currently serves an earlier upload of this same layout (`server/app.py` and `api/index.py`). Git deployments of `main` looked for a Flask entrypoint in the thesis tree and failed with `FLASK_ENTRYPOINT_NOT_FOUND` until this app was added.

```bash
python -c "from server.app import app"
python -c "from api.index import app"
```

## License

MIT License – see LICENSE. Copyright (c) 2026 Emmanuel Mensah Quaye.

## Citation

If you use this code, the synthetic-data generation procedure, or the analytical pipeline in academic or applied work, please cite the accompanying thesis as:

> Quaye, E. M. (2026). *Graph-based supply chain optimization for cocoa farmers in Ghana* [Thesis]. University of Ghana, Legon.  
> Chapters 3 (Research Methodology) and 4 (Implementation and Results).

Software citation:

> Quaye, E. M. (2026). *Graph-Based Supply Chain Optimization for Cocoa Farmers in Ghana* (Version 1.0) [Computer software]. https://github.com/charisquaye/Graph-Based-Supply-Chain-Optimization-for-Cocoa-Farmers-in-Ghana
