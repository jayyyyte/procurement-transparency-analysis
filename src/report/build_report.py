"""Collect generated tables/figures into reports/report_assets.md, ordered like the course's written report (FR-6)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.clean.normalize import now_str


def md_table(df: pd.DataFrame, floatfmt: str = "{:.4f}") -> str:
    def fmt(v):
        if isinstance(v, float):
            return floatfmt.format(v)
        return str(v).replace("|", "/")
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "---|" * len(df.columns)
    body = ["| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([head, sep, *body])


def _read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def build(cfg, mode: str, results: dict, logger) -> Path:
    reports, tables, figs = cfg.path("reports_dir"), cfg.path("tables_dir"), cfg.path("figures_dir")
    rel = lambda p: Path(p).relative_to(reports).as_posix()  # noqa: E731
    L = [f"# Report assets — Phân tích minh bạch đấu thầu", "", f"_Sinh tự động {now_str()} · dữ liệu: `{mode}`_", ""]
    if mode == "fixture":
        L += ["> ⚠️ Dữ liệu TỔNG HỢP — file này chỉ minh hoạ cấu trúc report; không dùng số liệu.", ""]

    L += ["## 1. Bài toán & dataset", ""]
    q = _read(reports / "data_quality.md")
    if q:
        overview = q.split("## Tổng quan", 1)[-1].split("## % thiếu", 1)[0].strip()
        L += [overview, "", "Chi tiết: `data_quality.md`.", ""]
    p0 = cfg.root / "reports" / "phase0" / "probe_results.json"
    if p0.exists():
        vol = json.loads(p0.read_text(encoding="utf-8")).get("volume", {}).get("mean_per_day", {})
        L += [f"Nguồn: muasamcong.mpi.gov.vn (Phase 0: ~{vol.get('tbmt', '?')} TBMT, ~{vol.get('kqlcnt', '?')} KQLCNT, "
              f"~{vol.get('khlcnt', '?')} KHLCNT đăng mỗi ngày).", ""]

    L += ["## 2. Phương pháp", "",
          "- Crawl API JSON `smart/search` (trang chủ, không gắn reCAPTCHA) theo cửa sổ 1 ngày, 10 bản ghi/request, "
          "rate limit + retry/backoff + checkpoint SQLite; raw lưu gzip JSONL.",
          "- Làm sạch: chuẩn hoá ngày/tiền/tỉnh (63 → 34), dedupe theo `ma_tbmt` (giữ bước xa nhất/phiên bản mới nhất), "
          "join KHLCNT theo `ma_khlcnt`, lọc NSNN theo proxy `planType`.",
          "- Regression (§7.1): Linear Regression · Random Forest · LightGBM (+ median tham chiếu); split theo thời gian + K-fold.",
          "- Anomaly (§7.2): Rule-based · Isolation Forest · LOF; đánh giá bằng mức đồng thuận (Jaccard, Spearman).", ""]

    L += ["## 3. Kết quả", "", "### 3.1 EDA", ""]
    eda = _read(reports / "eda_insights.md")
    if eda:
        L += [eda.split("## Số liệu chính", 1)[-1].split("## Biểu đồ", 1)[0].strip(), ""]
    L += [f"![{f.stem}]({rel(f)})" for f in sorted(figs.glob("fig0[1-8]_*.png"))] + [""]

    reg = tables / "regression_comparison.csv"
    if reg.exists():
        meta = json.loads((tables / "regression_metrics.json").read_text(encoding="utf-8"))
        L += ["### 3.2 Bài toán 1 — dự đoán " + meta["target_label"], "",
              f"Train {meta['train_rows']:,} gói · test {meta['test_rows']:,} gói (đăng sau {meta['test_after']}). "
              f"Model tốt nhất theo RMSE test: **{meta['best_model']}**.", "",
              md_table(pd.read_csv(reg).drop(columns=["fit_seconds"])), ""]
        imp = pd.read_csv(tables / "feature_importance.csv", index_col=0)
        L += ["Mức độ ảnh hưởng của đặc trưng:", "", md_table(imp.reset_index().rename(columns={"index": "feature"})), ""]
        L += [f"![{f.stem}]({rel(f)})" for f in sorted(figs.glob("fig09_*.png")) + sorted(figs.glob("fig1[01]_*.png"))] + [""]

    an = tables / "anomaly_summary.json"
    if an.exists():
        s = json.loads(an.read_text(encoding="utf-8"))
        top = pd.read_csv(tables / "anomaly_top.csv")
        L += ["### 3.3 Bài toán 2 — điểm bất thường thống kê", "", f"> {s['disclaimer']}", "",
              f"{s['rows']:,} gói có kết quả; mỗi thuật toán gắn cờ top {s['contamination']:.0%} ({s['k_flagged_per_method']:,} gói). "
              f"Số gói theo số thuật toán đồng thuận: {s['consensus_counts']}.", "",
              md_table(pd.read_csv(tables / "anomaly_agreement.csv")), "",
              "Top gói thầu (ưu tiên số thuật toán đồng thuận, rồi percentile trung bình):", "",
              md_table(top[["ma_tbmt", "ben_moi_thau", "nha_thau_trung_thau", "ty_le_trung_thau", "so_nha_thau_tham_du",
                            "n_methods_flagged", "giai_thich_tin_hieu"]].head(10), "{:.3f}"), "",
              "Đầy đủ: `tables/anomaly_top.csv`. Đối chiếu định tính với tin thanh tra/kiểm toán công khai: _R5 bổ sung_.", ""]
        L += [f"![{f.stem}]({rel(f)})" for f in sorted(figs.glob("fig12_*.png"))] + [""]

    for name, title in (("kmeans_clusters.csv", "3.4 (Optional) K-means"), ("network_communities.csv", "3.5 (Optional) Network")):
        p = tables / name
        if p.exists():
            L += [f"### {title}", "", md_table(pd.read_csv(p).head(10), "{:.3f}"), ""]

    L += ["## 4. Thành phần code chính", "",
          "| Module | Vai trò | Owner |", "|---|---|---|",
          "| `src/crawler/` | client lịch sự, checkpoint, raw store, nguồn TBMT/KQLCNT/KHLCNT | R1, R2 |",
          "| `src/parse/`, `src/clean/` | raw → bảng phẳng, chuẩn hoá, dedupe, join, data quality | R3 |",
          "| `src/eda/` | biểu đồ + số liệu insight | R4 |",
          "| `src/model/` | regression, anomaly, k-means, network | R5 |",
          "| `run_pipeline.py` | CLI chạy từng bước / toàn bộ | chung |", ""]
    L += ["## 5. Khó khăn & hướng giải quyết", "", "Xem `reports/phase0_feasibility.md` (mục Khó khăn).", ""]

    out = reports / "report_assets.md"
    out.write_text("\n".join(L), encoding="utf-8")
    logger.info("report assets written to %s", out)
    return out
