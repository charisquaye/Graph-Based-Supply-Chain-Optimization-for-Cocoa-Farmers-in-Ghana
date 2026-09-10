"""
Implementation of the Chapter 3 methodology for the cocoa supply-chain study.
Produces the REAL, reproducible results reported in Chapter 4.

Pipeline:
  1. Synthetic data generation (seeded)
  2. Weighted, multi-relational directed graph construction
  3. Graph algorithms: centrality, Dijkstra routing, Louvain communities
  4. Machine learning: RF & XGBoost for farm-gate price, with/without network features
  5. Monte Carlo simulation: baseline vs optimised configuration -> revenue gains

All numeric outputs are written to results.json and figures to c4_fig_*.png
"""
import json, math, warnings
import numpy as np
import pandas as pd
import networkx as nx
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from xgboost import XGBRegressor

warnings.filterwarnings("ignore")
SEED = 20250115
rng = np.random.default_rng(SEED)
R = {}  # results collector

# ---------------------------------------------------------------------------
# 1. SYNTHETIC DATA GENERATION
# ---------------------------------------------------------------------------
REGIONS = {
    # region: (production share, centroid lon, lat, yield multiplier)
    "Ashanti":       (0.24, -1.50, 6.70, 1.00),
    "Western North": (0.28, -2.55, 6.20, 1.08),
    "Western South": (0.17, -2.10, 5.30, 1.03),
    "Eastern":       (0.15, -0.45, 6.30, 0.94),
    "Central":       (0.10, -1.05, 5.55, 0.90),
    "Volta":         (0.06,  0.45, 6.90, 0.85),
}
N_FARMERS = 900
N_BUYING = 45
N_DEPOTS = 10
PORTS = {"Tema": (0.02, 5.67), "Takoradi": (-1.75, 4.90)}

region_names = list(REGIONS.keys())
shares = np.array([REGIONS[r][0] for r in region_names])
shares = shares / shares.sum()
farmer_region = rng.choice(region_names, size=N_FARMERS, p=shares)

def jitter(c, s=0.35):
    return c + rng.normal(0, s)

farmers = []
for i in range(N_FARMERS):
    reg = farmer_region[i]
    _, clon, clat, ymul = REGIONS[reg]
    lon, lat = jitter(clon), jitter(clat)
    farm_size = float(np.clip(rng.gamma(2.2, 1.15), 0.4, 12.0))      # ~2-3 ha mean, right-skew
    input_intensity = float(np.clip(rng.normal(0.55, 0.16), 0.05, 1.0))
    # agronomic expected yield (kg/ha) independent of network position
    base_yield = 430 * ymul
    exp_yield = base_yield * (0.6 + 0.5 * input_intensity) * rng.normal(1.0, 0.10)
    exp_yield = float(np.clip(exp_yield, 120, 900))
    farmers.append(dict(node=f"F{i}", kind="farmer", region=reg, lon=lon, lat=lat,
                        farm_size=farm_size, input_intensity=input_intensity,
                        exp_yield=exp_yield))

# buying points placed near production mass
bp_region = rng.choice(region_names, size=N_BUYING, p=shares)
buying = []
for j in range(N_BUYING):
    reg = bp_region[j]
    _, clon, clat, _ = REGIONS[reg]
    lon, lat = jitter(clon, 0.5), jitter(clat, 0.5)
    capacity = float(np.clip(rng.normal(1.0, 0.3), 0.4, 2.0))
    buying.append(dict(node=f"B{j}", kind="buying", region=reg, lon=lon, lat=lat, capacity=capacity))

# depots
dep_region = rng.choice(region_names, size=N_DEPOTS, p=shares)
depots = []
for k in range(N_DEPOTS):
    reg = dep_region[k]
    _, clon, clat, _ = REGIONS[reg]
    lon, lat = jitter(clon, 0.6), jitter(clat, 0.6)
    depots.append(dict(node=f"D{k}", kind="depot", region=reg, lon=lon, lat=lat))

ports = [dict(node=n, kind="port", lon=c[0], lat=c[1]) for n, c in PORTS.items()]

def hav(a, b):
    # rough planar distance in km (equirectangular, fine for a country-scale extent)
    dx = (a[0] - b[0]) * 111.0 * math.cos(math.radians((a[1] + b[1]) / 2))
    dy = (a[1] - b[1]) * 111.0
    return math.hypot(dx, dy)

# road-quality factor per link (higher = worse road -> raises time & reliability cost)
def road_factor():
    return float(np.clip(rng.normal(1.0, 0.25), 0.6, 1.8))

