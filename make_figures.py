"""Regenerate thesis Figures 4.1-4.6 from the archived results and pipeline outputs.

Inputs
  results.json, tuned_results.json      archived results (repository root)
  nodes_df.pkl, df_comm.npy, ml_df.pkl,  intermediate files written by
  per_farm_gain.npy, cluster_sizes.json, analysis_chapter4_pipeline.py
  bet_c.json
Outputs
  figures/fig_4_1.png ... figures/fig_4_6.png (300 dpi)

Usage (Python 3.12, pinned requirements.txt):
  python analysis_chapter4_pipeline.py   # writes the intermediate files
  python make_figures.py [--data-dir DIR] [--out-dir figures]

If the intermediate files are missing from --data-dir, the script runs the
archived pipeline in a temporary directory first (seed 20250115; deterministic).
Figure 4.2 plots the unrounded betweenness values from bet_c.json, so the
ranks 2-8 that round to 0.0002 in results.json remain distinguishable.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parent
DPI = 300
INTERMEDIATES = ("nodes_df.pkl", "df_comm.npy", "ml_df.pkl", "per_farm_gain.npy",
                 "cluster_sizes.json", "bet_c.json")
REGION_COLOURS = {
    "Ashanti": "#4c5a7a", "Central": "#b27bc9", "Eastern": "#d4a94f",
    "Volta": "#c9605d", "Western North": "#4f9e91", "Western South": "#7f9cc6",
}
NAVY, BLUE, TEAL, PALE, GREY = "#1f3864", "#3d6aa8", "#11776b", "#dbe2ef", "#6b6b6b"
NETWORK_FEATURES = {"route_cost", "comm_size", "degree", "betweenness", "closeness"}


def ensure_intermediates(data_dir: Path) -> Path:
    if all((data_dir / name).exists() for name in INTERMEDIATES):
        return data_dir
    work = Path(tempfile.mkdtemp(prefix="cocoa-figs-"))
    shutil.copy(ROOT / "analysis_chapter4_pipeline.py", work)
    print(f"Intermediate files missing; running the pipeline in {work}")
    subprocess.run([sys.executable, "analysis_chapter4_pipeline.py"], cwd=work, check=True)
    return work


def save(fig, out_dir: Path, name: str) -> Path:
    path = out_dir / name
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_4_1(nodes: pd.DataFrame, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(7, 6))
    farmers = nodes[nodes.kind == "farmer"]
    for region, colour in REGION_COLOURS.items():
        sub = farmers[farmers.region == region]
        ax.scatter(sub.lon, sub.lat, s=6, color=colour, alpha=0.8, label=region)
    styles = {"buying": dict(marker="s", s=60, facecolor="white", edgecolor="black", label="Buying point"),
              "depot": dict(marker="^", s=150, color="#1a1a1a", edgecolor="black", label="Depot"),
              "port": dict(marker="*", s=220, color="#b8860b", edgecolor="black", label="Port")}
    for kind, style in styles.items():
        sub = nodes[nodes.kind == kind]
        ax.scatter(sub.lon, sub.lat, zorder=3, **style)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower left", ncol=2, fontsize=8)
    return save(fig, out, "fig_4_1.png")


def fig_4_2(nodes: pd.DataFrame, bet: dict, out: Path) -> Path:
    inter = nodes[nodes.kind.isin(["buying", "depot"])].copy()
    inter["bet"] = inter.node.map(bet)
    top = inter.sort_values("bet", ascending=False).head(8)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    colours = [NAVY if k == "depot" else BLUE for k in top.kind]
    values = top.bet.to_numpy() * 1e4
    bars = ax.bar(range(len(top)), values, color=colours, edgecolor="black", linewidth=0.6)
    for bar, value in zip(bars, top.bet):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{value:.6f}",
                ha="center", va="bottom", fontsize=7)
    ax.set_xticks(range(len(top)), [f"{n}\n({r})" for n, r in zip(top.node, top.region)], fontsize=8)
    ax.set_ylabel(r"Betweenness centrality (weighted, $\times10^{-4}$)")
    ax.grid(axis="y", alpha=0.3)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=NAVY, ec="black", label="Depot"),
                       plt.Rectangle((0, 0), 1, 1, color=BLUE, ec="black", label="Buying point")])
    return save(fig, out, "fig_4_2.png")


def fig_4_3(nodes: pd.DataFrame, sizes: dict, modularity: float, out: Path) -> Path:
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 4.5))
    farmers = nodes[nodes.kind == "farmer"]
    a.scatter(farmers.lon, farmers.lat, c=farmers.community, cmap="tab10", s=8, alpha=0.85)
    a.set(title="(a) Farmer communities (spatial)", xlabel="Longitude", ylabel="Latitude")
    a.grid(alpha=0.2)
    ordered = sorted(sizes.values(), reverse=True)
    b.bar(range(len(ordered)), ordered, color=BLUE, edgecolor="black", linewidth=0.6)
    b.set(title="(b) Cluster sizes", xlabel="Community (rank)", ylabel="Number of farmers")
    b.text(0.95, 0.92, f"modularity = {modularity:.4f}", transform=b.transAxes, ha="right",
           style="italic", color=NAVY, fontsize=9)
    b.grid(axis="y", alpha=0.3)
    return save(fig, out, "fig_4_3.png")


def fig_4_4(ml: pd.DataFrame, routing: dict, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(ml.route_cost, bins=32, color=PALE, edgecolor="black", linewidth=0.6)
    ax.axvline(routing["mean_route_cost"], color="#b22222", ls="--", label=f"mean = {routing['mean_route_cost']:.0f}")
    ax.axvline(routing["p90_route_cost"], color=NAVY, ls=":", lw=2, label=f"90th pct = {routing['p90_route_cost']:.0f}")
    ax.set(xlabel="Least-cost route cost to port (composite units)", ylabel="Number of farmers")
    ax.legend()
    ax.grid(axis="y", alpha=0.2)
    return save(fig, out, "fig_4_4.png")


def fig_4_5(tuned: dict, out: Path) -> Path:
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 4.5), gridspec_kw={"width_ratios": [1, 1.3]})
    models = [("Random Forest", tuned["random_forest"]), ("XGBoost", tuned["xgboost"])]
    x = np.arange(len(models))
    for offset, key, colour, label in ((-0.18, "base", PALE, "Base features"),
                                       (0.18, "net", TEAL, "Base + network")):
        vals = [m[key]["R2"] for _, m in models]
        bars = a.bar(x + offset, vals, 0.36, color=colour, edgecolor="black", linewidth=0.6, label=label)
        for bar, v in zip(bars, vals):
            a.text(bar.get_x() + bar.get_width() / 2, v + 0.01, f"{v:.3f}", ha="center", va="bottom", fontsize=8)
    a.set_xticks(x, [n for n, _ in models])
    a.set(ylim=(0, 1), ylabel="Held-out test R²", title="(a) Predictive accuracy for farm-gate price")
    a.legend(loc="lower right", fontsize=8)
    a.grid(axis="y", alpha=0.3)
    top = tuned["xgboost"]["feature_importance"][:8][::-1]
    b.barh([r["feature"] for r in top], [r["importance"] for r in top],
           color=[NAVY if r["feature"] in NETWORK_FEATURES else GREY for r in top], edgecolor="black", linewidth=0.6)
    b.tick_params(axis="y", labelsize=8)
    b.set(title="(b) Feature importance", xlabel="Tuned XGBoost feature importance")
    b.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=NAVY, ec="black", label="Network-derived"),
                      plt.Rectangle((0, 0), 1, 1, color=GREY, ec="black", label="Conventional")],
             loc="lower right", fontsize=8)
    b.grid(axis="x", alpha=0.3)
    return save(fig, out, "fig_4_5.png")


def fig_4_6(per_farm: np.ndarray, results: dict, out: Path) -> Path:
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 4.5))
    a.hist(per_farm, bins=30, color=PALE, edgecolor="black", linewidth=0.6)
    mean = results["simulation"]["mean_gain_pct"]
    a.axvline(mean, color="#b22222", ls="--", label=f"aggregate mean = {mean:.2f}%")
    a.set(title="(a) Distribution of revenue gains", xlabel="Expected revenue gain per farmer (%)",
          ylabel="Number of farmers")
    a.legend(fontsize=8)
    a.grid(axis="y", alpha=0.2)
    savings, premiums = [0.20, 0.35, 0.50], [0.15, 0.30, 0.45]
    grid = np.array([[next(r["mean_gain_pct"] for r in results["sensitivity"]
                           if round(r["consolidation"], 2) == s and round(r["premium"], 2) == p)
                      for p in premiums] for s in savings])
    im = b.imshow(grid, origin="lower", cmap="YlGnBu", aspect="auto")
    for i in range(3):
        for j in range(3):
            b.text(j, i, f"{grid[i, j]:.2f}", ha="center", va="center", fontsize=9,
                   color="white" if grid[i, j] > 9.5 else "#222")
    b.set_xticks(range(3), [f"{p:.2f}" for p in premiums])
    b.set_yticks(range(3), [f"{s:.0%}" for s in savings])
    b.set(title="(b) Sensitivity of mean gain (%)", xlabel="Bargaining premium (GHS/kg)", ylabel="Transport saving")
    fig.colorbar(im, ax=b)
    return save(fig, out, "fig_4_6.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=Path.cwd())
    parser.add_argument("--out-dir", type=Path, default=ROOT / "figures")
    args = parser.parse_args()
    data = ensure_intermediates(args.data_dir)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    results = json.loads((ROOT / "results.json").read_text())
    tuned = json.loads((ROOT / "tuned_results.json").read_text())
    nodes = pd.read_pickle(data / "nodes_df.pkl")
    ml = pd.read_pickle(data / "ml_df.pkl")
    bet = json.loads((data / "bet_c.json").read_text())
    sizes = json.loads((data / "cluster_sizes.json").read_text())
    per_farm = np.load(data / "per_farm_gain.npy")
    paths = [
        fig_4_1(nodes, args.out_dir),
        fig_4_2(nodes, bet, args.out_dir),
        fig_4_3(nodes, sizes, results["community"]["modularity"], args.out_dir),
        fig_4_4(ml, results["routing"], args.out_dir),
        fig_4_5(tuned, args.out_dir),
        fig_4_6(per_farm, results, args.out_dir),
    ]
    for p in paths:
        print(p)


if __name__ == "__main__":
    main()
