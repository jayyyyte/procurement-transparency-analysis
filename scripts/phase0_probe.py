"""Phase 0 — feasibility probe for muasamcong.mpi.gov.vn (R1 + R2).

Sends a small, fixed number of single requests (~25, >= 2s apart) to answer requirements §3.3:
robots.txt, which endpoints need a reCAPTCHA token, response structure, field coverage vs §3.4,
pagination limits and per-day volume (-> full-scope crawl time estimate).
Full run ~100 requests (~4 min at 2s spacing); `--sections volume` re-runs only the volume sampling.

It never solves, extracts or replays reCAPTCHA tokens. The token-gated advanced-search endpoint is
called once without a token only to record how the server responds; its data is discarded.

Outputs:
  data/raw/phase0/*.json|html           raw responses (not committed)
  data/sample/phase0_<source>.jsonl     POC sample records (<= 100 per source)
  reports/phase0/probe_results.json     machine-readable findings (used by phase0_feasibility.md)

Usage: python scripts/phase0_probe.py [--delay 2.0]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import load_config  # noqa: E402
from src.crawler.client import PoliteClient  # noqa: E402
from src.crawler.es_query import SOURCE_FILTERS, build_search_payload  # noqa: E402

# §3.4 target field -> candidate keys in the API records (checked on the POC sample)
FIELD_CANDIDATES: dict[str, tuple[str, list[str]]] = {
    "ma_goi_thau": ("tbmt,kqlcnt", ["notifyNo"]),
    "ten_goi_thau": ("tbmt,kqlcnt", ["bidName"]),
    "ten_du_an": ("khlcnt", ["name", "planName", "projectName", "pname"]),
    "chu_dau_tu": ("khlcnt", ["investorName", "procuringEntityName"]),
    "ben_moi_thau": ("tbmt,kqlcnt", ["procuringEntityName", "investorName"]),
    "tinh_thanh": ("tbmt,kqlcnt,khlcnt", ["locations", "provName", "location"]),
    "linh_vuc": ("tbmt,kqlcnt", ["investField"]),
    "nguon_von": ("tbmt,kqlcnt,khlcnt", ["capitalDetail", "capitalSource", "investSource", "fundSource", "planType"]),
    "hinh_thuc_lua_chon_nha_thau": ("tbmt,kqlcnt", ["bidForm"]),
    "gia_goi_thau": ("tbmt,kqlcnt", ["bidPrice"]),
    "gia_trung_thau": ("kqlcnt", ["bidWinningPrice", "winningPrice", "lcntPrice"]),
    "nha_thau_trung_thau": ("kqlcnt", ["bidderWinName", "winningBidderName", "contractorName", "bidderName", "orgFullname"]),
    "so_nha_thau_tham_du": ("kqlcnt", ["numBidderJoin", "numBidderTech"]),
    "thoi_diem_dong_mo_thau": ("tbmt", ["bidCloseDate", "bidOpenDate"]),
    "thoi_gian_thuc_hien_hop_dong": ("tbmt,kqlcnt", ["contractPeriod", "contractPeriodUnit", "cperiod", "contractExecutionTime"]),
    "ngay_dang_tai": ("tbmt,kqlcnt,khlcnt", ["publicDate", "publicDateKqlcnt"]),
}

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "phase0"
SAMPLE = ROOT / "data" / "sample"
OUT = ROOT / "reports" / "phase0"


def filled(v) -> bool:
    return v not in (None, "", [], {}, "NaN") and not (isinstance(v, list) and all(x in (None, "") for x in v))


def static_analysis(html: str) -> dict:
    unescaped = html.replace("\\/", "/")
    services = sorted(set(re.findall(r"/o/egp-portal-[\w-]+/services/[\w./-]+", unescaped)))
    return {
        "bytes": len(html),
        "loads_recaptcha": "recaptcha/api.js" in html,
        "grecaptcha_execute_calls": len(re.findall(r"grecaptcha\.execute", html)),
        "token_query_usages": [ln.strip()[:160] for ln in html.splitlines() if "?token=" in ln][:5],
        "services": [s for s in services if "personal-page" not in s and "notification" not in s],
        "es_types": sorted(set(re.findall(r"es-[a-z0-9-]+", unescaped)) - {"es-contractor-selection"}),
        "step_codes": sorted(set(re.findall(r"[a-z-]+-step-\d+-[a-z0-9]+", html))),
        "portlet_unavailable": "tạm thời không có" in html,
    }


def sample_days(n: int, months: int = 48) -> list[date]:
    """n days spread evenly over the last `months` months (deterministic for a given run date)."""
    end = date.today() - timedelta(days=1)
    span = (end - (end - timedelta(days=int(months * 30.44)))).days
    return [end - timedelta(days=round(i * span / (n - 1))) for i in range(n)]


def volume_section(client: PoliteClient, ep: dict, n_days: int) -> dict:
    """Per-day totals for each source on n spread-out days (1 request per source/day, pageSize 10).

    For TBMT the 10 returned records also show whether older notices already carry result fields
    (stepCode step-4, bidWinningPrice) — if so, a separate KQLCNT pass is only needed for caseKHKQ=1.
    """
    variants = {
        "tbmt": build_search_payload,
        "kqlcnt": build_search_payload,
        "khlcnt": build_search_payload,
    }
    out: dict = {"days": [], "totals": {s: {} for s in variants}, "kqlcnt_competitive": {},
                 "tbmt_step_mix": {}, "tbmt_has_winning_price": {}}
    for d in sample_days(n_days):
        out["days"].append(d.isoformat())
        for source in variants:
            r = client.post_json(ep["home_search"], [build_search_payload(source, page=0, page_size=10, start=d, end=d)])
            pg = r.json().get("page", {}) if r.ok else {}
            out["totals"][source][d.isoformat()] = pg.get("totalElements") if r.ok else f"HTTP {r.status_code}"
            if source == "tbmt":
                recs = pg.get("content", [])
                mix: dict[str, int] = {}
                for rec in recs:
                    mix[rec.get("stepCode", "?")] = mix.get(rec.get("stepCode", "?"), 0) + 1
                out["tbmt_step_mix"][d.isoformat()] = mix
                out["tbmt_has_winning_price"][d.isoformat()] = sum(filled(rec.get("bidWinningPrice")) for rec in recs)
        # KQLCNT that belong to a competitive TBMT (caseKHKQ != 1)
        payload = build_search_payload("kqlcnt", page=0, page_size=1, start=d, end=d)
        payload["query"][0]["filters"].append({"fieldName": "caseKHKQ", "searchType": "not_in", "fieldValues": ["1"]})
        r = client.post_json(ep["home_search"], [payload])
        out["kqlcnt_competitive"][d.isoformat()] = r.json().get("page", {}).get("totalElements") if r.ok else f"HTTP {r.status_code}"
    for source, per_day in out["totals"].items():
        vals = [v for v in per_day.values() if isinstance(v, int)]
        out.setdefault("mean_per_day", {})[source] = round(sum(vals) / len(vals), 1) if vals else None
    vals = [v for v in out["kqlcnt_competitive"].values() if isinstance(v, int)]
    out["mean_per_day"]["kqlcnt_competitive"] = round(sum(vals) / len(vals), 1) if vals else None
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--sections", choices=["all", "volume"], default="all",
                    help="'volume' only re-runs the per-day volume sampling and merges it into probe_results.json")
    ap.add_argument("--volume-days", type=int, default=16)
    args = ap.parse_args()
    cfg = load_config()
    crawl = cfg["crawl"]
    ep = crawl["endpoints"]
    RAW.mkdir(parents=True, exist_ok=True)
    SAMPLE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    client = PoliteClient(crawl["base_url"], crawl["user_agent"].replace("<team-email>", "phase0-probe"),
                          min_delay_s=args.delay, jitter_s=0.5, max_retries=2)
    res: dict = {"run_at": datetime.now().isoformat(timespec="seconds"), "base_url": crawl["base_url"]}
    if args.sections == "volume":
        path = OUT / "probe_results.json"
        res = json.loads(path.read_text(encoding="utf-8")) if path.exists() else res
        res["volume"] = volume_section(client, ep, args.volume_days)
        res["volume_run_at"] = datetime.now().isoformat(timespec="seconds")
        path.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps(res["volume"], ensure_ascii=False, indent=1))
        print(f"requests: {client.stats.requests}")
        return

    # 1. robots.txt
    r = client.get("/robots.txt")
    res["robots"] = {"status": r.status_code, "text": r.text.strip()[:500],
                     "search_allowed": client.allowed(crawl["base_url"] + ep["home_search"])}

    # 2. pages + static analysis of their JS
    res["pages"] = {}
    for name, path in {"home": "/", "contractor_selection": "/web/guest/contractor-selection?render=index"}.items():
        t = time.monotonic()
        r = client.get(path)
        (RAW / f"page_{name}.html").write_text(r.text, encoding="utf-8")
        res["pages"][name] = {"status": r.status_code, "latency_s": round(time.monotonic() - t, 2), **static_analysis(r.text)}

    # 3. token-gated endpoint, one request without token: record behaviour only, discard data
    t = time.monotonic()
    r = client.post_json(ep["advanced_search"], [build_search_payload("tbmt", page=0, page_size=1)])
    body = r.text[:300]
    res["advanced_search_without_token"] = {
        "status": r.status_code, "latency_s": round(time.monotonic() - t, 2),
        "content_type": r.headers.get("Content-Type"), "body_head": body,
        "returned_records": '"content"' in r.text and '"content":[]' not in r.text.replace(" ", ""),
    }

    # 4. POC samples from the home-page endpoint (no token; the home page itself calls it)
    res["samples"] = {}
    # the home endpoint rejects pageSize > 10 ("PageSize unsatisfactory!!!")
    for source, pages in {"tbmt": 10, "kqlcnt": 5, "khlcnt": 5}.items():
        records, meta = [], None
        for page in range(pages):
            t = time.monotonic()
            r = client.post_json(ep["home_search"], [build_search_payload(source, page=page, page_size=10)])
            latency = round(time.monotonic() - t, 2)
            data = r.json() if r.ok else {"error": r.status_code, "body": r.text[:200]}
            (RAW / f"home_search_{source}_p{page}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            pg = data.get("page", {})
            meta = {k: v for k, v in pg.items() if k != "content"}
            records += pg.get("content", [])
            res.setdefault("latencies_s", []).append(latency)
        with open(SAMPLE / f"phase0_{source}.jsonl", "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        keys: dict[str, int] = {}
        for rec in records:
            for k, v in rec.items():
                keys[k] = keys.get(k, 0) + filled(v)
        res["samples"][source] = {"n": len(records), "page_meta": meta,
                                  "key_fill_rate": {k: round(v / max(len(records), 1), 2) for k, v in sorted(keys.items())}}

    # page-size limit of the home endpoint (one request with 20)
    r = client.post_json(ep["home_search"], [build_search_payload("tbmt", page=0, page_size=20)])
    res["home_search_page_size_20"] = {"status": r.status_code, "body_head": r.text[:100]}

    # 5. per-day volume on spread-out days
    res["volume"] = volume_section(client, ep, args.volume_days)

    # 6. site-wide statistics endpoint used by the home page
    r = client.request("POST", "/o/egp-portal-home/services/statistic/bid-monitoring/aggregations")
    try:
        agg = r.json()
        res["aggregations"] = agg.get("body", agg) if isinstance(agg, dict) else agg
    except ValueError:
        res["aggregations"] = {"status": r.status_code, "body_head": r.text[:200]}

    # 7. detail page reachable by a stable URL?
    rec = json.loads((SAMPLE / "phase0_tbmt.jsonl").read_text(encoding="utf-8").splitlines()[0])
    detail_url = (f"/web/guest/contractor-selection?render=detail&type={rec['type']}&stepCode={rec['stepCode']}"
                  f"&id={rec['id']}&notifyId={rec['notifyId']}&notifyNo={rec['notifyNo']}&planNo={rec.get('planNo')}")
    r = client.get(detail_url)
    (RAW / "page_detail.html").write_text(r.text, encoding="utf-8")
    res["detail_page"] = {"url": detail_url, "status": r.status_code, **static_analysis(r.text)}

    # 8. field coverage vs requirements §3.4
    samples = {s: [json.loads(ln) for ln in (SAMPLE / f"phase0_{s}.jsonl").read_text(encoding="utf-8").splitlines()]
               for s in ("tbmt", "kqlcnt", "khlcnt")}
    coverage = {}
    for field, (sources, cands) in FIELD_CANDIDATES.items():
        best = (0.0, None, None)
        for s in sources.split(","):
            recs = samples[s]
            for k in cands:
                rate = sum(filled(r.get(k)) for r in recs) / len(recs) if recs else 0.0
                if rate > best[0]:
                    best = (rate, s, k)
        coverage[field] = {"fill_rate": round(best[0], 2), "source": best[1], "key": best[2]}
    res["field_coverage"] = coverage
    res["fields_available_ge_50pct"] = sum(v["fill_rate"] >= 0.5 for v in coverage.values())
    res["fields_total"] = len(coverage)
    res["client_stats"] = client.stats.__dict__

    (OUT / "probe_results.json").write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("robots", "advanced_search_without_token", "field_coverage")},
                     ensure_ascii=False, indent=1, default=str))
    print(f"\nfields >=50% filled: {res['fields_available_ge_50pct']}/{res['fields_total']}"
          f" | requests: {client.stats.requests} | written: {OUT / 'probe_results.json'}")


if __name__ == "__main__":
    main()