# ---------------------------------------------------------------------------
# 2. GRAPH CONSTRUCTION (weighted, directed, multi-relational)
# ---------------------------------------------------------------------------
# composite weight: w = a*dist + b*tariff + c*time + d*(1-reliability)
A, Bc, Cc, Dc = 1.0, 0.8, 0.6, 25.0
TARIFF_PER_KM = 0.9

G = nx.DiGraph()
for rec in farmers + buying + depots + ports:
    G.add_node(rec["node"], **rec)

def edge_weight(u, v, rq):
    du = (G.nodes[u]["lon"], G.nodes[u]["lat"])
    dv = (G.nodes[v]["lon"], G.nodes[v]["lat"])
    dist = hav(du, dv)
    tariff = dist * TARIFF_PER_KM
    time_cost = dist * 0.12 * rq
    reliability = float(np.clip(1.05 - 0.30 * (rq - 0.6), 0.4, 1.0))
    w = A * dist + Bc * tariff + Cc * time_cost + Dc * (1 - reliability)
    return w, dist, reliability

bp_coords = {b["node"]: (b["lon"], b["lat"]) for b in buying}
dep_coords = {d["node"]: (d["lon"], d["lat"]) for d in depots}

# farmer -> buying point: distance-decay attachment, 1-3 links
for f in farmers:
    fp = (f["lon"], f["lat"])
    dists = sorted(((hav(fp, c), b) for b, c in bp_coords.items()))
    klink = rng.integers(1, 4)
    chosen = [b for _, b in dists[:klink + 2]]
    # probability weighted by inverse distance
    inv = np.array([1.0 / (hav(fp, bp_coords[b]) + 5) for b in chosen])
    inv = inv / inv.sum()
    picks = rng.choice(chosen, size=min(klink, len(chosen)), replace=False, p=inv)
    for b in np.atleast_1d(picks):
        w, dist, rel = edge_weight(f["node"], b, road_factor())
        G.add_edge(f["node"], b, rel="sells_to", weight=w, dist=dist, reliability=rel)

# buying -> depot: nearest 1-2 depots
for b in buying:
    bp = (b["lon"], b["lat"])
    dists = sorted(((hav(bp, c), d) for d, c in dep_coords.items()))
    for _, d in dists[:2]:
        w, dist, rel = edge_weight(b["node"], d, road_factor())
        G.add_edge(b["node"], d, rel="transports_to", weight=w, dist=dist, reliability=rel)

# depot -> nearest port
for d in depots:
    dp = (d["lon"], d["lat"])
    nearest = min(ports, key=lambda p: hav(dp, (p["lon"], p["lat"])))
    w, dist, rel = edge_weight(d["node"], nearest["node"], road_factor())
    G.add_edge(d["node"], nearest["node"], rel="evacuates_to", weight=w, dist=dist, reliability=rel)

R["network"] = {
    "n_nodes": G.number_of_nodes(),
    "n_edges": G.number_of_edges(),
    "n_farmers": N_FARMERS, "n_buying": N_BUYING, "n_depots": N_DEPOTS, "n_ports": len(ports),
    "avg_out_degree_farmer": round(np.mean([G.out_degree(f["node"]) for f in farmers]), 3),
    "density": round(nx.density(G), 5),
    "is_dag": nx.is_directed_acyclic_graph(G),
}

# ---------------------------------------------------------------------------
# 3. GRAPH ALGORITHMS
# ---------------------------------------------------------------------------
UG = G.to_undirected()
deg_c = nx.degree_centrality(G)
bet_c = nx.betweenness_centrality(G, weight="weight", normalized=True)
clo_c = nx.closeness_centrality(G, distance="weight")

# top intermediaries (buying points + depots) by betweenness
inter_nodes = [n for n in G.nodes if G.nodes[n]["kind"] in ("buying", "depot")]
top_bet = sorted(inter_nodes, key=lambda n: bet_c[n], reverse=True)[:8]
R["centrality_top"] = [
    {"node": n, "kind": G.nodes[n]["kind"], "region": G.nodes[n].get("region", ""),
     "betweenness": round(bet_c[n], 4), "degree": round(deg_c[n], 4)}
    for n in top_bet
]
R["centrality_summary"] = {
    "mean_betweenness_buying": round(np.mean([bet_c[n] for n in inter_nodes if G.nodes[n]["kind"] == "buying"]), 5),
    "mean_betweenness_depot": round(np.mean([bet_c[n] for n in inter_nodes if G.nodes[n]["kind"] == "depot"]), 5),
    "max_betweenness": round(max(bet_c.values()), 4),
}

