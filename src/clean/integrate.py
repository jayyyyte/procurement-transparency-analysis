"""Integrate notices (TBMT + KQLCNT) with plans (KHLCNT) -> data/processed/packages.parquet."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.clean.dedupe import dedupe_notices, dedupe_plans
from src.clean.normalize import (HINH_THUC, LINH_VUC, PLAN_TYPE, ProvinceMapper, hinh_thuc_nhom,
                                 parse_money, to_datetime)

DATE_COLS = ["thoi_diem_dong_thau", "thoi_diem_mo_thau", "ngay_dang_tai", "ngay_dang_kqlcnt", "ngay_quyet_dinh"]


def _normalise_notices(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in DATE_COLS:
        df[c] = to_datetime(df[c])
    for c in ("gia_goi_thau", "gia_trung_thau"):
        df[c] = df[c].map(parse_money)
    for c in ("so_nha_thau_tham_du", "so_nha_thau_dat_kt", "so_kien_nghi", "case_khkq"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def integrate(interim: dict[str, pd.DataFrame], cfg, logger) -> tuple[pd.DataFrame, dict]:
    stats: dict = {}
    notices = _normalise_notices(interim["notices"])
    stats["notices_raw"] = len(notices)
    notices, stats["notices_dup_removed"] = dedupe_notices(notices)
    plans, stats["plans_dup_removed"] = dedupe_plans(interim["plans"])
    stats["plans"] = len(plans)

    # ---- join KHLCNT on plan number (present on every notice in Phase 0 samples) ----
    plan_cols = ["ma_khlcnt", "ten_du_an", "chu_dau_tu", "tinh_thanh_raw", "plan_type", "tong_muc_dau_tu"]
    p = plans[[c for c in plan_cols if c in plans]].rename(columns=lambda c: c if c == "ma_khlcnt" else f"{c}_kh")
    df = notices.merge(p, on="ma_khlcnt", how="left")
    matched = df["ten_du_an_kh"].notna() if "ten_du_an_kh" in df else pd.Series(False, index=df.index)
    df["join_method"] = np.where(matched, "ma_khlcnt", "none")
    df["ten_du_an"] = df.get("ten_du_an_kh")
    df["chu_dau_tu"] = df["chu_dau_tu"].fillna(df.get("chu_dau_tu_kh"))
    # KQLCNT published with the plan (caseKHKQ=1) has no location: take it from the plan
    df["tinh_thanh_raw"] = df["tinh_thanh_raw"].fillna(df.get("tinh_thanh_raw_kh"))
    df["plan_type"] = df["plan_type"].fillna(df.get("plan_type_kh"))
    df = df.drop(columns=[c for c in df.columns if c.endswith("_kh") and c != "tong_muc_dau_tu_kh"])
    stats["join_rate"] = round(float(matched.mean()), 4) if len(df) else 0.0

    # ---- provinces: keep 63-level (at publication) and 34-level (after 07/2025 merger) ----
    mapper = ProvinceMapper(cfg.path("province_mapping"))
    mapped = [mapper.map(n, d) for n, d in zip(df["tinh_thanh_raw"], df["ngay_dang_tai"])]
    df["tinh_thanh_63"] = [m[0] for m in mapped]
    df["tinh_thanh_34"] = [m[1] for m in mapped]
    unmapped = df.loc[df["tinh_thanh_raw"].notna() & df["tinh_thanh_34"].isna(), "tinh_thanh_raw"]
    stats["province_unmapped"] = unmapped.value_counts().head(10).to_dict()
    df["tinh_thanh"] = df["tinh_thanh_34"]

    # ---- labels ----
    df["linh_vuc"] = df["linh_vuc_raw"].map(LINH_VUC).fillna(df["linh_vuc_raw"])
    df["hinh_thuc_lua_chon_nha_thau"] = df["hinh_thuc_raw"].map(HINH_THUC).fillna(df["hinh_thuc_raw"])
    df["hinh_thuc_nhom"] = df["hinh_thuc_raw"].map(hinh_thuc_nhom)
    df["nguon_von"] = df["plan_type"].map(PLAN_TYPE).fillna(df["plan_type"])

    # ---- state-budget filter (proxy on planType until a capital-source field is available) ----
    keep_types = set(cfg["clean"]["nsnn_plan_types"])
    is_nsnn = df["plan_type"].isin(keep_types)
    stats["non_nsnn_removed"] = int((~is_nsnn).sum())
    stats["non_nsnn_by_type"] = df.loc[~is_nsnn, "plan_type"].fillna("NA").value_counts().to_dict()
    df = df[is_nsnn].copy()

    # ---- derived fields ----
    df["ty_le_trung_thau"] = df["gia_trung_thau"] / df["gia_goi_thau"].where(df["gia_goi_thau"] > 0)
    df["tiet_kiem_pct"] = 1 - df["ty_le_trung_thau"]
    df["co_ket_qua"] = df["gia_trung_thau"].notna()
    t = df["ngay_dang_tai"]
    df["nam"], df["quy"], df["thang"] = t.dt.year, t.dt.quarter, t.dt.to_period("M").astype(str)
    df = df.rename(columns={"thoi_diem_dong_thau": "thoi_diem_dong_mo_thau"})

    stats["packages"] = len(df)
    out = cfg.path("processed_dir")
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / "packages.parquet", index=False)
    logger.info("integrated %d packages (join rate %.1f%%, %d non-NSNN removed)",
                len(df), 100 * stats["join_rate"], stats["non_nsnn_removed"])
    return df, stats
