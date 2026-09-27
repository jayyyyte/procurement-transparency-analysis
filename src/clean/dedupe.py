"""Dedupe: one row per bid notice (ma_tbmt) and per plan (ma_khlcnt), keeping the most advanced/latest version."""
from __future__ import annotations

import pandas as pd

from src.clean.normalize import step_rank, version_num


def dedupe_notices(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """The same notice can be crawled as TBMT and again as KQLCNT, and re-published as new versions.
    Keep the row with the furthest step (results), then highest version, then latest publication."""
    if df.empty:
        return df, 0
    d = df.assign(_step=df["step_code"].map(step_rank),
                  _ver=df["notify_version"].map(version_num),
                  _pub=pd.to_datetime(df["ngay_dang_kqlcnt"].fillna(df["ngay_dang_tai"]), errors="coerce", format="mixed"))
    d = d.sort_values(["ma_tbmt", "_step", "_ver", "_pub"], na_position="first")
    out = d.drop_duplicates("ma_tbmt", keep="last").drop(columns=["_step", "_ver", "_pub"])
    return out.reset_index(drop=True), len(df) - len(out)


def dedupe_plans(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if df.empty:
        return df, 0
    d = df.assign(_ver=df["plan_version"].map(version_num)).sort_values(["ma_khlcnt", "_ver"])
    out = d.drop_duplicates("ma_khlcnt", keep="last").drop(columns=["_ver"])
    return out.reset_index(drop=True), len(df) - len(out)
