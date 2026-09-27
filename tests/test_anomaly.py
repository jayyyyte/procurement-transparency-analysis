import pandas as pd

from src.model.anomaly import rule_score
from src.model.features import anomaly_frame


def packages(rows):
    base = {"co_ket_qua": True, "gia_goi_thau": 1e9, "ma_nha_thau_trung_thau": None, "ngay_dang_kqlcnt": pd.NaT,
            "hinh_thuc_nhom": "Cạnh tranh", "so_nha_thau_tham_du": 3}
    df = pd.DataFrame([{**base, **r} for r in rows])
    df["ngay_dang_tai"] = pd.to_datetime(df["ngay_dang_tai"])
    return df


def test_repeat_wins_counted_in_trailing_window(cfg):
    rows = [{"ma_tbmt": f"IB{i}", "ma_ben_moi_thau": "B1", "nha_thau_trung_thau": "X", "ngay_dang_tai": d,
             "ty_le_trung_thau": 0.9, "gia_trung_thau": 9e8}
            for i, d in enumerate(["2024-01-01", "2024-02-01", "2024-03-01", "2025-01-01"])]
    rows.append({"ma_tbmt": "IB9", "ma_ben_moi_thau": "B1", "nha_thau_trung_thau": "Y", "ngay_dang_tai": "2024-03-02",
                 "ty_le_trung_thau": 0.999, "gia_trung_thau": 9.99e8, "so_nha_thau_tham_du": 1})
    d = anomaly_frame(packages(rows), cfg).set_index("ma_tbmt")
    assert d.loc["IB2", "wins_in_window"] == 3        # Jan, Feb, Mar within 180 days
    assert d.loc["IB3", "wins_in_window"] == 1        # the 2025 win is outside the window
    assert d.loc["IB2", "repeat_winner"] == 1
    assert d.loc["IB9", "single_bidder"] == 1
    assert d.loc["IB0", "winner_share"] == 0.8
    s = rule_score(d, cfg)
    assert s["IB9"] > s["IB0"]  # single bidder + near-full price outranks a normal package
