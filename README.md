# Graph-Based Supply Chain Optimization for Cocoa Farmers in Ghana

Reproducible computational pipeline accompanying the thesis of **Emmanuel Mensah Quaye** (research methodology and results chapters).

## Overview

This repository contains the complete analysis pipeline that:

1. Generates a synthetic, calibrated representation of Ghana’s cocoa supply chain (900 farmers, 45 buying points, 10 depots, 2 ports).
2. Builds a weighted, multi-relational directed graph.
3. Applies centrality analysis, Dijkstra least-cost routing, and Louvain community detection (resolution = 1.0).
4. Trains Random Forest and XGBoost models for farm-gate price with and without network-derived features. The pipeline reports 5-fold cross-validated R² (`results.json`, shown on the Model evidence page, e.g. Random Forest + network 0.8549); `tune_models.py` tunes the models and reports a 720/180 held-out test R² (`tuned_results.json` / `results.json` `ml_tuned`, e.g. tuned Random Forest + network 0.844, shown on the overview card).
5. Runs a 5,000-iteration Monte Carlo simulation of baseline vs. consolidated marketing configurations.
6. Supports a prototype decision-support interface (Cocoa Network).

All stochastic components are governed by the fixed master seed **20250115**. Re-running the pipeline regenerates the network, routing, community, Random Forest, simulation and sensitivity results reported in Chapter 4 exactly. The fixed-configuration XGBoost values and the archived `ml_tuned.xgboost` block in `results.json` are reproduced only approximately (thesis Appendix A.2); the thesis reports the reproducible XGBoost values from `tuned_results.json`.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python analysis_chapter4_pipeline.py
python tune_models.py
python make_figures.py      # Figures 4.1–4.6 → figures/
```

`analysis_chapter4_pipeline.py` rebuilds the study and overwrites `results.json` on every run. `tune_models.py` rebuilds the same dataset (master seed 20250115), grid-searches Random Forest and XGBoost on the training split only, and writes `tuned_results.json`. The tuning script does not modify `results.json`; tuned scores stay in that separate file.

Outputs:

- `results.json` – numeric summaries from the main pipeline (overwritten each time that script runs)
- `tuned_results.json` – tuned Random Forest and XGBoost scores from `tune_models.py` (Tables 4.3 and 4.4)
- intermediate pickles / npy / json files used for figures (`nodes_df.pkl`, `ml_df.pkl`, `df_comm.npy`, `gains_pct.npy`, `per_farm_gain.npy`, `cluster_sizes.json`, `bet_c.json`)
- `figures/fig_4_1.png` … `figures/fig_4_6.png` – thesis Figures 4.1–4.6 at 300 dpi, drawn by `make_figures.py`

## Figures

`make_figures.py` redraws thesis Figures 4.1–4.6 from `results.json`, `tuned_results.json` and the intermediate files above, under the pinned `requirements.txt` (matplotlib 3.9.0). If the intermediate files are not in the working directory (or `--data-dir`), it runs the pipeline in a temporary directory first. Output is deterministic: two runs give byte-identical PNGs.

Figure 4.2 plots the unrounded betweenness values from `bet_c.json` (axis in units of 10⁻⁴, bar labels to 6 dp), so ranks 2–8 (0.000226 to 0.000161) can be told apart; `results.json` rounds them all to 0.0002. Figure 4.5 uses the tuned held-out R² values and the tuned XGBoost feature importance from `tuned_results.json` (Table 4.4).

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

### Prototype files

| File | Role |
|------|------|
| `server/app.py` | Read-only Flask service: serves the front end, `/api/health`, `/api/results` (frozen snapshot) and `/api/scenario` (sensitivity-grid lookup with participation rescaling) |
| `api/index.py` | Vercel entry that re-exports `server.app:app` |
| `src/index.html` | Page markup for the five views |
| `src/app.js` | Front-end logic: charts, network explorer, scenario lab, exports, interpretation panels |
| `src/styles.css` | Screen and print (Export PDF) styles |
| `src/results.json` | Frozen snapshot served by the API and offered as the JSON download |
| `src/interpretations.json` | Plain-language interpretation panel text |
| `public/` | Favicon and social image |
| `pyproject.toml`, `uv.lock` | Deployment dependency (Flask 3.1.2) and its lock file |

`src/results.json` equals the pipeline's `results.json` except that its XGBoost feature importance and `ml_tuned.xgboost` block come from `tuned_results.json` (thesis Table 4.4, Figure 4.5), each marked with a `source` field.

### Run the prototype locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt     # or: pip install Flask==3.1.2
python -c "from server.app import app; app.run(port=5000)"
# open http://localhost:5000
python -m unittest tests.test_report_pdf -v
```

In the Scenario lab, the 3 × 3 grid at 65 % participation shows executed values (800 runs per cell; the central 35 % / GHS 0.30 cell is reported from the 5,000-run simulation). Any other participation level is labelled *Exploratory participation rescaling*.

Sections include evidence overview, network explorer (routes & intermediaries), model evidence, scenario lab, and methods & limits. Results reflect the frozen study run (seed 20250115, 5-fold CV, 5,000 Monte Carlo iterations).

The read-only Flask service is part of this repository root. `server/app.py` defines `app`. Vercel loads it through `tool.vercel.entrypoint = "server.app:app"` in `pyproject.toml`, and `api/index.py` re-exports that same object. The Vercel function installs the `pyproject.toml` dependency (`Flask==3.1.2`). `requirements.txt` remains the local analysis environment and also includes Flask. The service reads the frozen snapshot in `src/results.json`. The interface is `src/index.html`, `src/app.js`, and `src/styles.css`. `public/` holds the icon and social image. Pipeline outputs stay in `results.json` and `tuned_results.json`.

**Export PDF** in the top bar calls `window.print()`. The print stylesheet lays the five views out on A4, one page each, and lets Methods continue onto a second page. It does not rerun the pipeline.

For the `charis5` Vercel project `cocoa-network-decision-support`, keep **Root Directory** as the repository root and keep the Framework Preset as Flask. Pushes to `main` deploy to production through the Git integration.

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
