VIETNAM PROCUREMENT TRANSPARENCY ANALYSIS
Capstone project - Introduction to Data Science (IT4142E), SOICT - HUST
===========================================================================

Pipeline: crawl du lieu dau thau cong khai (muasamcong.mpi.gov.vn) -> lam sach & tich hop
-> EDA -> modeling (du doan % tiet kiem + diem bat thuong thong ke) -> so lieu cho written report.

---------------------------------------------------------------------------
1. CAI DAT (Windows / macOS / Linux, Python >= 3.11; da kiem thu tren 3.14)
---------------------------------------------------------------------------
  python -m venv .venv
  Windows:      .venv\Scripts\activate
  macOS/Linux:  source .venv/bin/activate
  pip install -r requirements.txt

Kiem tra:  python -m pytest          (19 test, khong can Internet)

---------------------------------------------------------------------------
2. CHAY NHANH (khong can crawl) - du lieu tong hop de kiem thu pipeline
---------------------------------------------------------------------------
  python scripts/generate_fixture.py
  python run_pipeline.py all --data fixture          (~30 giay)
  -> ket qua trong reports/_fixture/  (DU LIEU GIA - khong dung trong bao cao)

  python run_pipeline.py all --data sample           (mau that Phase 0, 200 ban ghi;
                                                       qua nho nen buoc model tu bo qua)

---------------------------------------------------------------------------
3. CHAY DAY DU TREN DU LIEU THAT (theo thu tu)
---------------------------------------------------------------------------
  B0. Phase 0 (da lam, tai lap duoc):  python scripts/phase0_probe.py
        -> reports/phase0_feasibility.md, reports/phase0/probe_results.json
  B1. Crawl:  python run_pipeline.py crawl [--sources tbmt,kqlcnt,khlcnt] [--start YYYY-MM-DD --end YYYY-MM-DD]
        * Gate Phase 0 da chot (crawl.approved_option: "A", xem phase0_feasibility.md muc 6).
        * Truoc khi crawl: dat email lien he (mail truong) vao bien moi truong, vd PowerShell:
              $env:PTVN_CONTACT_EMAIL="ten@sis.hust.edu.vn"
          Neu approved_option = null hoac chua dat bien nay thi lenh crawl tu dung.
        * Dot 1: 24 thang tinh tu ngay chay (crawl.months_back: 24), 1 request / 1.5-2s.
          Dot 2: doi months_back thanh 48 roi chay lai lenh cu -> chi crawl them phan cu hon.
        * Truoc khi chot dataset final: crawl lai ~3 thang cuoi de lay ket qua cua cac goi
          TBMT luc crawl chua co KQ (phase0_feasibility.md muc 6, D2).
        * Dung giua chung (Ctrl+C) roi chay lai lenh cu -> tiep tuc tu checkpoint
          (data/checkpoint.sqlite), khong crawl trung.
        * Thoi gian uoc tinh: 2-10 ngay tuy pham vi (phase0_feasibility.md muc 5).
  B2. Cac buoc sau:  python run_pipeline.py all
        (hoac tung buoc: parse -> clean -> eda -> model -> report)

Ket qua:
  data/raw/<nguon>/<thoi diem>/batch_*.jsonl.gz   raw response API (giu de parse lai)
  data/interim/*.parquet                           ban ghi phang theo nguon
  data/processed/packages.parquet                  dataset sach, 1 dong / goi thau
  reports/data_quality.md                          bao cao chat luong du lieu
  reports/eda_insights.md, reports/figures/*.png   EDA (>= 8 bieu do)
  reports/tables/regression_comparison.csv         so sanh Linear Regression / Random Forest / LightGBM
  reports/tables/anomaly_*.csv|json                Rule-based / Isolation Forest / LOF + dong thuan
  reports/report_assets.md                         gom so lieu + hinh theo cau truc written report
  logs/*.log, logs/crawl_stats_*.json              log crawl (so request, loi, retry) va training

---------------------------------------------------------------------------
4. CAU HINH - config/config.yaml
---------------------------------------------------------------------------
  crawl.*    cua so thoi gian, rate limit, retry, gate approved_option, chien luoc extra_filters
  clean.*    proxy nguon von (nsnn_plan_types), nguong outlier
  model.*    target (tiet_kiem_pct | log_gia_trung), so thang test, k-fold
  anomaly.*  nguong tin hieu, trong so rule-based, ty le gan co, LOF
  optional.* bat/tat K-means va network analysis

---------------------------------------------------------------------------
5. CAU TRUC CODE
---------------------------------------------------------------------------
  run_pipeline.py          CLI chay tung buoc / toan bo
  src/crawler/             client lich su (rate limit, retry, robots.txt, circuit breaker),
                           checkpoint SQLite, raw store, payload API, nguon TBMT/KQLCNT/KHLCNT   [R1, R2]
  src/parse/               raw -> bang phang                                                     [R3]
  src/clean/               chuan hoa (ngay, tien, tinh 63->34), dedupe, join, data quality       [R3]
  src/eda/                 bieu do + so lieu insight                                             [R4]
  src/model/               regression, anomaly, clustering (K-means), network (Louvain)          [R5]
  src/report/              tong hop report_assets.md                                             [R5]
  scripts/                 phase0_probe.py, generate_fixture.py, make_zip.py
  config/                  config.yaml, province_mapping.csv (63 tinh cu -> 34 tinh moi)
  tests/                   pytest
  docs/                    requirements.md, team-plan.md

---------------------------------------------------------------------------
6. THU VIEN BEN NGOAI (khai bao day du trong requirements.txt)
---------------------------------------------------------------------------
  requests, PyYAML, numpy, pandas, pyarrow, scikit-learn, lightgbm,
  matplotlib, networkx, pytest.
  Thu vien chuan Python: sqlite3, gzip, json, ssl, urllib.robotparser, csv, argparse, logging.

---------------------------------------------------------------------------
7. LUU Y DAO DUC / PHAP LY
---------------------------------------------------------------------------
  * Chi dung du lieu cong khai, khong dang nhap, khong vuot CAPTCHA; crawler dung han khi gap
    403/challenge. User-Agent ghi ro muc dich hoc thuat.
  * Diem anomaly la "diem bat thuong thong ke", KHONG phai ket luan vi pham hay gian lan.

Dong goi nop bai:  python scripts/make_zip.py   -> dist/procurement-transparency-analysis.zip
