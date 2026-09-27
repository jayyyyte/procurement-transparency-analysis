"""Bài toán 1 (§7.1): predict % savings (or log winning price) and compare algorithms side by side.

Models: Median (reference) · Linear Regression (baseline) · Random Forest (main) · LightGBM (advanced;
falls back to scikit-learn HistGradientBoosting if lightgbm is not installed).
Evaluation: time-based hold-out (last `test_months` months) + K-fold CV on the training period.
"""
from __future__ import annotations

import json
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.dummy import DummyRegressor  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.inspection import permutation_importance  # noqa: E402
from sklearn.linear_model import LinearRegression  # noqa: E402
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score  # noqa: E402
from sklearn.model_selection import KFold, cross_validate  # noqa: E402
from sklearn.pipeline import Pipeline, make_pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # noqa: E402

from src.eda.plots import SERIES, SURFACE, TEXT_2  # noqa: E402  (also applies the shared rcParams)
from src.model.features import TARGETS, regression_frame, time_split  # noqa: E402

try:
    from lightgbm import LGBMRegressor
except ImportError:  # optional dependency
    LGBMRegressor = None


def _preprocessor(cats: list[str], nums: list[str], scale: bool) -> ColumnTransformer:
    num_steps = [SimpleImputer(strategy="median")] + ([StandardScaler()] if scale else [])
    return ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=20, sparse_output=False), cats),
        ("num", make_pipeline(*num_steps), nums),
    ])


def build_models(cats: list[str], nums: list[str], seed: int) -> dict[str, Pipeline]:
    models = {
        "Median (tham chiếu)": Pipeline([("prep", _preprocessor(cats, nums, False)),
                                          ("m", DummyRegressor(strategy="median"))]),
        "Linear Regression": Pipeline([("prep", _preprocessor(cats, nums, True)), ("m", LinearRegression())]),
        "Random Forest": Pipeline([("prep", _preprocessor(cats, nums, False)),
                                   ("m", RandomForestRegressor(n_estimators=300, min_samples_leaf=5, max_features=0.5,
                                                               n_jobs=-1, random_state=seed))]),
    }
    if LGBMRegressor is not None:
        models["LightGBM"] = Pipeline([("prep", _preprocessor(cats, nums, False)),
                                       ("m", LGBMRegressor(n_estimators=600, learning_rate=0.03, num_leaves=31,
                                                           min_child_samples=30, subsample=0.8, subsample_freq=1,
                                                           colsample_bytree=0.8, random_state=seed, verbose=-1))])
    else:
        models["HistGradientBoosting"] = Pipeline([("prep", _preprocessor(cats, nums, False)),
                                                   ("m", HistGradientBoostingRegressor(max_iter=500, learning_rate=0.05,
                                                                                      random_state=seed))])
    return models


def _metrics(y, p) -> dict[str, float]:
    return {"RMSE": float(np.sqrt(mean_squared_error(y, p))), "MAE": float(mean_absolute_error(y, p)),
            "R2": float(r2_score(y, p))}


def _grouped_importance(pipe: Pipeline, cats: list[str], nums: list[str]) -> pd.Series | None:
    """Impurity/split importance summed back from one-hot columns to the original feature."""
    model = pipe.named_steps["m"]
    if not hasattr(model, "feature_importances_"):
        return None
    names = pipe.named_steps["prep"].get_feature_names_out()
    imp = pd.Series(model.feature_importances_, index=names, dtype=float)
    orig = []
    for n in names:
        kind, rest = n.split("__", 1)
        orig.append(next((c for c in cats if rest.startswith(c + "_")), rest) if kind == "cat" else rest)
    s = imp.groupby(orig).sum()
    return s / s.sum()


