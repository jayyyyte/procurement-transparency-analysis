import numpy as np
import pandas as pd

from src.clean.contractors import resolve_winners
from src.model.anomaly import rule_score
from src.model.features import anomaly_frame


def packages(rows):
    base = {"co_ket_qua": True, "gia_goi_thau": 1e9, "ma_nha_thau_trung_thau": None, "ngay_dang_kqlcnt": pd.NaT,
            "hinh_thuc_nhom": "Cạnh tranh", "so_nha_thau_tham_du": 3, "ty_le_trung_thau": 0.9, "gia_trung_thau": 9e8}
    df = pd.DataFrame([{**base, **r} for r in rows])
    df["ngay_dang_tai"] = pd.to_datetime(df["ngay_dang_tai"])
    return resolve_winners(df)[0]


def test_repeat_wins_counted_in_trailing_window(cfg):
    rows = [{"ma_tbmt": f"IB{i}", "ma_ben_moi_thau": "B1", "nha_thau_trung_thau": "X", "ngay_dang_tai": d}
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


def test_wins_belong_to_their_own_solicitor_winner_pair(cfg):
    """Many pairs of different sizes: every package must get the count of its own pair, not a neighbour's."""
    rng = np.random.default_rng(0)
    n, days = 600, cfg["anomaly"]["repeat_window_days"]
    df = packages([{"ma_tbmt": f"IB{i}", "ma_ben_moi_thau": f"vn01000000{rng.integers(10, 30)}",
                    "nha_thau_trung_thau": f"NT {rng.integers(40)}", "ma_nha_thau_trung_thau": None,
                    "ngay_dang_tai": pd.Timestamp("2024-01-01") + pd.Timedelta(days=int(rng.integers(700)))}
                   for i in range(n)])
    d = anomaly_frame(df, cfg)
    assert len(d) == n
    t, pair = d["ngay_dang_tai"], d["ma_ben_moi_thau"] + "/" + d["nha_thau_trung_thau"]
    expected = [int(((pair == pair[i]) & (t <= t[i]) & (t > t[i] - pd.Timedelta(days=days))).sum()) for i in d.index]
    assert d["wins_in_window"].tolist() == expected
    assert (d["wins_in_window"] <= pair.map(pair.value_counts())).all()


def test_consortium_member_and_unregistered_winner_are_credited(cfg):
    a, b = "vn0100000001", "vn0200000002"
    rows = [{"ma_tbmt": "IB1", "nha_thau_trung_thau": "CÔNG TY A", "ma_nha_thau_trung_thau": a, "ngay_dang_tai": "2024-01-10"},
            {"ma_tbmt": "IB2", "nha_thau_trung_thau": "Liên danh A - B", "ma_nha_thau_trung_thau": f"{b} | {a}",
             "ngay_dang_tai": "2024-02-10"},
            {"ma_tbmt": "IB3", "nha_thau_trung_thau": "Công ty A", "ma_nha_thau_trung_thau": a, "ngay_dang_tai": "2024-03-10"},
            # an unregistered shop gets a new UUID with every result
            *[{"ma_tbmt": f"DC{i}", "nha_thau_trung_thau": "Cửa hàng Toan", "ngay_dang_tai": f"2024-0{i}-15",
               "ma_nha_thau_trung_thau": f"f7a5063c-9654-43c6-8b0a-5bd8a41cf1b{i}"} for i in (1, 2, 3)]]
    d = anomaly_frame(packages([{"ma_ben_moi_thau": "B1", **r} for r in rows]), cfg).set_index("ma_tbmt")
    assert d.loc["IB3", "wins_in_window"] == 3 and d.loc["IB3", "repeat_winner"] == 1   # A: alone, in consortium, alone
    assert d.loc["IB2", "wins_in_window"] == 2 and d.loc["IB2", "winner_share"] == 0.5   # its most repeated member, A
    assert d.loc["DC3", "wins_in_window"] == 3 and d.loc["DC3", "repeat_winner"] == 1
    assert 0 < d.loc["IB1", "solicitor_hhi"] <= 1
