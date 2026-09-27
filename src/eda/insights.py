"""Numbers behind the EDA figures -> reports/eda_insights.md (+ tables). R4 adds the commentary."""
from __future__ import annotations

import pandas as pd

from src.clean.normalize import now_str
from src.eda.plots import hhi_by_solicitor


def compute(df: pd.DataFrame) -> dict:
    res = df.dropna(subset=["tiet_kiem_pct"])
    prov = df["tinh_thanh"].value_counts()
    monthly = df.set_index("ngay_dang_tai").resample("MS").size()
    by_month_of_year = df.groupby(df["ngay_dang_tai"].dt.month).size()
    comp = res[res["hinh_thuc_nhom"] == "Cạnh tranh"]
    single = comp[comp["so_nha_thau_tham_du"] == 1]
    multi = comp[comp["so_nha_thau_tham_du"] >= 2]
    hhi = hhi_by_solicitor(df)
    wins = df["nha_thau_trung_thau"].value_counts()
    return {
        "n_packages": len(df),
        "n_with_result": len(res),
        "period": f"{df['ngay_dang_tai'].min():%d/%m/%Y} – {df['ngay_dang_tai'].max():%d/%m/%Y}",
        "total_value_ty": df["gia_goi_thau"].sum() / 1e9,
        "top5_province_share": prov.head(5).sum() / max(prov.sum(), 1),
        "top5_provinces": ", ".join(prov.head(5).index),
        "field_share": df["linh_vuc"].value_counts(normalize=True).round(3).to_dict(),
        "method_share": df["hinh_thuc_nhom"].value_counts(normalize=True).round(3).to_dict(),
        "direct_value_share": df.loc[df["hinh_thuc_nhom"] == "Chỉ định thầu", "gia_goi_thau"].sum() / max(df["gia_goi_thau"].sum(), 1),
        "peak_month": f"{monthly.idxmax():%m/%Y}" if len(monthly) else None,
        "busiest_calendar_month": int(by_month_of_year.idxmax()) if len(by_month_of_year) else None,
        "busiest_month_share": float(by_month_of_year.max() / max(by_month_of_year.sum(), 1)),
        "median_saving_by_group": res.groupby("hinh_thuc_nhom")["tiet_kiem_pct"].median().round(4).to_dict(),
        "median_saving_single_bidder": float(single["tiet_kiem_pct"].median()) if len(single) else None,
        "median_saving_multi_bidder": float(multi["tiet_kiem_pct"].median()) if len(multi) else None,
        "share_single_bidder_competitive": len(single) / max(len(comp), 1),
        "share_near_zero_saving": float((res["tiet_kiem_pct"] < 0.01).mean()) if len(res) else None,
        "n_solicitors_hhi": len(hhi),
        "share_solicitors_hhi_gt_025": float((hhi > 0.25).mean()) if len(hhi) else None,
        "top_contractor": wins.index[0] if len(wins) else None,
        "top_contractor_wins": int(wins.iloc[0]) if len(wins) else None,
    }


def write(df: pd.DataFrame, cfg, figures: list[str], synthetic: bool) -> dict:
    s = compute(df)
    tables = cfg.path("tables_dir")
    tables.mkdir(parents=True, exist_ok=True)
    df.groupby("tinh_thanh").agg(so_goi=("ma_tbmt", "size"), tong_gia_goi=("gia_goi_thau", "sum"),
                                 tiet_kiem_trung_vi=("tiet_kiem_pct", "median")) \
      .sort_values("so_goi", ascending=False).to_csv(tables / "eda_by_province.csv")
    df.groupby(["nam", "hinh_thuc_nhom"]).size().unstack(fill_value=0).to_csv(tables / "eda_method_by_year.csv")

    pct = lambda v: "—" if v is None else f"{v:.1%}"  # noqa: E731
    lines = ["# EDA — số liệu & insight", "", f"_Sinh tự động {now_str()}_", ""]
    if synthetic:
        lines += ["> ⚠️ **DỮ LIỆU TỔNG HỢP** — số liệu dưới đây chỉ kiểm thử pipeline, không phải kết quả thật.", ""]
    lines += [
        "## Số liệu chính",
        "",
        f"- Phạm vi: **{s['n_packages']:,} gói thầu** (NSNN, proxy planType), {s['period']}; "
        f"{s['n_with_result']:,} gói đã có kết quả. Tổng giá gói thầu ≈ {s['total_value_ty']:,.0f} tỷ đồng.",
        f"- **Địa lý (fig01):** top 5 tỉnh ({s['top5_provinces']}) chiếm {pct(s['top5_province_share'])} số gói.",
        f"- **Lĩnh vực (fig02):** {', '.join(f'{k} {v:.0%}' for k, v in s['field_share'].items())}.",
        f"- **Thời gian (fig03):** tháng cao điểm {s['peak_month']}; tháng {s['busiest_calendar_month']} "
        f"trong năm chiếm {pct(s['busiest_month_share'])} số gói (mùa vụ giải ngân).",
        f"- **Hình thức (fig04):** {', '.join(f'{k} {v:.0%}' for k, v in s['method_share'].items())}; "
        f"chỉ định thầu chiếm {pct(s['direct_value_share'])} tổng giá trị.",
        f"- **Tiết kiệm (fig05):** trung vị theo nhóm {', '.join(f'{k} {v:.1%}' for k, v in s['median_saving_by_group'].items())}; "
        f"{pct(s['share_near_zero_saving'])} gói tiết kiệm < 1%.",
        f"- **Cạnh tranh (fig07):** trong hình thức cạnh tranh, {pct(s['share_single_bidder_competitive'])} gói chỉ có 1 nhà thầu; "
        f"tiết kiệm trung vị 1 nhà thầu = {pct(s['median_saving_single_bidder'])} so với ≥2 nhà thầu = {pct(s['median_saving_multi_bidder'])}.",
        f"- **Tập trung (fig06, fig08):** nhà thầu thắng nhiều nhất: {s['top_contractor']} ({s['top_contractor_wins']} gói); "
        f"{pct(s['share_solicitors_hhi_gt_025'])} trong {s['n_solicitors_hhi']:,} bên mời thầu (≥5 gói) có HHI > 0.25.",
        "",
        "## Biểu đồ",
        "",
    ]
    lines += [f"- `{p.split('reports')[-1].lstrip(chr(92) + '/')}`" for p in figures]
    lines += ["", "## Nhận xét (R4 bổ sung)", "", "_TODO: diễn giải từng insight, đối chiếu báo chí/số liệu công khai._", ""]
    (cfg.path("reports_dir") / "eda_insights.md").write_text("\n".join(lines), encoding="utf-8")
    return s
