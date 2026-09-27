"""Feature frames shared by the regression and anomaly models."""
from __future__ import annotations

import numpy as np
import pandas as pd

# §7.1 inputs: lĩnh vực, giá gói thầu, tỉnh, hình thức LCNT, nguồn vốn, thời gian thực hiện HĐ (+ thời điểm)
CATEGORICAL = ["linh_vuc", "tinh_thanh", "hinh_thuc_raw", "plan_type", "phuong_thuc"]
NUMERIC = ["log_gia_goi", "nam", "thang_trong_nam", "qua_mang", "thoi_gian_thuc_hien_hop_dong"]
TARGETS = {"tiet_kiem_pct": "% tiết kiệm", "log_gia_trung": "log(giá trúng thầu)"}


def regression_frame(df: pd.DataFrame, cfg) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Rows with a valid result; returns (frame, categorical cols, numeric cols) — columns that are
    entirely empty in this dataset (e.g. contract duration from the list API) are dropped."""
    low, high = cfg["clean"]["ratio_outlier_low"], cfg["clean"]["ratio_outlier_high"]
    d = df[df["ty_le_trung_thau"].between(low, high) & (df["gia_goi_thau"] > 0)].copy()
    d["log_gia_goi"] = np.log(d["gia_goi_thau"])
    d["log_gia_trung"] = np.log(d["gia_trung_thau"])
    d["thang_trong_nam"] = d["ngay_dang_tai"].dt.month
    d["qua_mang"] = pd.to_numeric(d["qua_mang"], errors="coerce")
    d["thoi_gian_thuc_hien_hop_dong"] = pd.to_numeric(d.get("thoi_gian_thuc_hien_hop_dong"), errors="coerce")
    if cfg["model"].get("use_bidder_count"):
        d["so_nha_thau"] = d["so_nha_thau_tham_du"]
    cats = [c for c in CATEGORICAL if c in d and d[c].notna().any()]
    nums = [c for c in NUMERIC + (["so_nha_thau"] if "so_nha_thau" in d else []) if c in d and d[c].notna().any()]
    for c in cats:
        d[c] = d[c].fillna("NA").astype(str)
    d = d.dropna(subset=["ngay_dang_tai"])
    return d.sort_values("ngay_dang_tai").reset_index(drop=True), cats, nums


def time_split(d: pd.DataFrame, test_months: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    cutoff = d["ngay_dang_tai"].max() - pd.DateOffset(months=test_months)
    return d[d["ngay_dang_tai"] <= cutoff], d[d["ngay_dang_tai"] > cutoff], cutoff


def anomaly_frame(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """Packages with a result + per-package competition signals (§FR-5 / §7.2)."""
    a = cfg["anomaly"]
    low, high = cfg["clean"]["ratio_outlier_low"], cfg["clean"]["ratio_outlier_high"]
    d = df[df["co_ket_qua"] & df["ty_le_trung_thau"].between(low, high)].copy()
    d["winner_key"] = d["ma_nha_thau_trung_thau"].fillna(d["nha_thau_trung_thau"])
    d["ngay_kq"] = d["ngay_dang_kqlcnt"].fillna(d["ngay_dang_tai"])
    d = d.dropna(subset=["winner_key", "ngay_kq", "ma_ben_moi_thau"])
    d["is_competitive"] = (d["hinh_thuc_nhom"] == "Cạnh tranh").astype(int)
    d["is_direct"] = (d["hinh_thuc_nhom"] == "Chỉ định thầu").astype(int)
    d["so_nha_thau"] = d["so_nha_thau_tham_du"].fillna(0)
    d["single_bidder"] = ((d["is_competitive"] == 1) & (d["so_nha_thau"] == 1)).astype(int)
    d["log_gia_goi"] = np.log(d["gia_goi_thau"])

    # wins by the same winner at the same solicitor within the trailing window (inclusive)
    d = d.sort_values(["ma_ben_moi_thau", "winner_key", "ngay_kq"]).reset_index(drop=True)
    d["_one"] = 1.0
    rolled = (d.groupby(["ma_ben_moi_thau", "winner_key"], sort=False)
                .rolling(f"{a['repeat_window_days']}D", on="ngay_kq")["_one"].sum())
    # rows are sorted by (group, date) and groupby(sort=False) keeps that order, so positions line up
    # (pandas 3 indexes the result by the `on` column, not the original row index)
    d["wins_in_window"] = rolled.to_numpy()
    d = d.drop(columns="_one")
    # winner's share of all results at this solicitor, and the solicitor's concentration (HHI)
    pair = d.groupby(["ma_ben_moi_thau", "winner_key"]).size()
    tot = d.groupby("ma_ben_moi_thau").size()
    share = (pair / tot.reindex(pair.index.get_level_values(0)).to_numpy()).rename("winner_share")
    hhi = (share ** 2).groupby(level=0).sum().rename("solicitor_hhi")
    d = d.join(share, on=["ma_ben_moi_thau", "winner_key"]).join(hhi, on="ma_ben_moi_thau")
    d["solicitor_n"] = d["ma_ben_moi_thau"].map(tot)
    d["repeat_winner"] = (d["wins_in_window"] >= a["repeat_min_wins"]).astype(int)
    return d
