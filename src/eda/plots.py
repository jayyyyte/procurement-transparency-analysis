"""EDA figures (FR-4) -> reports/figures/*.png. One chart = one question; no dual axes."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

# Reference palette (dataviz skill, light mode); first 3 categorical slots validated all-pairs.
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
SEQ = "#2a78d6"
GROUP_ORDER = ["Cạnh tranh", "Chỉ định thầu", "Khác"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": TEXT_2, "xtick.color": TEXT_2, "ytick.color": TEXT_2,
    "text.color": TEXT, "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "font.size": 9.5, "legend.frameon": False,
    "font.family": ["Segoe UI", "DejaVu Sans"],
})


def _save(fig, cfg, name: str, note: str | None) -> str:
    if note:
        fig.text(0.01, 0.005, note, fontsize=8, color=TEXT_2, ha="left", va="bottom")
    out = cfg.path("figures_dir")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def _hbar(ax, s: pd.Series, title: str, fmt, xlabel: str | None = None) -> None:
    s = s.sort_values()
    ax.barh(s.index, s.values, color=SEQ, height=0.7, edgecolor=SURFACE, linewidth=2)
    ax.set_title(title)
    ax.grid(axis="y", visible=False)
    for i, v in enumerate(s.values):
        ax.text(v, i, " " + fmt(v), va="center", fontsize=8, color=TEXT_2)
    ax.margins(x=0.15)
    if xlabel:
        ax.set_xlabel(xlabel)


def ty(v: float) -> str:
    """Label for values already divided by 1e9."""
    return f"{v:,.0f}"


def fig_province(df, cfg, note):
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.5))
    top = df["tinh_thanh"].value_counts().head(15)
    _hbar(axes[0], top, "Số gói thầu theo tỉnh (top 15, 34 tỉnh mới)", lambda v: f"{v:,.0f}")
    val = df.groupby("tinh_thanh")["gia_goi_thau"].sum().sort_values(ascending=False).head(15) / 1e9
    _hbar(axes[1], val, "Tổng giá gói thầu theo tỉnh (top 15)", ty, "tỷ đồng")
    fig.tight_layout()
    return _save(fig, cfg, "fig01_tinh_thanh", note)


def fig_field(df, cfg, note):
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    _hbar(axes[0], df["linh_vuc"].value_counts(), "Số gói thầu theo lĩnh vực", lambda v: f"{v:,.0f}")
    _hbar(axes[1], df.groupby("linh_vuc")["gia_goi_thau"].sum() / 1e9, "Tổng giá gói thầu theo lĩnh vực", ty, "tỷ đồng")
    fig.tight_layout()
    return _save(fig, cfg, "fig02_linh_vuc", note)


def fig_trend(df, cfg, note):
    monthly = df.set_index("ngay_dang_tai").resample("MS").size()
    quarterly = df.set_index("ngay_dang_tai").resample("QS")["gia_goi_thau"].sum() / 1e12
    fig, axes = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True)
    axes[0].plot(monthly.index, monthly.values, color=SEQ, linewidth=2)
    axes[0].set_title("Số gói thầu đăng tải theo tháng")
    peak = monthly.idxmax()
    axes[0].annotate(f"cao nhất {peak:%m/%Y}: {monthly.max():,}", (peak, monthly.max()),
                     xytext=(8, -4), textcoords="offset points", fontsize=8, color=TEXT_2)
    axes[1].bar(quarterly.index, quarterly.values, width=70, color=SEQ, edgecolor=SURFACE, linewidth=2)
    axes[1].set_title("Tổng giá gói thầu theo quý (nghìn tỷ đồng)")
    fig.tight_layout()
    return _save(fig, cfg, "fig03_xu_huong_thoi_gian", note)


def fig_method(df, cfg, note):
    groups = [g for g in GROUP_ORDER if (df["hinh_thuc_nhom"] == g).any()]
    share = (pd.crosstab(df["linh_vuc"], df["hinh_thuc_nhom"], normalize="index")
             .reindex(columns=groups, fill_value=0))
    share.loc["TẤT CẢ"] = df["hinh_thuc_nhom"].value_counts(normalize=True).reindex(groups, fill_value=0)
    share = share.iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 4))
    left = np.zeros(len(share))
    for col in groups:
        color = SERIES[GROUP_ORDER.index(col)]  # colour follows the group, not its position
        vals = share[col].values
        ax.barh(share.index, vals, left=left, color=color, height=0.65, edgecolor=SURFACE, linewidth=2, label=col)
        for i, (l, v) in enumerate(zip(left, vals)):
            if v >= 0.06:
                ax.text(l + v / 2, i, f"{v:.0%}", ha="center", va="center", fontsize=8, color=TEXT, weight="bold")
        left += vals
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title("Tỷ lệ hình thức lựa chọn nhà thầu theo lĩnh vực")
    ax.legend(ncol=3, loc="upper left", bbox_to_anchor=(0, -0.08))
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return _save(fig, cfg, "fig04_hinh_thuc_lcnt", note)


def fig_savings(df, cfg, note):
    d = df.dropna(subset=["tiet_kiem_pct"])
    groups = [g for g in GROUP_ORDER if (d["hinh_thuc_nhom"] == g).any()]
    fig, axes = plt.subplots(1, len(groups), figsize=(4 * len(groups), 3.6), sharey=False)
    axes = np.atleast_1d(axes)
    bins = np.linspace(-0.05, 0.5, 45)
    for ax, g, color in zip(axes, groups, SERIES):
        v = d.loc[d["hinh_thuc_nhom"] == g, "tiet_kiem_pct"].clip(-0.05, 0.5)
        ax.hist(v, bins=bins, color=color, edgecolor=SURFACE, linewidth=1)
        med = v.median()
        ax.axvline(med, color=TEXT, linewidth=1, linestyle="--")
        ax.text(med, ax.get_ylim()[1] * 0.92, f" trung vị {med:.1%}", fontsize=8, color=TEXT)
        ax.set_title(f"{g} (n={len(v):,})")
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    fig.suptitle("Phân bố % tiết kiệm = 1 − giá trúng / giá gói thầu", x=0.01, ha="left", weight="bold")
    fig.tight_layout()
    return _save(fig, cfg, "fig05_phan_bo_tiet_kiem", note)


def fig_contractors(df, cfg, note):
    d = df.dropna(subset=["nha_thau_trung_thau"])
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    short = lambda s: s if len(s) <= 42 else s[:40] + "…"  # noqa: E731
    wins = d["nha_thau_trung_thau"].value_counts().head(12)
    _hbar(axes[0], wins.rename(index=short), "Top nhà thầu theo số gói trúng", lambda v: f"{v:,.0f}")
    val = d.groupby("nha_thau_trung_thau")["gia_trung_thau"].sum().sort_values(ascending=False).head(12) / 1e9
    _hbar(axes[1], val.rename(index=short), "Top nhà thầu theo tổng giá trúng", ty, "tỷ đồng")
    fig.tight_layout()
    return _save(fig, cfg, "fig06_top_nha_thau", note)


def fig_bidders(df, cfg, note):
    d = df[(df["hinh_thuc_nhom"] == "Cạnh tranh")].dropna(subset=["tiet_kiem_pct", "so_nha_thau_tham_du"])
    d = d[d["so_nha_thau_tham_du"] >= 1]
    k = d["so_nha_thau_tham_du"].clip(upper=8).astype(int)
    stats = d.groupby(k)["tiet_kiem_pct"].describe(percentiles=[0.25, 0.5, 0.75])
    fig, ax = plt.subplots(figsize=(9, 4))
    x = stats.index.values
    ax.vlines(x, stats["25%"], stats["75%"], color=SEQ, linewidth=6, alpha=0.35, label="khoảng tứ phân vị")
    ax.plot(x, stats["50%"], "o-", color=SEQ, linewidth=2, markersize=7, label="trung vị")
    ax.set_xticks(x, [f"{i}" if i < 8 else "8+" for i in x])
    ax.set_xlabel("Số nhà thầu tham dự")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    for xi, n in zip(x, stats["count"]):
        ax.text(xi, ax.get_ylim()[0], f"n={int(n):,}", ha="center", va="bottom", fontsize=7, color=TEXT_2)
    ax.set_title("% tiết kiệm theo số nhà thầu tham dự (hình thức cạnh tranh)")
    ax.legend(loc="upper left")
    fig.tight_layout()
    return _save(fig, cfg, "fig07_so_nha_thau_vs_tiet_kiem", note)


def hhi_by_solicitor(df: pd.DataFrame, min_packages: int = 5) -> pd.Series:
    """Herfindahl index of winners' share (by count) for each bid solicitor with >= min_packages results."""
    d = df.dropna(subset=["nha_thau_trung_thau"])
    counts = d.groupby(["ma_ben_moi_thau", "nha_thau_trung_thau"]).size()
    totals = counts.groupby(level=0).sum()
    shares = counts / totals.reindex(counts.index.get_level_values(0)).values
    hhi = (shares ** 2).groupby(level=0).sum()
    return hhi[totals >= min_packages]


