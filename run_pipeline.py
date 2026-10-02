"""Pipeline CLI: crawl -> parse -> clean -> eda -> model -> report.

  python run_pipeline.py crawl [--sources tbmt,kqlcnt,khlcnt] [--start YYYY-MM-DD --end YYYY-MM-DD]
  python run_pipeline.py all                 # parse..report on crawled raw data (crawl runs separately)
  python run_pipeline.py all --data fixture  # same, on the synthetic fixture (scripts/generate_fixture.py)
  python run_pipeline.py all --data sample   # same, on the Phase 0 POC sample (too small for models)

Outputs of --data sample/fixture go to data/{interim,processed}/<mode>/ and reports/_<mode>/ so they
never mix with results from real crawled data.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime

import pandas as pd

from src.config import crawl_window, load_config
from src.logs import setup_logging

STEPS = ["crawl", "parse", "clean", "eda", "model", "report"]

GATE_MSG = """Full crawl đang bị KHOÁ bởi gate Phase 0 (crawl.approved_option = null trong config/config.yaml).
Đọc reports/phase0_feasibility.md §6 (nhóm đã chốt D1 = phương án A), rồi đặt approved_option: "A".
(Dùng --data fixture để chạy các bước sau trên dữ liệu tổng hợp trong lúc chờ.)"""


def configure(args):
    cfg = load_config(args.config)
    if args.data != "raw":
        m = args.data
        cfg = cfg.with_paths(interim_dir=f"data/interim/{m}", processed_dir=f"data/processed/{m}",
                             reports_dir=f"reports/_{m}", figures_dir=f"reports/_{m}/figures",
                             tables_dir=f"reports/_{m}/tables")
    for key in ("reports_dir", "figures_dir", "tables_dir", "processed_dir", "interim_dir"):
        cfg.path(key).mkdir(parents=True, exist_ok=True)
    return cfg


def step_crawl(cfg, args, log) -> None:
    from src.crawler.checkpoint import Checkpoint
    from src.crawler.client import CircuitOpen, CrawlBlocked, PoliteClient
    from src.crawler.raw_store import RawStore
    from src.crawler.sources import SearchSource

    c = cfg["crawl"]
    if args.data != "raw":
        sys.exit("crawl chỉ chạy với --data raw")
    if c.get("approved_option") in (None, "", "null"):
        sys.exit(GATE_MSG)
    if c["approved_option"] == "B":
        sys.exit("Phương án B (trình duyệt thật) chưa được implement — cần thiết kế riêng sau khi được duyệt.")
    if c["approved_option"] != "A":
        sys.exit(f"approved_option không hợp lệ: {c['approved_option']!r}")
    if "<" in c["user_agent"]:
        sys.exit("crawl.user_agent còn placeholder — điền email liên hệ (D5) trước khi crawl thật.")
    if args.start:
        c["start_date"] = args.start
    if args.end:
        c["end_date"] = args.end
    start, end = crawl_window(cfg)
    sources = args.sources.split(",") if args.sources else c["sources"]
    log.info("crawl window %s -> %s, sources=%s, option=%s", start, end, sources, c["approved_option"])

    client = PoliteClient.from_config(c, logger=log)
    cp = Checkpoint(cfg.path("checkpoint_db"))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        for source in sources:
            store = RawStore(cfg.path("raw_dir"), source, c["raw_batch_size"])
            src = SearchSource(source, client, store, cp, c["endpoints"]["home_search"], c["page_size"],
                               c["max_result_window"], log, (c.get("extra_filters") or {}).get(source))
            try:
                n = src.crawl(start, end)
                log.info("%s done: %d new records", source, n)
            finally:
                store.close()
                client.stats.dump(cfg.path("logs_dir") / f"crawl_stats_{ts}.json")
    except (CrawlBlocked, CircuitOpen) as e:
        log.error("CRAWL STOPPED: %s — ghi vào báo cáo, không tìm cách vượt qua.", e)
        sys.exit(2)
    finally:
        log.info("checkpoint summary: %s | stats: %s", cp.summary(), client.stats)
        cp.close()


def step_parse(cfg, args, log):
    from src.parse.records import parse_all
    return parse_all(cfg, args.data, log)


def step_clean(cfg, args, log, interim=None):
    from src.clean.integrate import integrate
    from src.clean.quality import write_report
    if interim is None:
        d = cfg.path("interim_dir")
        interim = {n: pd.read_parquet(d / f"{n}.parquet") for n in ("notices", "plans", "plan_packages")}
    df, stats = integrate(interim, cfg, log)
    write_report(df, stats, cfg, args.data)
    return df


def _packages(cfg) -> pd.DataFrame:
    return pd.read_parquet(cfg.path("processed_dir") / "packages.parquet")


def step_eda(cfg, args, log, df=None):
    from src.eda import insights, plots
    df = _packages(cfg) if df is None else df
    synthetic = bool(df["is_synthetic"].any())
    figs = plots.make_all(df, cfg, log, synthetic)
    return insights.write(df, cfg, figs, synthetic)


def step_model(cfg, args, log, df=None) -> dict:
    from src.model import anomaly, regression
    df = _packages(cfg) if df is None else df
    out = {"regression": regression.run(df, cfg, log)}
    a = anomaly.run(df, cfg, log)
    out["anomaly"] = a
    opt = cfg.data.get("optional", {})
    if opt.get("kmeans"):
        from src.model import clustering
        out["kmeans"] = clustering.run(df, cfg, log)
    if opt.get("network"):
        from src.model import network
        out["network"] = network.run(df, cfg, log)
    return out


def step_report(cfg, args, log, results=None):
    from src.report.build_report import build
    return build(cfg, args.data, results or {}, log)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=STEPS + ["all"])
    ap.add_argument("--config", default=None)
    ap.add_argument("--data", choices=["raw", "sample", "fixture"], default="raw",
                    help="raw = crawled data (default); sample = Phase 0 POC; fixture = synthetic")
    ap.add_argument("--sources", help="crawl only: comma-separated subset of tbmt,kqlcnt,khlcnt")
    ap.add_argument("--start", help="crawl only: YYYY-MM-DD (overrides config)")
    ap.add_argument("--end", help="crawl only: YYYY-MM-DD (overrides config)")
    args = ap.parse_args(argv)
    cfg = configure(args)
    log = setup_logging(f"{args.step}_{args.data}", cfg.path("logs_dir"))
    log.info("run_pipeline %s --data %s (%s)", args.step, args.data, date.today())

    if args.step == "crawl":
        return step_crawl(cfg, args, log)
    if args.step == "all":
        interim = step_parse(cfg, args, log)
        df = step_clean(cfg, args, log, interim)
        step_eda(cfg, args, log, df)
        results = step_model(cfg, args, log, df)
        step_report(cfg, args, log, results)
        return
    {"parse": step_parse, "clean": step_clean, "eda": step_eda, "model": step_model,
     "report": step_report}[args.step](cfg, args, log)


if __name__ == "__main__":
    main()
