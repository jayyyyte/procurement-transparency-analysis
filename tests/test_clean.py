import logging

import pandas as pd

from src.clean.dedupe import dedupe_notices
from src.clean.integrate import integrate
from src.parse.records import parse_notify, parse_plan

LOG = logging.getLogger("test")


def notify(no, step, version="00", **kw):
    rec = {"id": no, "notifyNo": no, "notifyVersion": version, "planNo": "PL1", "bidName": ["Gói 1"],
           "investorName": "BQL A", "investorCode": "vnA", "investField": ["XL"], "planType": "DTPT",
           "bidForm": "DTRR", "bidPrice": [1_000_000_000.0], "publicDate": "2024-05-01T08:00:00",
           "stepCode": f"notify-contractor-step-{step}-x", "locations": [{"provName": "Tỉnh Nam Định"}]}
    rec.update(kw)
    return parse_notify(rec, "tbmt")


def test_dedupe_prefers_result_step_then_version():
    df = pd.DataFrame([notify("IB1", 1), notify("IB1", 4, bidWinningPrice=[9e8]), notify("IB2", 1, "00"),
                       notify("IB2", 1, "01")])
    out, removed = dedupe_notices(df)
    assert removed == 2
    assert out.set_index("ma_tbmt").loc["IB1", "gia_trung_thau"] == 9e8
    assert out.set_index("ma_tbmt").loc["IB2", "notify_version"] == "01"


def test_integrate_joins_plan_and_filters_budget(cfg):
    # KQLCNT with caseKHKQ=1 has no location -> taken from the plan
    kq = notify("DC1", 4, bidWinningPrice=[990_000_000.0], locations=None, caseKHKQ=1, bidForm="CDTRG")
    other = notify("IB9", 4, planNo="PL2", planType="KHAC", bidWinningPrice=[5e8])
    plan = parse_plan({"planNo": "PL1", "planVersion": "00", "name": "KH A", "pname": "Dự án A",
                       "investorName": "BQL A", "locations": [{"provName": "Tỉnh Nam Định"}], "planType": "DTPT",
                       "bidName": ["Gói 1"], "bidPrice": [1e9], "publicDate": "2024-04-01T00:00:00"})
    interim = {"notices": pd.DataFrame([kq, other]), "plans": pd.DataFrame([plan]), "plan_packages": pd.DataFrame()}
    df, stats = integrate(interim, cfg, LOG)
    assert len(df) == 1 and stats["non_nsnn_removed"] == 1
    row = df.iloc[0]
    assert row["ten_du_an"] == "Dự án A" and row["join_method"] == "ma_khlcnt"
    assert row["tinh_thanh_63"] == "Nam Định" and row["tinh_thanh_34"] == "Ninh Bình"
    assert abs(row["tiet_kiem_pct"] - 0.01) < 1e-9 and row["hinh_thuc_nhom"] == "Chỉ định thầu"
