import pandas as pd

from src.clean.contractors import contractor_names, explode_winners, resolve_winners

VNPT = "TẬP ĐOÀN BƯU CHÍNH VIỄN THÔNG VIỆT NAM"
UUID1, UUID2, UUID3 = ("f7a5063c-9654-43c6-8b0a-5bd8a41cf1b1", "cedb7fea-8564-475f-974b-46385c5e7cf4",
                       "c3023525-e4d0-44a2-9ee9-d506f3b43408")


def resolve(rows):
    df = pd.DataFrame(rows, columns=["ma_ben_moi_thau", "nha_thau_trung_thau", "ma_nha_thau_trung_thau"])
    return resolve_winners(df)


def test_one_code_under_several_names_is_one_contractor():
    df, stats = resolve([
        ("B1", f"{VNPT} (LOẠI HÌNH DOANH NGHIỆP: CÔNG TY TNHH)", "vn0100684378"),
        ("B2", f"{VNPT} (LOẠI HÌNH DOANH NGHIỆP: CÔNG TY TNHH)", "vn0100684378"),
        ("B2", "Tập đoàn Bưu chính Viễn thông Việt Nam - VNPT", "vn0100684378"),
        ("B1", "Trung tâm Quan trắc tài nguyên và môi trường", "vnz000000001"),
        ("B2", "Trung tâm Quan trắc tài nguyên và môi trường", "vnz000000002"),  # same name, another entity
    ])
    assert df["nha_thau_key"].tolist() == ["vn0100684378"] * 3 + ["vnz000000001", "vnz000000002"]
    assert df["nha_thau_chuan"].tolist()[:3] == [VNPT] * 3  # most frequent spelling, legal-form note dropped
    assert stats["codes_with_name_variants"] == 1 and stats["contractors"] == 3


def test_unregistered_winner_is_keyed_by_name_within_its_solicitor():
    df, stats = resolve([
        ("B1", "Cửa hàng Nguyễn Xuân Toan", UUID1),
        ("B1", "CỬA HÀNG  NGUYỄN XUÂN TOAN", UUID2),   # fresh UUID per result, same shop
        ("B2", "Cửa hàng Nguyễn Xuân Toan", UUID3),    # same name elsewhere: not assumed to be the same shop
    ])
    assert df["nha_thau_key"].tolist() == ["ten:cua hang nguyen xuan toan@B1"] * 2 + ["ten:cua hang nguyen xuan toan@B2"]
    assert stats["by_name_unregistered"] == 3 and stats["by_system_code"] == 0


def test_several_winners_are_keyed_by_code_whatever_the_order():
    df, stats = resolve([
        ("B1", "Liên danh gói thầu số 01", "vn0200000002 | vn0100000001"),               # consortium: 1 name
        ("B1", "CÔNG TY A | CÔNG TY B", "vn0100000001 | vn0200000002"),                  # multi-lot: names in another order
        ("B1", "CÔNG TY A", "vn0100000001"),
        ("B1", None, None),
    ])
    assert df["nha_thau_key"].tolist()[:2] == ["vn0100000001 | vn0200000002"] * 2
    assert df["so_nha_thau_trung"].tolist()[:3] == [2, 2, 1] and pd.isna(df.loc[3, "nha_thau_key"])
    assert df.loc[0, "nha_thau_chuan"] == "Liên danh gói thầu số 01"
    assert stats["multi_winner"] == 2 and stats["packages_with_winner"] == 3
    w = explode_winners(df)
    assert w["nha_thau_key"].value_counts().to_dict() == {"vn0100000001": 3, "vn0200000002": 2}
    assert w.index.tolist() == [0, 0, 1, 1, 2]
    assert contractor_names(df).to_dict() == {"vn0100000001": "CÔNG TY A"}
