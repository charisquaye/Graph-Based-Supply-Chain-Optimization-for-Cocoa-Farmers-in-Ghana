"""
Hyperparameter tuning and held-out evaluation for the Chapter 4 price models.

Implements the procedure of Sections 3.7.3 and 4.7 of the thesis:
  * the analysis dataset is rebuilt exactly as in analysis_chapter4_pipeline.py
    (same code, same master seed 20250115), by executing that script up to the
    point where the feature matrix is defined;
  * a single 80/20 split (720 training / 180 test observations) on the seed;
  * exhaustive grid search with five-fold cross-validation (RMSE criterion)
    inside the training partition only, over the grids of Table 4.3 / Table C.1;
  * the selected configuration of each family is refitted on the training set
    with base features and with base + network features and evaluated once on
    the untouched test set; the tuned Random Forest is also used for the
    yield control target, and the feature importances of the tuned XGBoost
    model (base + network features) are recorded.

Results are written to tuned_results.json; results.json is not modified.
Run from the repository root, after analysis_chapter4_pipeline.py is present:
    python tune_models.py
"""
import json
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GridSearchCV, KFold, train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from xgboost import XGBRegressor

# 1. Rebuild the analysis dataset with the archived pipeline code.
#    Execution stops before the pipeline's own model evaluation, so nothing is
#    written to disk and the random-number stream is identical to the pipeline.
src = open("analysis_chapter4_pipeline.py", encoding="utf-8").read()
ns = {"__name__": "pipeline_data"}
exec(compile(src.split("def evaluate(")[0], "analysis_chapter4_pipeline.py", "exec"), ns)
df, base_feats, net_feats, SEED = ns["df"], ns["base_feats"], ns["net_feats"], ns["SEED"]
y = df["price"].values

# 2. One 80/20 split on the master seed.
idx_tr, idx_te = train_test_split(np.arange(len(df)), test_size=0.2, random_state=SEED)
cv = KFold(n_splits=5, shuffle=True, random_state=SEED)

# 3. Search grids (Table 4.3 / Table C.1).
RF_GRID = {"n_estimators": [300, 600], "max_depth": [None, 16],
           "min_samples_leaf": [1, 2], "max_features": ["sqrt", 1.0]}
XGB_GRID = {"n_estimators": [400, 800], "max_depth": [3, 5],
            "learning_rate": [0.03, 0.08], "subsample": [0.9], "colsample_bytree": [0.9]}
FAMILIES = {
    "random_forest": (lambda **p: RandomForestRegressor(random_state=SEED, n_jobs=-1, **p), RF_GRID),
    "xgboost": (lambda **p: XGBRegressor(random_state=SEED, n_jobs=-1, **p), XGB_GRID),
}

def scores(y_true, pred):
    return {"RMSE": round(float(np.sqrt(mean_squared_error(y_true, pred))), 4),
            "MAE": round(float(mean_absolute_error(y_true, pred)), 4),
            "R2": round(float(r2_score(y_true, pred)), 4)}

def fit_eval(make, params, feats, target):
    X = df[feats].values
    model = make(**params).fit(X[idx_tr], target[idx_tr])
    return scores(target[idx_te], model.predict(X[idx_te]))

out = {"seed": SEED, "n_train": int(len(idx_tr)), "n_test": int(len(idx_te))}
all_feats = base_feats + net_feats
for name, (make, grid) in FAMILIES.items():
    # tuning on the training partition, full (base + network) feature set
    gs = GridSearchCV(make(), grid, cv=cv, scoring="neg_root_mean_squared_error", n_jobs=1)
    gs.fit(df[all_feats].values[idx_tr], y[idx_tr])
    best = gs.best_params_
    out[name] = {
        "best_params": best,
        "cv_best_rmse": round(float(-gs.best_score_), 4),
        "n_combos": len(gs.cv_results_["params"]),
        "base": fit_eval(make, best, base_feats, y),
        "net": fit_eval(make, best, all_feats, y),
    }
    if name == "xgboost":  # importance ranking of the tuned model (Figure 4.5b)
        m = make(**best).fit(df[all_feats].values[idx_tr], y[idx_tr])
        out[name]["feature_importance"] = [
            {"feature": f, "importance": round(float(v), 4)}
            for f, v in sorted(zip(all_feats, m.feature_importances_), key=lambda t: -t[1])]

# 4. Yield control with the tuned Random Forest (expected yield removed from predictors).
yld = df["exp_yield"].values
ctrl = [c for c in base_feats if c != "exp_yield"]
rf_make, rf_best = FAMILIES["random_forest"][0], out["random_forest"]["best_params"]
out["yield_control"] = {
    "R2_base": fit_eval(rf_make, rf_best, ctrl, yld)["R2"],
    "R2_base_plus_network": fit_eval(rf_make, rf_best, ctrl + net_feats, yld)["R2"],
}

with open("tuned_results.json", "w") as fh:
    json.dump(out, fh, indent=2)
print(json.dumps(out, indent=2))
