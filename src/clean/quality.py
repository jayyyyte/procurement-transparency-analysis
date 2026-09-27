"""Data quality report (FR-3): missing rates, join coverage, outliers, dedupe/filter counts."""
from __future__ import annotations

import pandas as pd

from src.clean.normalize import now_str

KEY_FIELDS = [
    "ma_tbmt", "ten_goi_thau", "ten_du_an", "chu_dau_tu", "ben_moi_thau", "tinh_thanh", "linh_vuc",
    "nguon_von", "hinh_thuc_lua_chon_nha_thau", "gia_goi_thau", "gia_trung_thau", "nha_thau_trung_thau",
    "so_nha_thau_tham_du", "thoi_diem_dong_mo_thau", "thoi_gian_thuc_hien_hop_dong", "ngay_dang_tai",
]


def missing_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c in KEY_FIELDS:
        if c not in df:
            rows.append({"field": c, "missing_pct": 100.0, "missing_pct_with_result": 100.0})
            continue
        res = df[df["co_ket_qua"]] if "co_ket_qua" in df else df
        rows.append({"field": c,
                     "missing_pct": round(100 * df[c].isna().mean(), 2) if len(df) else 100.0,
                     "missing_pct_with_result": round(100 * res[c].isna().mean(), 2) if len(res) else 100.0})
    return pd.DataFrame(rows)


def outliers(df: pd.DataFrame, low: float, high: float) -> dict[str, int]:
    r = df["ty_le_trung_thau"]
    return {
        "gia_goi_thau <= 0": int((df["gia_goi_thau"] <= 0).sum()),
        "gia_trung_thau <= 0": int((df["gia_trung_thau"] <= 0).sum()),
        "gia_trung_thau > gia_goi_thau": int((df["gia_trung_thau"] > df["gia_goi_thau"]).sum()),
        f"ty_le_trung_thau < {low}": int((r < low).sum()),
        f"ty_le_trung_thau > {high}": int((r > high).sum()),
        "ngay_dang_tai thiếu/không parse được": int(df["ngay_dang_tai"].isna().sum()),
    }


def write_report(df: pd.DataFrame, stats: dict, cfg, mode: str) -> str:
    low, high = cfg["clean"]["ratio_outlier_low"], cfg["clean"]["ratio_outlier_high"]
    miss = missing_table(df)
    outl = outliers(df, low, high)
    tables = cfg.path("tables_dir")
    tables.mkdir(parents=True, exist_ok=True)
    miss.to_csv(tables / "data_quality_missing.csv", index=False)

    synthetic = bool(df.get("is_synthetic", pd.Series(dtype=bool)).any())
    lines = [
        "# Data Quality Report",
        "",
        f"_Sinh tự động {now_str()} — nguồn dữ liệu: `{mode}`_",
        "",
    ]
    if synthetic:
        lines += ["> ⚠️ **DỮ LIỆU TỔNG HỢP (synthetic fixture)** — chỉ dùng để kiểm thử pipeline, "
                  "KHÔNG dùng số liệu này trong written report.", ""]
    lines += [
        "## Tổng quan",
        "",
        "| Chỉ số | Giá trị |",
        "|---|---|",
        f"| Bản ghi notify thô (TBMT + KQLCNT) | {stats['notices_raw']:,} |",
        f"| Bị loại do trùng `ma_tbmt` | {stats['notices_dup_removed']:,} |",
        f"| KHLCNT (sau dedupe) | {stats['plans']:,} (loại trùng {stats['plans_dup_removed']:,}) |",
        f"| Tỉ lệ join được KHLCNT theo `ma_khlcnt` | {100 * stats['join_rate']:.1f}% |",
        f"| Bị loại vì không phải NSNN (proxy planType) | {stats['non_nsnn_removed']:,} {stats['non_nsnn_by_type']} |",
        f"| **Gói thầu cuối cùng** | **{stats['packages']:,}** |",
        f"| Trong đó có dấu hiệu vốn vay (ODA/TPCP, theo từ khoá tên) | {stats.get('dau_hieu_von_vay', 0):,} |",
        f"| Trong đó đã có kết quả (giá trúng) | {int(df['co_ket_qua'].sum()):,} |",
        "",
        "## % thiếu theo field (schema §3.4)",
        "",
        "| Field | % thiếu (tất cả) | % thiếu (gói đã có KQ) |",
        "|---|---|---|",
    ]
    lines += [f"| `{r.field}` | {r.missing_pct:.1f} | {r.missing_pct_with_result:.1f} |" for r in miss.itertuples()]
    lines += ["", "## Outlier / bất hợp lệ", "", "| Kiểm tra | Số gói |", "|---|---|"]
    lines += [f"| {k} | {v:,} |" for k, v in outl.items()]
    if stats.get("province_unmapped"):
        lines += ["", f"Tên tỉnh chưa map được (top): `{stats['province_unmapped']}`"]
    lines += [
        "",
        "## Ghi chú",
        "",
        "- `thoi_gian_thuc_hien_hop_dong` không có trong API danh sách; cần API chi tiết (chưa xác minh ở Phase 0).",
        "- `nguon_von` là proxy từ `planType` của KHLCNT, không phải field nguồn vốn gốc. Phạm vi giữ DTPT "
        "(đầu tư công, kể cả vốn TPCP/ODA cân đối qua NSNN), TX, DTMS; loại KHAC.",
        "- `dau_hieu_von_vay` chỉ là heuristic theo từ khoá (ODA, vốn vay, WB, ADB, JICA, trái phiếu...): "
        "dùng cho phân tích độ nhạy, không dùng để lọc.",
        "- `tinh_thanh_63` để trống với gói đăng sau 01/07/2025 thuộc tỉnh đã sáp nhập (không truy ngược được).",
        "",
    ]
    text = "\n".join(lines)
    (cfg.path("reports_dir") / "data_quality.md").write_text(text, encoding="utf-8")
    return text
