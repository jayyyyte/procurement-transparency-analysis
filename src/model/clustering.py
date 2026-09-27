"""Optional §7.3: K-means segmentation of packages; k chosen by silhouette on a sample."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

FEATURES = ["log_gia_goi", "tiet_kiem_pct", "so_nha_thau", "is_direct", "is_competitive"]


def run(df: pd.DataFrame, cfg, logger) -> dict:
    seed = cfg["model"]["random_state"]
    d = df.dropna(subset=["tiet_kiem_pct"]).copy()
    d = d[d["gia_goi_thau"] > 0]
    if len(d) < cfg["model"]["min_rows"]:
        return {"skipped": True}
    d["log_gia_goi"] = np.log(d["gia_goi_thau"])
    d["so_nha_thau"] = d["so_nha_thau_tham_du"].fillna(0).clip(upper=15)
    d["is_direct"] = (d["hinh_thuc_nhom"] == "Chỉ định thầu").astype(int)
    d["is_competitive"] = (d["hinh_thuc_nhom"] == "Cạnh tranh").astype(int)
    X = StandardScaler().fit_transform(d[FEATURES])
    rng = np.random.default_rng(seed)
    sample = rng.choice(len(X), min(len(X), 10000), replace=False)
    sil = {}
    for k in range(3, 9):
        labels = KMeans(k, n_init=5, random_state=seed).fit_predict(X[sample])
        sil[k] = float(silhouette_score(X[sample], labels))
    best_k = max(sil, key=sil.get)
    d["cluster"] = KMeans(best_k, n_init=10, random_state=seed).fit_predict(X)
    profile = d.groupby("cluster").agg(
        so_goi=("ma_tbmt", "size"), gia_goi_trung_vi_ty=("gia_goi_thau", lambda s: s.median() / 1e9),
        tiet_kiem_trung_vi=("tiet_kiem_pct", "median"), so_nha_thau_tb=("so_nha_thau", "mean"),
        ty_le_chi_dinh=("is_direct", "mean"), linh_vuc_chinh=("linh_vuc", lambda s: s.mode().iat[0]))
    tables = cfg.path("tables_dir")
    profile.round(4).to_csv(tables / "kmeans_clusters.csv")
    pd.Series(sil, name="silhouette").to_csv(tables / "kmeans_silhouette.csv", index_label="k")
    logger.info("k-means: best k=%d (silhouette %.3f)", best_k, sil[best_k])
    return {"best_k": best_k, "silhouette": sil}
