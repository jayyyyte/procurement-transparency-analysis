"""Raw API records -> flat rows (schema §3.4 + extra fields). Types/values are normalised later in clean/.

Record shapes (seen in Phase 0):
  notify docs  (type es-notify-contractor; sources tbmt + kqlcnt): one bid notice, whose `stepCode`
               advances tbmt -> kqmt -> dsntdkt -> kqlcnt; once at step 4 it carries result fields
               (bidWinningPrice, contractorName, numBidderJoin). caseKHKQ=1 = result published together
               with the plan (no TBMT, e.g. chỉ định thầu rút gọn).
  plan docs    (type es-plan-project-p; source khlcnt): one KHLCNT with parallel lists of packages.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Iterable, Iterator

import pandas as pd

from src.crawler.raw_store import iter_raw


def _first(v):
    if isinstance(v, list):
        return v[0] if v else None
    return v


def _join(v, sep=" | "):
    if isinstance(v, list):
        vals = [str(x) for x in v if x not in (None, "")]
        return sep.join(vals) if vals else None
    return v


def _sum(v):
    if isinstance(v, list):
        nums = [float(x) for x in v if isinstance(x, (int, float))]
        return sum(nums) if nums else None
    return float(v) if isinstance(v, (int, float)) else v


def _location(rec: dict) -> tuple[str | None, str | None, int]:
    locs = rec.get("locations") or []
    if not locs:
        return None, None, 0
    provs = {loc.get("provName") for loc in locs if loc.get("provName")}
    return locs[0].get("provName"), locs[0].get("provCode"), len(provs)


def _invest_field(v) -> str | None:
    vals = sorted(set(v)) if isinstance(v, list) else ([v] if v else [])
    if not vals:
        return None
    return vals[0] if len(vals) == 1 else "HON_HOP"


def parse_notify(rec: dict, source: str) -> dict:
    prov, prov_code, n_prov = _location(rec)
    return {
        "source": source,
        "notify_id": rec.get("id"),
        "ma_tbmt": rec.get("notifyNo"),
        "notify_version": rec.get("notifyVersion"),
        "ma_khlcnt": rec.get("planNo"),
        "bid_id": rec.get("bidId"),
        "ten_goi_thau": _join(rec.get("bidName")),
        "chu_dau_tu": rec.get("investorName"),
        "ma_chu_dau_tu": rec.get("investorCode"),
        "ben_moi_thau": rec.get("procuringEntityName") or rec.get("investorName"),
        "ma_ben_moi_thau": rec.get("procuringEntityCode") or rec.get("investorCode"),
        "tinh_thanh_raw": prov,
        "prov_code": prov_code,
        "n_tinh": n_prov,
        "linh_vuc_raw": _invest_field(rec.get("investField")),
        "plan_type": rec.get("planType"),
        "hinh_thuc_raw": rec.get("bidForm"),
        "phuong_thuc": rec.get("bidMode"),
        "gia_goi_thau": _sum(rec.get("bidPrice")),
        "gia_trung_thau": _sum(rec.get("bidWinningPrice")),
        "nha_thau_trung_thau": _join(rec.get("contractorName")),
        "ma_nha_thau_trung_thau": _join(rec.get("winningCode")),
        "so_nha_thau_tham_du": rec.get("numBidderJoin"),
        "so_nha_thau_dat_kt": rec.get("numBidderTech"),
        "thoi_diem_dong_thau": rec.get("bidCloseDate"),
        "thoi_diem_mo_thau": rec.get("bidOpenDate"),
        "thoi_gian_thuc_hien_hop_dong": rec.get("contractPeriod"),
        "ngay_dang_tai": rec.get("publicDate"),
        "ngay_dang_kqlcnt": rec.get("publicDateKqlcnt"),
        "ngay_quyet_dinh": rec.get("decisionDate"),
        "step_code": rec.get("stepCode"),
        "case_khkq": rec.get("caseKHKQ"),
        "qua_mang": rec.get("isInternet"),
        "trong_nuoc": rec.get("isDomestic"),
        "so_kien_nghi": rec.get("numPetition"),
        "is_synthetic": bool(rec.get("_synthetic", False)),
    }


def parse_plan(rec: dict) -> dict:
    prov, prov_code, n_prov = _location(rec)
    names = rec.get("bidName") or []
    return {
        "plan_id": rec.get("id"),
        "ma_khlcnt": rec.get("planNo"),
        "plan_version": rec.get("planVersion"),
        "ten_khlcnt": rec.get("name"),
        "ten_du_an": rec.get("pname") or rec.get("name"),
        "chu_dau_tu": rec.get("investorName"),
        "ma_chu_dau_tu": rec.get("investorCode"),
        "ben_moi_thau": rec.get("procuringEntityName"),
        "tinh_thanh_raw": prov,
        "prov_code": prov_code,
        "n_tinh": n_prov,
        "linh_vuc_raw": _invest_field(rec.get("investField")),
        "plan_type": rec.get("planType"),
        "tong_muc_dau_tu": rec.get("investTotal"),
        "tong_gia_goi_thau": _sum(rec.get("bidPrice")),
        "so_goi_thau": len(names) if isinstance(names, list) else None,
        "ngay_dang_tai": rec.get("publicDate"),
        "ngay_quyet_dinh": rec.get("decisionDate"),
        "is_synthetic": bool(rec.get("_synthetic", False)),
    }


def explode_plan_packages(rec: dict) -> list[dict]:
    names = rec.get("bidName") or []
    prices = rec.get("bidPrice") or []
    return [{"ma_khlcnt": rec.get("planNo"), "plan_version": rec.get("planVersion"), "stt": i,
             "ten_goi_thau": n, "gia_goi_thau_kh": prices[i] if i < len(prices) else None}
            for i, n in enumerate(names)]


# ---------- loaders ----------

def records_from_raw(raw_dir: Path, source: str) -> Iterator[dict]:
    """Records inside raw list responses written by the crawler (RawStore)."""
    for line in iter_raw(raw_dir, source):
        if line.get("kind") == "list" and isinstance(line.get("payload"), dict):
            yield from line["payload"].get("page", {}).get("content", [])


def records_from_jsonl(path: Path) -> Iterator[dict]:
    """Records stored one per line (Phase 0 sample, synthetic fixture)."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def load_source(mode: str, source: str, cfg) -> Iterable[dict]:
    if mode == "raw":
        return records_from_raw(cfg.path("raw_dir"), source)
    if mode == "sample":
        return records_from_jsonl(cfg.path("sample_dir") / f"phase0_{source}.jsonl")
    if mode == "fixture":
        return records_from_jsonl(cfg.path("fixture_dir") / f"{source}.jsonl.gz")
    raise ValueError(mode)


def parse_all(cfg, mode: str, logger) -> dict[str, pd.DataFrame]:
    """Parse every source and write data/interim/{notices,plans,plan_packages}.parquet."""
    notices, plans, packages = [], [], []
    for source in ("tbmt", "kqlcnt"):
        n0 = len(notices)
        notices += [parse_notify(r, source) for r in load_source(mode, source, cfg)]
        logger.info("parsed %s: %d notify records", source, len(notices) - n0)
    for r in load_source(mode, "khlcnt", cfg):
        plans.append(parse_plan(r))
        packages += explode_plan_packages(r)
    logger.info("parsed khlcnt: %d plans, %d plan packages", len(plans), len(packages))
    out_dir = cfg.path("interim_dir")
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = {"notices": pd.DataFrame(notices), "plans": pd.DataFrame(plans),
              "plan_packages": pd.DataFrame(packages)}
    for name, df in frames.items():
        df.to_parquet(out_dir / f"{name}.parquet", index=False)
    return frames