def run(df: pd.DataFrame, cfg, logger) -> dict:
    mc = cfg["model"]
    seed = mc["random_state"]
    target = mc.get("target", "tiet_kiem_pct")
    d, cats, nums = regression_frame(df, cfg)
    if len(d) < mc["min_rows"]:
        logger.warning("regression skipped: only %d usable rows (< min_rows=%d)", len(d), mc["min_rows"])
        return {"skipped": True, "rows": len(d)}
    if mc.get("max_train_rows") and len(d) > mc["max_train_rows"]:
        d = d.sample(mc["max_train_rows"], random_state=seed).sort_values("ngay_dang_tai")
    train, test, cutoff = time_split(d, mc["test_months"])
    X_cols = cats + nums
    logger.info("regression target=%s rows=%d train=%d test=%d (test after %s) features=%s",
                target, len(d), len(train), len(test), cutoff.date(), X_cols)

    rows, fitted = [], {}
    for name, pipe in build_models(cats, nums, seed).items():
        t0 = time.time()
        cv = cross_validate(pipe, train[X_cols], train[target],
                            cv=KFold(mc["cv_folds"], shuffle=True, random_state=seed),
                            scoring=("neg_root_mean_squared_error", "r2"), n_jobs=1)
        pipe.fit(train[X_cols], train[target])
        pred = pipe.predict(test[X_cols])
        m = _metrics(test[target], pred)
        rows.append({"model": name, "test_RMSE": m["RMSE"], "test_MAE": m["MAE"], "test_R2": m["R2"],
                     "cv_RMSE_mean": -cv["test_neg_root_mean_squared_error"].mean(),
                     "cv_RMSE_std": cv["test_neg_root_mean_squared_error"].std(),
                     "cv_R2_mean": cv["test_r2"].mean(), "fit_seconds": round(time.time() - t0, 1)})
        fitted[name] = (pipe, pred)
        logger.info("%-22s test RMSE=%.4f MAE=%.4f R2=%.3f | cv R2=%.3f", name, m["RMSE"], m["MAE"], m["R2"],
                    cv["test_r2"].mean())
    comp = pd.DataFrame(rows)
    best = comp[~comp["model"].str.startswith("Median")].sort_values("test_RMSE").iloc[0]["model"]

    # feature importance: model-based (RF + GBM) and permutation on the test period (best model)
    imp = {n: _grouped_importance(p, cats, nums) for n, (p, _) in fitted.items()}
    imp = pd.DataFrame({n: s for n, s in imp.items() if s is not None})
    sample = test.sample(min(len(test), 5000), random_state=seed)
    perm = permutation_importance(fitted[best][0], sample[X_cols], sample[target], n_repeats=5,
                                  random_state=seed, scoring="neg_root_mean_squared_error")
    imp[f"permutation ({best})"] = pd.Series(perm.importances_mean, index=X_cols)

    tables, figs = cfg.path("tables_dir"), cfg.path("figures_dir")
    tables.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)
    comp.round(5).to_csv(tables / "regression_comparison.csv", index=False)
    imp.sort_values(imp.columns[0], ascending=False).round(5).to_csv(tables / "feature_importance.csv")
    summary = {"target": target, "target_label": TARGETS.get(target, target), "rows": len(d),
               "train_rows": len(train), "test_rows": len(test), "test_after": str(cutoff.date()),
               "features": X_cols, "best_model": best, "comparison": comp.round(5).to_dict("records")}
    (tables / "regression_metrics.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    _plot_comparison(comp, figs / "fig09_so_sanh_regression.png", summary)
    _plot_importance(imp, figs / "fig10_feature_importance.png")
    _plot_pred(test[target].to_numpy(), fitted[best][1], best, figs / "fig11_du_doan_vs_thuc_te.png", summary)
    return summary


def _plot_comparison(comp: pd.DataFrame, path, s) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
    for ax, col, label in zip(axes, ["test_RMSE", "test_MAE", "test_R2"], ["RMSE (thấp hơn tốt hơn)",
                                                                          "MAE (thấp hơn tốt hơn)",
                                                                          "R² (cao hơn tốt hơn)"]):
        c = comp.iloc[::-1]
        ax.barh(c["model"], c[col], color=SERIES[0], height=0.6, edgecolor=SURFACE, linewidth=2)
        for i, v in enumerate(c[col]):
            ax.text(max(v, 0), i, f" {v:.4f}" if "R2" not in col else f" {v:.3f}", va="center", fontsize=8, color=TEXT_2)
        ax.set_title(label)
        ax.grid(axis="y", visible=False)
        ax.margins(x=0.25)
    fig.suptitle(f"So sánh mô hình dự đoán {s['target_label']} — tập test {s['test_rows']:,} gói (sau {s['test_after']})",
                 x=0.01, ha="left", weight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_importance(imp: pd.DataFrame, path) -> None:
    cols = [c for c in imp.columns if not c.startswith("Linear")]
    fig, axes = plt.subplots(1, len(cols), figsize=(4.2 * len(cols), 3.8))
    for ax, col, color in zip(np.atleast_1d(axes), cols, SERIES):
        s = imp[col].dropna().sort_values()
        ax.barh(s.index, s.values, color=color, height=0.6, edgecolor=SURFACE, linewidth=2)
        ax.set_title(col, fontsize=10)
        ax.grid(axis="y", visible=False)
    fig.suptitle("Mức độ ảnh hưởng của đặc trưng", x=0.01, ha="left", weight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_pred(y, p, name, path, s) -> None:
    fig, ax = plt.subplots(figsize=(5.5, 5))
    idx = np.random.default_rng(0).choice(len(y), min(len(y), 4000), replace=False)
    ax.scatter(y[idx], p[idx], s=8, alpha=0.35, color=SERIES[0], linewidths=0)
    lo, hi = np.percentile(np.r_[y, p], [0.5, 99.5])
    ax.plot([lo, hi], [lo, hi], color=TEXT_2, linewidth=1, linestyle="--")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel(f"Thực tế — {s['target_label']}")
    ax.set_ylabel("Dự đoán")
    ax.set_title(f"{name}: dự đoán vs thực tế (tập test)")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
