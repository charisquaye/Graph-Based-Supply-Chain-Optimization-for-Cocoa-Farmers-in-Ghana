# Graph-Based Supply Chain Optimization for Cocoa Farmers in Ghana

Reproducible computational pipeline accompanying the thesis chapters on research methodology and results.

## Overview

This repository contains the complete analysis pipeline that:

1. Generates a synthetic, calibrated representation of Ghana’s cocoa supply chain (900 farmers, 45 buying points, 10 depots, 2 ports).
2. Builds a weighted, multi-relational directed graph.
3. Applies centrality analysis, Dijkstra least-cost routing, and Louvain community detection (resolution = 1.0).
4. Trains Random Forest and XGBoost models for farm-gate price with and without network-derived features (5-fold CV, held-out test evaluation).
5. Runs a 5,000-iteration Monte Carlo simulation of baseline vs. consolidated marketing configurations.
6. Supports a prototype decision-support interface (CocoaNet).

All stochastic components are governed by the fixed master seed **20250115**. Re-running the pipeline regenerates the numerical results reported in Chapter 4 exactly.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python analysis_chapter4_pipeline.py
```

Outputs:

- `results.json` – all numeric summaries
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

## Prototype decision-support tool

A web-based prototype (CocoaNet) that surfaces network overview, critical intermediaries, collaborative clusters, and an interactive scenario simulator is deployed separately. See the live URL in the repository description / releases once available.

## License

MIT License – see LICENSE.

## Citation

If you use this code, the synthetic-data generation procedure, or the analytical pipeline in academic or applied work, please cite the accompanying thesis as:

> Quaye, C. (2025). *Graph-based supply chain optimization for cocoa farmers in Ghana* [Master’s / Doctoral thesis]. [Institution].  
> Chapters 3 (Research Methodology) and 4 (Implementation and Results).

A software citation for the repository itself:

> Quaye, C. (2025). *Graph-Based Supply Chain Optimization for Cocoa Farmers in Ghana* (Version 1.0) [Computer software]. https://github.com/charisquaye/Graph-Based-Supply-Chain-Optimization-for-Cocoa-Farmers-in-Ghana
