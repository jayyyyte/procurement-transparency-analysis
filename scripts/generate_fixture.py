"""Synthetic fixture shaped exactly like the portal's API records (see data/sample/phase0_*.jsonl).

For development/testing of Phase 2-4 while the full crawl waits for the Phase 0 gate.
Every record carries `_synthetic: true` and the data-quality report prints a warning banner —
numbers from this fixture must never appear in the written report.

Planted patterns (so anomaly detection has something to find):
  * some bid solicitors have a "favoured" contractor that wins most of their packages
  * a share of competitive packages has a single bidder and a winning price ~= package price

Usage: python scripts/generate_fixture.py [--plans 6000] [--seed 7]
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import load_config  # noqa: E402

FIELDS = ["HH", "XL", "TV", "PTV", "HON_HOP"]
FIELD_P = [0.38, 0.32, 0.14, 0.13, 0.03]
FORMS = ["DTRR", "CHCT", "CGTTRG", "CDT", "CDTRG"]
FORM_P = [0.30, 0.20, 0.08, 0.07, 0.35]
PLAN_TYPES = ["DTPT", "TX", "DTMS", "KHAC"]
PLAN_TYPE_P = [0.42, 0.33, 0.07, 0.18]
MERGER = datetime(2025, 7, 1)


def gz_writer(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    return gzip.open(path, "wt", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plans", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    cfg = load_config()
    out = cfg.path("fixture_dir")

    with open(cfg.path("province_mapping"), encoding="utf-8") as f:
        prov_rows = list(csv.DictReader(f))
    provinces = [(r["ten_63"], r["ten_34"]) for r in prov_rows]
    prov_weight = rng.pareto(1.5, len(provinces)) + 1
    prov_weight[[i for i, p in enumerate(provinces) if p[0] in ("Hà Nội", "Hồ Chí Minh")]] *= 6  # 2 đô thị lớn
    prov_weight /= prov_weight.sum()
    prov_effect = {p[1]: rng.normal(0, 0.02) for p in provinces}

    n_investors = max(50, args.plans // 6)
    investors = [(f"vn{rng.integers(10**9, 10**10)}", f"BAN QUẢN LÝ DỰ ÁN SỐ {i + 1} (GIẢ LẬP)",
                  provinces[rng.choice(len(provinces), p=prov_weight)]) for i in range(n_investors)]
    contractors = [(f"vn{rng.integers(10**9, 10**10)}", f"CÔNG TY TNHH NHÀ THẦU {i + 1} (GIẢ LẬP)")
                   for i in range(max(100, args.plans // 3))]
    favoured = {inv[0]: contractors[rng.integers(len(contractors))] for inv in investors
                if rng.random() < 0.06}

    end = datetime.now().replace(microsecond=0) - timedelta(days=1)
    start = end - timedelta(days=4 * 365)
    seq = {"PL": 2200000000, "IB": 2200000000, "DC": 2200000000}

    def code(prefix: str, when: datetime) -> str:
        seq[prefix] += int(rng.integers(1, 40))
        return f"{prefix}{str(when.year)[2:]}{seq[prefix] % 10**8:08d}"

    def location(prov: tuple[str, str], when: datetime) -> list[dict]:
        name = prov[1] if when >= MERGER else prov[0]
        prefix = "Thành phố" if name in {"Hà Nội", "Hồ Chí Minh", "Hải Phòng", "Đà Nẵng", "Cần Thơ", "Huế"} else "Tỉnh"
        return [{"provCode": "00", "provName": f"{prefix} {name}"}]

    def iso(t: datetime) -> str:
        return t.isoformat(timespec="seconds")

    f_plan = gz_writer(out / "khlcnt.jsonl.gz")
    f_tbmt = gz_writer(out / "tbmt.jsonl.gz")
    f_kq = gz_writer(out / "kqlcnt.jsonl.gz")
    n = {"khlcnt": 0, "tbmt": 0, "kqlcnt": 0}
    span = (end - start).total_seconds()

    for _ in range(args.plans):
        # year-end surge in publications
        t = start + timedelta(seconds=float(rng.random() * span))
        if rng.random() < 0.15:
            t = t.replace(month=12, day=int(rng.integers(1, 29)))
            t = min(t, end)
        inv_code, inv_name, prov = investors[rng.integers(len(investors))]
        plan_type = rng.choice(PLAN_TYPES, p=PLAN_TYPE_P)
        plan_no = code("PL", t)
        n_pkg = int(rng.integers(1, 5))
        fields = rng.choice(FIELDS, size=n_pkg, p=FIELD_P)
        prices = np.round(np.exp(rng.normal(21.2, 1.4, n_pkg)), -3)  # ~1.6 tỷ median
        names = [f"Gói thầu số {i + 1:02d}: {'Xây lắp' if fl == 'XL' else 'Mua sắm'} hạng mục {rng.integers(1, 999)}"
                 for i, fl in enumerate(fields)]
        project = f"Dự án cải tạo, nâng cấp công trình {rng.integers(1, 9999)} (giả lập)"
        plan = {
            "id": str(uuid.UUID(int=int(rng.integers(0, 2**63)))), "planNo": plan_no, "planVersion": "00",
            "name": f"Kế hoạch lựa chọn nhà thầu {project}", "pname": project,
            "investorName": inv_name, "investorCode": inv_code, "locations": location(prov, t),
            "investField": sorted(set(fields.tolist())), "planType": str(plan_type),
            "investTotal": float(prices.sum() * rng.uniform(1.0, 1.6)), "bidPrice": prices.tolist(),
            "bidName": names, "publicDate": iso(t), "decisionDate": iso(t - timedelta(days=int(rng.integers(1, 20)))),
            "stepCode": "plan-step-1", "type": "es-plan-project-p", "_synthetic": True,
        }
        f_plan.write(json.dumps(plan, ensure_ascii=False) + "\n"); n["khlcnt"] += 1
        if rng.random() < 0.04:  # amended plan version
            f_plan.write(json.dumps({**plan, "planVersion": "01"}, ensure_ascii=False) + "\n"); n["khlcnt"] += 1

        for i in range(n_pkg):
            form = str(rng.choice(FORMS, p=FORM_P))
            if prices[i] < 5e8 and form == "DTRR":
                form = "CHCT"
            direct = form in ("CDT", "CDTRG")
            pub = min(t + timedelta(days=int(rng.integers(3, 60))), end)
            close = pub + timedelta(days=int(rng.integers(7, 30)))
            has_result = close + timedelta(days=20) < end and rng.random() < 0.9
            winner = favoured.get(inv_code) if (inv_code in favoured and rng.random() < 0.75) else None
            winner = winner or contractors[rng.integers(len(contractors))]
            if direct:
                bidders = 1
            else:
                bidders = int(min(1 + rng.poisson(1.8 if fields[i] != "XL" else 2.6), 15))
            single_suspicious = (not direct) and rng.random() < 0.05
            if single_suspicious:
                bidders = 1
            # savings: more bidders / competitive / bigger packages -> lower ratio
            saving = (0.004 if direct else 0.03 + 0.022 * np.log1p(bidders - 1)
                      + 0.01 * (np.log(prices[i]) - 21) + (0.02 if fields[i] == "XL" else 0.0)
                      + (0.01 if plan_type == "DTPT" else 0.0) + prov_effect[prov[1]])
            saving = float(np.clip(saving + rng.normal(0, 0.035 if not direct else 0.004), 0, 0.6))
            if single_suspicious or (winner is favoured.get(inv_code) and rng.random() < 0.5):
                saving = float(rng.uniform(0, 0.004))
            win_price = float(np.round(prices[i] * (1 - saving), -3))
            base = {
                "id": str(uuid.UUID(int=int(rng.integers(0, 2**63)))), "bidName": [names[i]], "investField": [str(fields[i])],
                "investorName": inv_name, "investorCode": inv_code, "planType": str(plan_type), "planNo": plan_no,
                "bidId": str(uuid.UUID(int=int(rng.integers(0, 2**63)))), "bidForm": form, "bidMode": "1_MTHS",
                "bidPrice": [float(prices[i])], "type": "es-notify-contractor", "isInternet": int(not direct),
                "isDomestic": 1, "numPetition": int(rng.random() < 0.02), "processApply": "LDT", "_synthetic": True,
            }
            result = {"bidWinningPrice": [win_price], "contractorName": [winner[1]], "winningCode": [winner[0]],
                      "numBidderJoin": bidders, "numBidderTech": bidders,
                      "stepCode": "notify-contractor-step-4-kqlcnt", "decisionDate": iso(close + timedelta(days=10)),
                      "publicDateKqlcnt": iso(close + timedelta(days=12))}
            if direct:
                if not has_result:
                    continue
                no = code("DC", pub)
                rec = {**base, "notifyNo": no, "notifyVersion": "01", "notifyId": base["id"], "publicDate": iso(pub),
                       "bidCloseDate": iso(pub), "caseKHKQ": 1, **result}
                rec.pop("locations", None)  # like the real KQLCNT records: no location
                f_kq.write(json.dumps(rec, ensure_ascii=False) + "\n"); n["kqlcnt"] += 1
                continue
            no = code("IB", pub)
            rec = {**base, "notifyNo": no, "notifyVersion": "00", "notifyId": base["id"], "publicDate": iso(pub),
                   "bidCloseDate": iso(close), "bidOpenDate": iso(close), "locations": location(prov, pub),
                   "stepCode": "notify-contractor-step-1-tbmt"}
            if has_result:
                rec.update(result)
            f_tbmt.write(json.dumps(rec, ensure_ascii=False) + "\n"); n["tbmt"] += 1
            if has_result and rng.random() < 0.3:  # the same notice seen again in the KQLCNT crawl
                f_kq.write(json.dumps(rec, ensure_ascii=False) + "\n"); n["kqlcnt"] += 1

    for fh in (f_plan, f_tbmt, f_kq):
        fh.close()
    print(f"synthetic fixture written to {out}: {n}")


if __name__ == "__main__":
    main()
