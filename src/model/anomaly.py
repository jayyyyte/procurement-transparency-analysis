"""Bài toán 2 (§7.2): statistical anomaly scores for competition signals — no ground truth.

Methods: Rule-based composite (baseline) · Isolation Forest (main) · Local Outlier Factor (comparison).
Evaluation without labels = agreement: pairwise Jaccard of flagged sets, Spearman correlation of scores,
and how many methods flag each package. Results are "điểm bất thường thống kê", never a finding of fraud.
"""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import IsolationForest  # noqa: E402
from sklearn.neighbors import LocalOutlierFactor  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from src.eda.plots import SERIES, SURFACE, TEXT_2  # noqa: E402
from src.model.features import anomaly_frame  # noqa: E402

ML_FEATURES = ["ty_le_trung_thau", "log_gia_goi", "so_nha_thau", "is_competitive", "is_direct", "single_bidder",
               "log_wins_in_window", "winner_share", "solicitor_hhi"]
METHODS = ["rule", "iforest", "lof"]
METHOD_LABEL = {"rule": "Rule-based", "iforest": "Isolation Forest", "lof": "LOF"}
DISCLAIMER = ("Điểm bất thường thống kê — chỉ ra gói thầu có các tín hiệu cạnh tranh khác thường so với phần còn lại "
              "của dữ liệu; KHÔNG phải kết luận vi phạm hay gian lận.")


def rule_score(d: pd.DataFrame, cfg) -> pd.Series:
    a = cfg["anomaly"]
    w = a["weights"]
    near_full = ((d["ty_le_trung_thau"] - 0.95) / (a["near_full_ratio"] - 0.95)).clip(0, 1)
    repeat = (d["wins_in_window"] / (2 * a["repeat_min_wins"])).clip(0, 1)
    return w["single_bidder"] * d["single_bidder"] + w["near_full_price"] * near_full + w["repeat_winner"] * repeat


def explain(r: pd.Series, cfg) -> str:
    a = cfg["anomaly"]
    parts = []
    if r["single_bidder"]:
        parts.append("chỉ 1 nhà thầu tham dự dù hình thức cạnh tranh")
    if r["ty_le_trung_thau"] >= a["near_full_ratio"]:
        parts.append(f"giá trúng = {r['ty_le_trung_thau']:.2%} giá gói thầu")
    if r["wins_in_window"] >= a["repeat_min_wins"]:
        parts.append(f"nhà thầu thắng {int(r['wins_in_window'])} gói tại cùng bên mời thầu trong {a['repeat_window_days']} ngày")
    if r["winner_share"] >= 0.5 and r["solicitor_n"] >= 5:
        parts.append(f"nhà thầu chiếm {r['winner_share']:.0%} số gói của bên mời thầu ({int(r['solicitor_n'])} gói)")
    if r["is_direct"]:
        parts.append("chỉ định thầu")
    return "; ".join(parts) or "tổ hợp đặc trưng hiếm (không có tín hiệu quy tắc nổi bật)"