# Louvain communities on undirected weighted graph (use inverse weight as similarity)
for u, v, dd in UG.edges(data=True):
    dd["sim"] = 1.0 / (dd["weight"] + 1.0)
communities = nx.community.louvain_communities(UG, weight="sim", seed=SEED, resolution=1.0)
mod = nx.community.modularity(UG, communities, weight="sim")
comm_of = {}
for ci, cset in enumerate(communities):
    for n in cset:
        comm_of[n] = ci
farmer_comm_sizes = {}
for ci, cset in enumerate(communities):
    fs = [n for n in cset if G.nodes[n]["kind"] == "farmer"]
    farmer_comm_sizes[ci] = len(fs)
sizes = sorted([s for s in farmer_comm_sizes.values() if s > 0], reverse=True)
R["community"] = {
    "n_communities": len(communities),
    "modularity": round(mod, 4),
    "n_farmer_clusters": len(sizes),
    "largest_cluster": sizes[0] if sizes else 0,
    "median_cluster": int(np.median(sizes)) if sizes else 0,
    "mean_cluster": round(float(np.mean(sizes)), 1) if sizes else 0,
}

# Dijkstra: least-cost path cost for each farmer to its port
farmer_route_cost = {}
for f in farmers:
    try:
        c = nx.shortest_path_length(G, f["node"], weight="weight")
        # cost to nearest reachable port
        pc = [c[p["node"]] for p in ports if p["node"] in c]
        farmer_route_cost[f["node"]] = min(pc) if pc else np.nan
    except Exception:
        farmer_route_cost[f["node"]] = np.nan
rc_vals = np.array([v for v in farmer_route_cost.values() if not np.isnan(v)])
R["routing"] = {
    "reachable_farmers": int(len(rc_vals)),
    "mean_route_cost": round(float(np.mean(rc_vals)), 2),
    "median_route_cost": round(float(np.median(rc_vals)), 2),
    "p90_route_cost": round(float(np.percentile(rc_vals, 90)), 2),
    "min_route_cost": round(float(np.min(rc_vals)), 2),
    "max_route_cost": round(float(np.max(rc_vals)), 2),
}

# ---------------------------------------------------------------------------
# 4. MACHINE LEARNING: farm-gate price per farmer
# ---------------------------------------------------------------------------
# Ground-truth generative model for realised farm-gate price (GHS/kg):
#   base national price - access penalty(route cost) + bargaining premium(community size & centrality) + noise
BASE_PRICE = 11.0
route_arr = np.array([farmer_route_cost[f["node"]] for f in farmers])
route_norm = (route_arr - np.nanmean(route_arr)) / np.nanstd(route_arr)
rows = []
for i, f in enumerate(farmers):
    n = f["node"]
    csize = farmer_comm_sizes.get(comm_of.get(n, -1), 1)
    access_penalty = 0.9 * max(route_norm[i], -2)          # farther -> lower price
    bargaining = 0.6 * math.tanh((csize - 25) / 25.0) + 4.0 * bet_c[n]
    price = BASE_PRICE - access_penalty + bargaining + rng.normal(0, 0.35)
    price = float(np.clip(price, 7.5, 13.5))
    rows.append(dict(
        node=n, region=f["region"], farm_size=f["farm_size"],
        input_intensity=f["input_intensity"], exp_yield=f["exp_yield"],
        lon=f["lon"], lat=f["lat"],
        degree=deg_c[n], betweenness=bet_c[n], closeness=clo_c[n],
        comm_size=csize, route_cost=farmer_route_cost[n],
        price=price))
df = pd.DataFrame(rows).dropna(subset=["route_cost"])

df = pd.get_dummies(df, columns=["region"], prefix="reg")
base_feats = ["farm_size", "input_intensity", "exp_yield", "lon", "lat"] + [c for c in df.columns if c.startswith("reg_")]
net_feats = ["degree", "betweenness", "closeness", "comm_size", "route_cost"]
y = df["price"].values

def evaluate(model_ctor, feats, name):
    X = df[feats].values
    kf = KFold(n_splits=5, shuffle=True, random_state=SEED)
    pred = cross_val_predict(model_ctor(), X, y, cv=kf)
    return {
        "model": name, "n_features": len(feats),
        "RMSE": round(float(np.sqrt(mean_squared_error(y, pred))), 4),
        "MAE": round(float(mean_absolute_error(y, pred)), 4),
        "R2": round(float(r2_score(y, pred)), 4),
    }

