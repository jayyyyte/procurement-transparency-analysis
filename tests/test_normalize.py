import numpy as np
import pandas as pd
import pytest

from src.clean.normalize import ProvinceMapper, hinh_thuc_nhom, parse_money
from src.config import PROJECT_ROOT


@pytest.mark.parametrize("raw,expected", [
    (1234567.0, 1234567.0),
    ("1.234.567.890 VND", 1234567890.0),
    ("1.234.567,5", 1234567.5),
    ("1,234,567", 1234567.0),
    ("570945000", 570945000.0),
    ("", np.nan),
    (None, np.nan),
])
def test_parse_money(raw, expected):
    got = parse_money(raw)
    assert (np.isnan(got) and np.isnan(expected)) or got == expected


@pytest.fixture(scope="module")
def mapper():
    return ProvinceMapper(PROJECT_ROOT / "config" / "province_mapping.csv")


def test_province_before_merger(mapper):
    assert mapper.map("Tỉnh Hà Giang", pd.Timestamp("2024-03-01")) == ("Hà Giang", "Tuyên Quang")
    assert mapper.map("Tỉnh Bà Rịa - Vũng Tàu", pd.Timestamp("2023-01-01")) == ("Bà Rịa - Vũng Tàu", "Hồ Chí Minh")


def test_province_after_merger_cannot_trace_back(mapper):
    # "Tuyên Quang" after 07/2025 is the merged province (old Hà Giang + Tuyên Quang)
    assert mapper.map("Tỉnh Tuyên Quang", pd.Timestamp("2026-09-25")) == (None, "Tuyên Quang")
    # unchanged provinces keep their 63-level name
    assert mapper.map("Tỉnh Cao Bằng", pd.Timestamp("2026-09-25")) == ("Cao Bằng", "Cao Bằng")


def test_province_aliases(mapper):
    assert mapper.map("Thành phố Hồ Chí Minh")[1] == "Hồ Chí Minh"
    assert mapper.map("TP. Hồ Chí Minh")[1] == "Hồ Chí Minh"
    assert mapper.map("Thành phố Huế", pd.Timestamp("2026-01-01")) == ("Thừa Thiên Huế", "Huế")
    assert mapper.map("Tỉnh Không Tồn Tại") == (None, None)
    assert mapper.map(None) == (None, None)


def test_mapping_has_63_to_34():
    df = pd.read_csv(PROJECT_ROOT / "config" / "province_mapping.csv")
    assert len(df) == 63 and df["ten_34"].nunique() == 34


def test_hinh_thuc_nhom():
    assert hinh_thuc_nhom("DTRR") == "Cạnh tranh"
    assert hinh_thuc_nhom("CDTRG") == "Chỉ định thầu"
    assert hinh_thuc_nhom("TTH") == "Khác"
