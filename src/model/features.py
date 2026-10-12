"""Feature frames shared by the regression and anomaly models."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.clean.contractors import explode_winners

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
    d["ngay_kq"] = d["ngay_dang_kqlcnt"].fillna(d["ngay_dang_tai"])
    d = d.dropna(subset=["nha_thau_key", "ngay_kq", "ma_ben_moi_thau"])
    d = d.sort_values(["ma_ben_moi_thau", "nha_thau_key", "ngay_kq"]).reset_index(drop=True)
    d["is_competitive"] = (d["hinh_thuc_nhom"] == "Cạnh tranh").astype(int)
    d["is_direct"] = (d["hinh_thuc_nhom"] == "Chỉ định thầu").astype(int)
    d["so_nha_thau"] = d["so_nha_thau_tham_du"].fillna(0)
    d["single_bidder"] = ((d["is_competitive"] == 1) & (d["so_nha_thau"] == 1)).astype(int)
    d["log_gia_goi"] = np.log(d["gia_goi_thau"])

    # one row per (package, winner): a consortium member or the winner of one lot is credited with the win
    pair_keys = ["ma_ben_moi_thau", "nha_thau_key"]
    w = explode_winners(d)[pair_keys + ["ngay_kq"]]
    w["wins"] = trailing_count(w.groupby(pair_keys).ngroup(), w["ngay_kq"], a["repeat_window_days"])
    # winner's share of the solicitor's packages, and the solicitor's concentration (HHI over winning slots)
    pair = w.groupby(pair_keys).size()
    tot = d.groupby("ma_ben_moi_thau").size()
    w = w.join((pair / tot.reindex(pair.index.get_level_values(0)).to_numpy()).rename("share"), on=pair_keys)
    hhi = ((pair / pair.groupby(level=0).transform("sum")) ** 2).groupby(level=0).sum()
    # a package with several winners carries the signal of its most repeated / most dominant winner
    by_package = w.groupby(level=0)[["wins", "share"]].max()
    d["wins_in_window"] = by_package["wins"].astype(float)
    d["winner_share"] = by_package["share"]
    d["solicitor_hhi"] = d["ma_ben_moi_thau"].map(hhi)
    d["solicitor_n"] = d["ma_ben_moi_thau"].map(tot)
    d["repeat_winner"] = (d["wins_in_window"] >= a["repeat_min_wins"]).astype(int)
    return d


def trailing_count(group: pd.Series, when: pd.Series, days: int) -> np.ndarray:
    """For each row, the number of rows of the same group dated in (when - days, when], itself included.

    Rows are matched by their own (group, time) position on one sorted axis, so the result cannot be
    misaligned — groupby().rolling() returns groups in an order that need not be the frame's.
    """
    g = group.to_numpy(dtype="int64")
    t = when.to_numpy(dtype="datetime64[s]").astype("int64")
    if not len(t):
        return np.zeros(0, dtype="int64")
    window = days * 86_400
    t = t - t.min()
    pos = g * (t.max() + window + 1) + t   # groups occupy disjoint, increasing ranges at least a window apart
    order = np.argsort(pos, kind="stable")
    ps = pos[order]
    out = np.empty(len(ps), dtype="int64")
    out[order] = np.searchsorted(ps, ps, side="right") - np.searchsorted(ps, ps - window, side="right")
    return out