rf = lambda: RandomForestRegressor(n_estimators=400, max_depth=None, random_state=SEED, n_jobs=-1)
xgb = lambda: XGBRegressor(n_estimators=500, max_depth=4, learning_rate=0.05,
                           subsample=0.9, colsample_bytree=0.9, random_state=SEED, n_jobs=-1)

R["ml"] = {
    "target": "farm-gate price (GHS/kg)",
    "n_obs": int(len(df)),
    "results": [
        evaluate(rf, base_feats, "Random Forest (base features)"),
        evaluate(rf, base_feats + net_feats, "Random Forest (base + network)"),
        evaluate(xgb, base_feats, "XGBoost (base features)"),
        evaluate(xgb, base_feats + net_feats, "XGBoost (base + network)"),
    ],
}
# feature importance from full XGBoost
Xall = df[base_feats + net_feats].values
xgb_full = xgb().fit(Xall, y)
imp = xgb_full.feature_importances_
fi = sorted(zip(base_feats + net_feats, imp), key=lambda t: t[1], reverse=True)
R["feature_importance"] = [{"feature": f, "importance": round(float(v), 4)} for f, v in fi]

# yield model sanity check: network features should add little to an agronomic target
yld = df["exp_yield"].values
def eval_target(feats, target):
    X = df[feats].values
    kf = KFold(n_splits=5, shuffle=True, random_state=SEED)
    pred = cross_val_predict(rf(), X, target, cv=kf)
    return round(float(r2_score(target, pred)), 4)
R["yield_check"] = {
    "R2_base": eval_target([c for c in base_feats if c != "exp_yield"], yld),
    "R2_base_plus_network": eval_target([c for c in base_feats if c != "exp_yield"] + net_feats, yld),
}

# ---------------------------------------------------------------------------
# 5. MONTE CARLO SIMULATION: baseline vs optimised
# ---------------------------------------------------------------------------
# Baseline: farmer ships individually; transport cost per kg proportional to route cost.
# Optimised: within-community consolidation lowers per-kg transport cost (shared haulage)
#            and group bargaining adds a modest price premium, realised only for participants.
N_ITER = 5000
COST_PER_UNIT = 0.006          # GHS per kg per unit of composite route cost
CONSOLIDATION_SAVING = 0.35    # 35% transport-cost reduction when consolidated
BARGAIN_PREMIUM = 0.30         # GHS/kg group premium

fdf = df.copy()
route = fdf["route_cost"].values
size_ha = np.array([f["farm_size"] for f in farmers if f["node"] in set(fdf["node"])])
# align farm_size with fdf order
node_to_size = {f["node"]: f["farm_size"] for f in farmers}
size_ha = fdf["node"].map(node_to_size).values
base_price_arr = fdf["price"].values
comm_size_arr = fdf["comm_size"].values

gains_pct = []
mean_base_rev = []
mean_opt_rev = []
for _ in range(N_ITER):
    yield_draw = np.clip(fdf["exp_yield"].values * rng.normal(1.0, 0.12, len(fdf)), 100, None)
    price_draw = np.clip(base_price_arr * rng.normal(1.0, 0.05, len(fdf)), 6, None)
    output = yield_draw * size_ha  # kg
    transport_cost = route * COST_PER_UNIT
    base_rev = output * (price_draw - transport_cost)
    # participation: higher in larger communities
    part_prob = np.clip(0.35 + 0.010 * (comm_size_arr - 10), 0.2, 0.9)
    participate = rng.random(len(fdf)) < part_prob
    opt_transport = np.where(participate, transport_cost * (1 - CONSOLIDATION_SAVING), transport_cost)
    opt_price = np.where(participate, price_draw + BARGAIN_PREMIUM, price_draw)
    opt_rev = output * (opt_price - opt_transport)
    gp = (opt_rev.sum() - base_rev.sum()) / base_rev.sum() * 100
    gains_pct.append(gp)
    mean_base_rev.append(base_rev.mean())
    mean_opt_rev.append(opt_rev.mean())

