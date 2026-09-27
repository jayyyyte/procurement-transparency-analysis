"""Normalisation: dates, money (VND), provinces (63 -> 34), category codes -> labels."""
from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.text import norm_key

MERGER_DATE = pd.Timestamp("2025-07-01")  # 34 đơn vị hành chính cấp tỉnh có hiệu lực

LINH_VUC = {"HH": "Hàng hóa", "XL": "Xây lắp", "TV": "Tư vấn", "PTV": "Phi tư vấn", "HON_HOP": "Hỗn hợp"}

HINH_THUC = {
    "DTRR": "Đấu thầu rộng rãi",
    "DTHC": "Đấu thầu hạn chế",
    "CDT": "Chỉ định thầu",
    "CDTRG": "Chỉ định thầu rút gọn",
    "CHCT": "Chào hàng cạnh tranh",
    "CHCTRG": "Chào hàng cạnh tranh rút gọn",
    "CGTT": "Chào giá trực tuyến",
    "CGTTRG": "Chào giá trực tuyến rút gọn",
    "MSTT": "Mua sắm trực tiếp",
    "TTH": "Tự thực hiện",
    "DPG": "Đàm phán giá",
    "LCNT_DB": "Lựa chọn nhà thầu trường hợp đặc biệt",
    "TGTHCD": "Tham gia thực hiện của cộng đồng",
}
COMPETITIVE_FORMS = {"DTRR", "DTHC", "CHCT", "CHCTRG", "CGTT", "CGTTRG"}
DIRECT_FORMS = {"CDT", "CDTRG"}

PLAN_TYPE = {"DTPT": "Đầu tư phát triển", "TX": "Chi thường xuyên", "DTMS": "Dự toán mua sắm", "KHAC": "Khác"}


def to_datetime(s: pd.Series) -> pd.Series:
    """API timestamps are local Vietnam time (UTC+7) without offset; kept naive."""
    return pd.to_datetime(s, errors="coerce", format="mixed")


_MONEY_JUNK = re.compile(r"(vnd|vnđ|đồng|dong|đ)\s*$", re.I)


def parse_money(v) -> float:
    """Numbers pass through; strings like '1.234.567.890 VND' / '1,234,567' -> float VND."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    s = _MONEY_JUNK.sub("", str(v).strip()).strip()
    if not s:
        return np.nan
    # Vietnamese format uses '.' for thousands and ',' for decimals
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", s):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return np.nan


class ProvinceMapper:
    def __init__(self, mapping_csv: Path):
        self.to34: dict[str, str] = {}
        self.old_names: dict[str, str] = {}
        self.unchanged: set[str] = set()
        with open(mapping_csv, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        targets: dict[str, int] = {}
        for r in rows:
            targets[r["ten_34"]] = targets.get(r["ten_34"], 0) + 1
        for r in rows:
            keys = {norm_key(r["ten_63"])} | {norm_key(a) for a in r["alias"].split(";") if a.strip()}
            for k in keys:
                self.to34[k] = r["ten_34"]
                self.old_names[k] = r["ten_63"]
            if targets[r["ten_34"]] == 1:
                self.unchanged.add(r["ten_63"])
        for new in targets:
            self.to34.setdefault(norm_key(new), new)

    @staticmethod
    def _key(name: str) -> str:
        k = norm_key(name)
        return re.sub(r"^(tinh|thanh pho|tp)\s+", "", k)

    def map(self, name, published: pd.Timestamp | None = None) -> tuple[str | None, str | None]:
        """-> (tinh_thanh_63, tinh_thanh_34). A post-merger record naming a merged province cannot
        be traced back to one of the 63 old provinces, so its 63-level value is None."""
        if name is None or (isinstance(name, float) and np.isnan(name)):
            return None, None
        k = self._key(name)
        new = self.to34.get(k)
        old = self.old_names.get(k)
        if new is None:
            return None, None
        if old is None or (published is not None and not pd.isna(published) and published >= MERGER_DATE
                           and old not in self.unchanged):
            return None, new
        return old, new


def hinh_thuc_nhom(code) -> str:
    if code in COMPETITIVE_FORMS:
        return "Cạnh tranh"
    if code in DIRECT_FORMS:
        return "Chỉ định thầu"
    return "Khác"


def version_num(v) -> int:
    try:
        return int(str(v))
    except (TypeError, ValueError):
        return -1


def step_rank(step) -> int:
    m = re.search(r"step-(\d+)", str(step or ""))
    return int(m.group(1)) if m else 0


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")