def fig_hhi(df, cfg, note):
    hhi = hhi_by_solicitor(df)
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.hist(hhi, bins=np.linspace(0, 1, 41), color=SEQ, edgecolor=SURFACE, linewidth=1)
    ax.axvline(0.25, color=TEXT, linewidth=1, linestyle="--")
    ax.text(0.25, ax.get_ylim()[1] * 0.9, f"  HHI > 0.25 (tập trung cao): {(hhi > 0.25).mean():.0%} bên mời thầu",
            fontsize=8, color=TEXT)
    ax.set_title(f"Mức tập trung nhà thầu trúng tại mỗi bên mời thầu (HHI, n={len(hhi):,} bên có ≥5 gói)")
    ax.set_xlabel("HHI theo số gói trúng (1 = một nhà thầu thắng tất cả)")
    fig.tight_layout()
    return _save(fig, cfg, "fig08_tap_trung_hhi", note)


FIGURES = [fig_province, fig_field, fig_trend, fig_method, fig_savings, fig_contractors, fig_bidders, fig_hhi]


def make_all(df: pd.DataFrame, cfg, logger, synthetic: bool) -> list[str]:
    note = "DỮ LIỆU TỔNG HỢP (synthetic) — chỉ để kiểm thử pipeline" if synthetic else "Nguồn: muasamcong.mpi.gov.vn"
    paths = []
    for fn in FIGURES:
        try:
            paths.append(fn(df, cfg, note))
        except Exception as e:  # one broken chart must not stop the rest
            logger.warning("figure %s failed: %s", fn.__name__, e)
    logger.info("wrote %d figures to %s", len(paths), cfg.path("figures_dir"))
    return paths