gains_pct = np.array(gains_pct)
R["simulation"] = {
    "n_iterations": N_ITER,
    "mean_gain_pct": round(float(np.mean(gains_pct)), 2),
    "median_gain_pct": round(float(np.median(gains_pct)), 2),
    "sd_gain_pct": round(float(np.std(gains_pct)), 2),
    "ci95_low": round(float(np.percentile(gains_pct, 2.5)), 2),
    "ci95_high": round(float(np.percentile(gains_pct, 97.5)), 2),
    "p10": round(float(np.percentile(gains_pct, 10)), 2),
    "p90": round(float(np.percentile(gains_pct, 90)), 2),
    "mean_base_rev": round(float(np.mean(mean_base_rev)), 2),
    "mean_opt_rev": round(float(np.mean(mean_opt_rev)), 2),
}

# sensitivity: vary consolidation saving and bargain premium
sens = []
for cs in [0.20, 0.35, 0.50]:
    for bp in [0.15, 0.30, 0.45]:
        gg = []
        for _ in range(800):
            yield_draw = np.clip(fdf["exp_yield"].values * rng.normal(1.0, 0.12, len(fdf)), 100, None)
            price_draw = np.clip(base_price_arr * rng.normal(1.0, 0.05, len(fdf)), 6, None)
            output = yield_draw * size_ha
            transport_cost = route * COST_PER_UNIT
            base_rev = output * (price_draw - transport_cost)
            part_prob = np.clip(0.35 + 0.010 * (comm_size_arr - 10), 0.2, 0.9)
            participate = rng.random(len(fdf)) < part_prob
            opt_transport = np.where(participate, transport_cost * (1 - cs), transport_cost)
            opt_price = np.where(participate, price_draw + bp, price_draw)
            opt_rev = output * (opt_price - opt_transport)
            gg.append((opt_rev.sum() - base_rev.sum()) / base_rev.sum() * 100)
        sens.append({"consolidation": cs, "premium": bp, "mean_gain_pct": round(float(np.mean(gg)), 2)})
R["sensitivity"] = sens
R["params"] = {"seed": SEED, "A": A, "B": Bc, "C": Cc, "D": Dc, "tariff_per_km": TARIFF_PER_KM,
               "cost_per_unit": COST_PER_UNIT, "consolidation_saving": CONSOLIDATION_SAVING,
               "bargain_premium": BARGAIN_PREMIUM}

# save everything needed for figures
np.save("gains_pct.npy", gains_pct)
df.to_pickle("ml_df.pkl")

# per-farmer expected revenue gain (%) averaged over a batch of iterations, for histogram
per_farm_gain = np.zeros(len(fdf))
BATCH = 400
for _ in range(BATCH):
    yield_draw = np.clip(fdf["exp_yield"].values * rng.normal(1.0, 0.12, len(fdf)), 100, None)
    price_draw = np.clip(base_price_arr * rng.normal(1.0, 0.05, len(fdf)), 6, None)
    output = yield_draw * size_ha
    transport_cost = route * COST_PER_UNIT
    base_rev = output * (price_draw - transport_cost)
    part_prob = np.clip(0.35 + 0.010 * (comm_size_arr - 10), 0.2, 0.9)
    participate = rng.random(len(fdf)) < part_prob
    opt_transport = np.where(participate, transport_cost * (1 - CONSOLIDATION_SAVING), transport_cost)
    opt_price = np.where(participate, price_draw + BARGAIN_PREMIUM, price_draw)
    opt_rev = output * (opt_price - opt_transport)
    per_farm_gain += (opt_rev - base_rev) / base_rev * 100
per_farm_gain /= BATCH
np.save("per_farm_gain.npy", per_farm_gain)

# nodes frame for spatial plots
node_rows = []
for n in G.nodes:
    nd = G.nodes[n]
    node_rows.append(dict(node=n, kind=nd["kind"], region=nd.get("region", ""),
                          lon=nd["lon"], lat=nd["lat"],
                          community=comm_of.get(n, -1), betweenness=bet_c[n]))
pd.DataFrame(node_rows).to_pickle("nodes_df.pkl")
# farmer community id aligned to df order
df_comm = df["node"].map(lambda n: comm_of.get(n, -1)).values
np.save("df_comm.npy", df_comm)
# cluster sizes (farmers per community)
json.dump({str(k): v for k, v in farmer_comm_sizes.items()}, open("cluster_sizes.json", "w"))

with open("bet_c.json", "w") as fh:
    json.dump({n: bet_c[n] for n in G.nodes}, fh)
with open("results.json", "w") as fh:
    json.dump(R, fh, indent=2)

print("DONE. mean gain %.2f%%  price R2 base->net RF %.3f->%.3f"
      % (R["simulation"]["mean_gain_pct"], R["ml"]["results"][0]["R2"], R["ml"]["results"][1]["R2"]))