def run(df: pd.DataFrame, cfg, logger) -> dict:
    a = cfg["anomaly"]
    seed = cfg["model"]["random_state"]
    d = anomaly_frame(df, cfg)
    if len(d) < cfg["model"]["min_rows"]:
        logger.warning("anomaly scoring skipped: only %d packages with results", len(d))
        return {"skipped": True, "rows": len(d)}
    d["log_wins_in_window"] = np.log1p(d["wins_in_window"])
    X = StandardScaler().fit_transform(d[ML_FEATURES].fillna(0).to_numpy())

    d["score_rule"] = rule_score(d, cfg)
    iso = IsolationForest(n_estimators=300, contamination=a["contamination"], random_state=seed, n_jobs=-1).fit(X)
    d["score_iforest"] = -iso.score_samples(X)
    # small jitter so exact duplicates (common in categorical-heavy data) do not break LOF densities
    Xj = X + np.random.default_rng(seed).normal(0, 1e-6, X.shape)
    if len(d) > a["lof_max_rows"]:
        idx = np.random.default_rng(seed).choice(len(d), a["lof_max_rows"], replace=False)
        lof = LocalOutlierFactor(n_neighbors=a["lof_neighbors"], novelty=True).fit(Xj[idx])
        d["score_lof"] = -lof.score_samples(Xj)
    else:
        lof = LocalOutlierFactor(n_neighbors=a["lof_neighbors"]).fit(Xj)
        d["score_lof"] = -lof.negative_outlier_factor_

    # each method flags its top `contamination` share; agreement across methods is the evaluation
    k = max(1, int(round(a["contamination"] * len(d))))
    for m in METHODS:
        d[f"rank_{m}"] = d[f"score_{m}"].rank(ascending=False, method="first")
        d[f"flag_{m}"] = d[f"rank_{m}"] <= k
        d[f"pct_{m}"] = d[f"score_{m}"].rank(pct=True)
    d["n_methods_flagged"] = d[[f"flag_{m}" for m in METHODS]].sum(axis=1)
    d["mean_percentile"] = d[[f"pct_{m}" for m in METHODS]].mean(axis=1)

    agree_rows = []
    for i, m1 in enumerate(METHODS):
        for m2 in METHODS[i + 1:]:
            s1, s2 = set(d.index[d[f"flag_{m1}"]]), set(d.index[d[f"flag_{m2}"]])
            agree_rows.append({"cap": f"{METHOD_LABEL[m1]} ↔ {METHOD_LABEL[m2]}",
                               "jaccard_flagged": len(s1 & s2) / len(s1 | s2),
                               "spearman_score": d[f"score_{m1}"].corr(d[f"score_{m2}"], method="spearman")})
    agree = pd.DataFrame(agree_rows)
    consensus = d["n_methods_flagged"].value_counts().reindex([0, 1, 2, 3], fill_value=0)
    signal_rate = {m: {s: float(d.loc[d[f"flag_{m}"], s].mean()) for s in ("single_bidder", "repeat_winner", "is_direct")}
                   | {"median_ty_le": float(d.loc[d[f"flag_{m}"], "ty_le_trung_thau"].median())} for m in METHODS}
    signal_rate["tất cả gói"] = {s: float(d[s].mean()) for s in ("single_bidder", "repeat_winner", "is_direct")} | \
                                {"median_ty_le": float(d["ty_le_trung_thau"].median())}

    top = d.sort_values(["n_methods_flagged", "mean_percentile"], ascending=False).head(a["top_k"]).copy()
    top["giai_thich_tin_hieu"] = top.apply(explain, axis=1, cfg=cfg)
    cols = ["ma_tbmt", "ten_goi_thau", "ben_moi_thau", "nha_thau_trung_thau", "tinh_thanh", "hinh_thuc_lua_chon_nha_thau",
            "gia_goi_thau", "gia_trung_thau", "ty_le_trung_thau", "so_nha_thau_tham_du", "wins_in_window",
            "score_rule", "score_iforest", "score_lof", "n_methods_flagged", "giai_thich_tin_hieu"]

    tables, figs = cfg.path("tables_dir"), cfg.path("figures_dir")
    tables.mkdir(parents=True, exist_ok=True)
    top[cols].round(4).to_csv(tables / "anomaly_top.csv", index=False, encoding="utf-8-sig")
    agree.round(4).to_csv(tables / "anomaly_agreement.csv", index=False)
    d[["ma_tbmt", "score_rule", "score_iforest", "score_lof", "n_methods_flagged"]].to_parquet(
        cfg.path("processed_dir") / "anomaly_scores.parquet", index=False)
    summary = {"rows": len(d), "k_flagged_per_method": k, "contamination": a["contamination"],
               "consensus_counts": {int(i): int(v) for i, v in consensus.items()},
               "agreement": agree.round(4).to_dict("records"), "signal_rate_in_flagged": signal_rate,
               "disclaimer": DISCLAIMER}
    (tables / "anomaly_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(consensus, agree, signal_rate, figs / "fig12_anomaly_dong_thuan.png", k)
    logger.info("anomaly: %d packages, k=%d per method, consensus(3/3)=%d, jaccard=%s", len(d), k, consensus[3],
                agree["jaccard_flagged"].round(2).tolist())
    return summary


def _plot(consensus: pd.Series, agree: pd.DataFrame, rates: dict, path, k: int) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.8))
    c = consensus.loc[[1, 2, 3]]
    axes[0].bar([f"{i}/3" for i in c.index], c.values, color=SERIES[0], width=0.6, edgecolor=SURFACE, linewidth=2)
    for i, v in enumerate(c.values):
        axes[0].text(i, v, f"{v:,}", ha="center", va="bottom", fontsize=8, color=TEXT_2)
    axes[0].set_title("Số gói bị gắn cờ theo số thuật toán đồng thuận")
    axes[0].grid(axis="x", visible=False)
    ag = agree.iloc[::-1]
    axes[1].barh(ag["cap"], ag["jaccard_flagged"], color=SERIES[0], height=0.55, edgecolor=SURFACE, linewidth=2)
    for i, (j, r) in enumerate(zip(ag["jaccard_flagged"], ag["spearman_score"])):
        axes[1].text(j, i, f" J={j:.2f} · ρ={r:.2f}", va="center", fontsize=8, color=TEXT_2)
    axes[1].set_xlim(0, 1)
    axes[1].set_title(f"Độ trùng nhóm top-{k:,} (Jaccard) và tương quan điểm (ρ)")
    axes[1].grid(axis="y", visible=False)
    groups = list(rates)
    x = np.arange(len(groups))
    width = 0.26
    for j, (sig, label) in enumerate([("single_bidder", "1 nhà thầu (cạnh tranh)"), ("repeat_winner", "thắng lặp lại"),
                                      ("is_direct", "chỉ định thầu")]):
        axes[2].bar(x + (j - 1) * width, [rates[g][sig] for g in groups], width, color=SERIES[j], label=label,
                    edgecolor=SURFACE, linewidth=1.5)
    axes[2].set_xticks(x, [METHOD_LABEL.get(g, g) for g in groups], fontsize=8)
    axes[2].yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    axes[2].set_title("Tỷ lệ tín hiệu trong nhóm bị gắn cờ")
    axes[2].legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3)
    axes[2].grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
