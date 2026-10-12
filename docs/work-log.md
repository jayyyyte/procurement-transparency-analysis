# Nhật ký làm việc (Work Log)

**Project:** Vietnam Procurement Transparency Analysis — IT4142E, SOICT – HUST
**Phạm vi nhật ký:** 25/09/2026 → 12/10/2026 · **Cập nhật lần cuối:** 12/10/2026
**Cách dùng:** mỗi mốc có *việc đã làm → cách làm → kết quả → commit*. Phần cuối là các vấn đề còn mở. Khi có việc mới, thêm một mục ở cuối §2 và cập nhật §1, §4.

> Các thư mục `data/raw/`, `data/interim/`, `data/processed/`, `logs/`, `reports/figures/`, `reports/tables/` bị `.gitignore`, nên **không có trong repo**. Số liệu kết quả bên dưới được ghi lại ở đây để không mất khi dữ liệu bị sinh lại. Nguồn của từng con số xem §5.

---

## 1. Tóm tắt nhanh

| Mốc | Ngày | Trạng thái | Kết quả chính |
|---|---|---|---|
| Khung dự án, tài liệu, crawler, code pipeline | 25–27/09 | ✅ Xong | 13 commit, đủ 5 module `crawler/parse/clean/eda/model/report` |
| Phase 0 — POC crawl & feasibility | 25/09 | ✅ Xong | 200 bản ghi mẫu thật, 15/16 field có dữ liệu |
| Chốt gate D1–D5 | 27/09 (D3), 02/10 (còn lại) | ✅ Xong | Phương án A, chiến lược S2, đợt 1 = 24 tháng |
| Full crawl đợt 1 (24 tháng) | 02–06/10 | ✅ Xong | 206.621 request, 2.056.114 bản ghi, **0 lỗi** |
| Parse → clean → EDA → model → report trên dữ liệu thật | 12/10 | ✅ Chạy hết | 1.108.989 gói thầu; LightGBM R² test 0,153; 903 gói được cả 3 thuật toán gắn cờ (sau Việc 17) |
| Crawl mở rộng 48 tháng | — | ⏳ Chưa làm | Chưa có log |
| Crawl lại ~3 tháng cuối trước khi chốt dataset | — | ⏳ **Cần làm** | Tỉ lệ có KQ đã tụt còn 88,8% ở 09–10/2026 (§3.3) |

---

## 2. Nhật ký theo ngày

### 25/09/2026 — Khởi tạo, crawler, Phase 0

**Việc 1. Dựng khung dự án và tài liệu** (`cfcbe2c`, 15:00)
- Viết `docs/requirements.md` (223 dòng: scope, phased plan, schema §3.4, mô hình §7), `docs/team-plan.md` (phân vai 5 người: Data Lead / Data Engineer / 2 AI / DevOps), `README.md`, `docs/README.md`, `requirements.txt`.
- Viết bản đầu `reports/phase0_feasibility.md`.

**Việc 2. Viết crawler** (`61b5891`, `2220eb6`)
- `src/crawler/client.py` — client "lịch sự": rate limit + jitter, retry/backoff theo `Retry-After`, đọc `robots.txt`, circuit breaker dừng hẳn khi gặp 403/challenge, `LegacyTLSAdapter` hạ SECLEVEL chỉ cho domain này (server dùng khoá DH 1024-bit, OpenSSL 3 từ chối) nhưng vẫn verify chứng chỉ.
- `src/crawler/es_query.py` (payload kiểu Elasticsearch), `sources.py` (3 nguồn TBMT / KQLCNT / KHLCNT), `checkpoint.py` (SQLite, theo cặp *nguồn × ngày × trang*), `raw_store.py` (gzip JSONL, 500 bản ghi/file).
- `src/config.py`, `src/logs.py`, `src/text.py` — đọc `config.yaml`, log ra `logs/`, helper chuẩn hoá chữ.

**Việc 3. Script hỗ trợ** (`d85b98d`)
- `scripts/phase0_probe.py` (249 dòng) — khảo sát tự động, ghi `reports/phase0/probe_results.json`.
- `scripts/generate_fixture.py` — sinh dữ liệu tổng hợp để chạy thử pipeline không cần Internet.
- `scripts/make_zip.py` — đóng gói nộp bài.

**Việc 4. Khảo sát Phase 0** (chạy `phase0_probe.py`)
- ~100 request đơn lẻ, cách nhau ≥ 2s, User-Agent ghi mục đích học thuật. Không có 403/429/challenge; 3 request cố ý test giới hạn đều nhận 400 như dự kiến.
- Đọc JavaScript của chính site để tìm endpoint thay vì đoán → phát hiện danh sách render bằng Vue, không nằm trong HTML.
- **Phát hiện chính:**
  - Tìm kiếm nâng cao gắn **reCAPTCHA v3** (gọi không token → HTTP 400). Không vượt, không dùng lại token.
  - Endpoint trang chủ `/o/egp-portal-home/services/smart/search` **không gắn CAPTCHA**, cùng index, nhưng `pageSize ≤ 10` và `totalElements` tối đa 10.000 → phải chia cửa sổ 1 ngày.
  - KQLCNT không có địa điểm → lấy tỉnh qua join KHLCNT theo `planNo`.
  - Không có field nguồn vốn và thời gian thực hiện hợp đồng ở API danh sách.
- **Kết quả:** mẫu 100 TBMT + 50 KQLCNT + 50 KHLCNT (`data/sample/phase0_*.jsonl`); 15/16 field mong muốn có dữ liệu (94%); ước lượng volume từ 16 ngày lấy mẫu trải đều 48 tháng: TB 442 TBMT / 1.510 KQLCNT / 946 KHLCNT mỗi ngày → 48 tháng ≈ 4,2 triệu bản ghi ≈ **9,9 ngày** ở 1 request/2s (S1), 8,4 ngày (S2), 5,2 ngày (S3).

**Việc 5. Chạy thử pipeline trên fixture và sample** (log `all_fixture_*`, `all_sample_*`, 14:39–14:50)
- `run_pipeline.py all --data fixture` chạy xong ~30s; `--data sample` (200 bản ghi thật) chạy được nhưng bước model tự bỏ qua vì dưới `min_rows: 200`.

---

### 27/09/2026 — Hoàn thiện module xử lý & chốt D3

**Việc 6. Hoàn thiện các module sau crawl** (`3333914` → `5c39c7c`, 14:41–14:44)

| Module | File chính | Nội dung |
|---|---|---|
| `src/parse/` | `records.py` (178 dòng) | raw JSONL → bảng phẳng cho TBMT / KQLCNT / KHLCNT |
| `src/clean/` | `normalize.py`, `dedupe.py`, `integrate.py`, `quality.py` | chuẩn hoá ngày/tiền/tỉnh (63 → 34), dedupe theo `ma_tbmt` giữ bản ở bước xa nhất, join KHLCNT, lọc NSNN, báo cáo chất lượng |
| `src/eda/` | `insights.py`, `plots.py` | số liệu insight + 8 biểu đồ EDA |
| `src/model/` | `features.py`, `regression.py`, `anomaly.py`, `clustering.py`, `network.py` | Linear Regression / Random Forest / LightGBM; Rule-based / Isolation Forest / LOF; K-means; Louvain |
| `src/report/` | `build_report.py` | gom số liệu + hình vào `reports/report_assets.md` |
| gốc | `run_pipeline.py`, `config/config.yaml`, `readme.txt`, `pytest.ini` | CLI `crawl/parse/clean/eda/model/report/all`; cấu hình tập trung |

- `config/province_mapping.csv` (63 tỉnh cũ → 34 tỉnh mới) vì sáp nhập hành chính 01/07/2025: giữ 2 cột `tinh_thanh_63` / `tinh_thanh_34`.
- Chọn **time-based split** (6 tháng cuối làm test) và `use_bidder_count: false` để tránh leakage, vì số nhà thầu chỉ biết sau mở thầu.

**Việc 7. Viết unit test** (`d6023a2`)
- `test_anomaly`, `test_clean`, `test_crawler` (resumability bằng client giả), `test_es_query`, `test_normalize` + `conftest.py`.

**Việc 8. Chốt D3 — định nghĩa "vốn ngân sách nhà nước"** (`13a1f74`)
- Quyết định: dùng proxy `planType ∈ {DTPT, TX, DTMS}`, loại `KHAC` (~18% mẫu, chủ yếu vốn tự có của DNNN và nguồn xã hội hoá). Không recon API chi tiết.
- Code: thêm cột heuristic `dau_hieu_von_vay` (từ khoá ODA, vốn vay, WB, ADB, JICA, trái phiếu…) để phân tích độ nhạy; sửa `normalize.py`, `integrate.py`, `quality.py`, `test_normalize.py`, `requirements.md`.

---

### 02/10/2026 — Gate Phase 0 và chuẩn bị full crawl

**Việc 9. Nhóm chốt D1, D2, D4, D5 → mở gate** (`dd4966e`, `e9d31cf`, `59c9abb`, `dcd0956`, `bbd2370`)

| Quyết định | Chốt |
|---|---|
| D1 — dùng endpoint trang chủ (không reCAPTCHA) ở quy mô lớn | Phương án **A** (`approved_option: "A"`), giữ ~1 request/2s, circuit breaker dừng khi 403/challenge |
| D2 — phạm vi & tốc độ | Chiến lược **S2**, 1 tiến trình, 2 đợt: 24 tháng rồi mở rộng 48 tháng; **bắt buộc crawl lại ~3 tháng cuối** trước dataset final |
| D4 — `thoi_gian_thuc_hien_hop_dong` | **Bỏ** khỏi crawl chính (thêm 1 request/gói ≈ gấp 6 lần thời gian) |
| D5 — email liên hệ | Đặt qua biến môi trường `PTVN_CONTACT_EMAIL`, không ghi vào repo |

- Config: `approved_option: "A"`, `months_back: 24`, `extra_filters.kqlcnt = caseKHKQ in [1]` (S2), `user_agent` dùng placeholder `{contact}`.
- `run_pipeline.py`: lệnh `crawl` tự dừng nếu gate đóng hoặc chưa có `PTVN_CONTACT_EMAIL`. Thêm test cho nhánh này.
- Cập nhật `phase0_feasibility.md` §1, §6, §8; `team-plan.md` (thêm việc "crawl lại 3 tháng cuối" cho Data Lead); `readme.txt`; `quality.py` (ghi chú field D4).

**Việc 10. Sự cố: unit test chạy crawl thật** (ghi nhận trong `phase0_feasibility.md` §8)
- *Hiện tượng:* ngay sau khi mở gate, test kiểm tra gate vô tình gọi crawl thật ~2 phút (~80 request, TBMT 30/09–02/10), User-Agent còn placeholder.
- *Xử lý:* dừng, sửa test để luôn ép gate đóng (`dd4966e`). Lượng request vẫn đúng rate limit; dữ liệu hợp lệ nên giữ lại. Checkpoint thử được tách ra `data/checkpoint_local_20261002.sqlite` (28 KB).
- *Bài học:* test không bao giờ được phụ thuộc vào config thật của gate.

**Việc 11. Vẽ sơ đồ thiết kế hệ thống** (`59054ae`)
- `docs/diagram_system_design/`: `diagram1_kien_truc_he_thong.png`, `diagram2_luong_tich_hop_du_lieu.png`, `diagram3_luong_crawler.png`.

**Việc 12. Chạy crawl trên workstation** (log `logs/workstation/`)
- Truy cập workstation qua tunnel pinggy (`ssh_tunnel.log`); full crawl (~4 ngày) chạy trên máy đó thay vì máy cá nhân.
- 17:39:41 — chạy thử 1 ngày (01/09/2026): 64 request, 64 OK, 623 bản ghi (32 TBMT + 200 KHLCNT + 391 KQLCNT), 110,8s, 0 lỗi. Xác nhận crawler chạy đúng trên máy này.
- 17:41:49 — bắt đầu full crawl, cửa sổ 02/10/2024 → 02/10/2026, 3 nguồn.

---

### 02–06/10/2026 — Full crawl đợt 1

**Việc 13. Full crawl 24 tháng** (`full_crawl.log`, `crawl_stats_20261002_174150.json`)
- Kết thúc 06/10 22:10:26. Tiến trình **không bị ngắt** giữa chừng (một lần chạy liên tục).

| Chỉ số | Giá trị |
|---|---|
| Thời gian | 361.716 s ≈ **100,5 giờ ≈ 4,2 ngày** (khớp ước lượng S2 24 tháng = 4,2 ngày) |
| Request | 206.621 · thành công 206.621 · **lỗi 0 · retry 0** · toàn bộ HTTP 200 |
| Bản ghi | 2.056.114 |
| Dung lượng response | 2.979.981.226 byte (~2,98 GB); sau gzip `data/raw` ≈ 432 MB |
| Tốc độ thực tế | ~1,75 s/request, nằm trong khoảng cấu hình `min_delay_s 1,5 + jitter 0,5` |

- Không có 403/429/challenge; circuit breaker không kích hoạt. Các dòng khớp `403`/`429` trong log chỉ là số bản ghi của ngày đó (vd. "403 records").
- Dữ liệu raw được đưa về máy local (thư mục `data/raw` ghi nhận lúc 12/10 12:47).

---

### 12/10/2026 — Chạy pipeline trên dữ liệu thật

**Việc 14. parse → clean → eda → model → report** (log `*_raw_20261012_*.log`)

| Bước | Thời gian | Thời lượng | Kết quả |
|---|---|---|---|
| `parse` | 12:48:36 | ~66 s | 293.560 TBMT · 960.989 KQLCNT · 802.188 KHLCNT (1.652.881 dòng plan-package) |
| `clean` | 12:50:15 | ~88 s | **1.108.989 gói**; join KHLCNT 96,9%; loại 145.560 gói `KHAC` |
| `eda` | 12:52:54 | ~12 s | 8 biểu đồ EDA |
| `model` | 12:53:12 | ~7 phút 47 s | regression, anomaly, K-means, network (chi tiết §3) |
| `report` | 13:01:01 | ~1 s | `reports/report_assets.md` |

Tổng cộng ~13 phút trên máy cá nhân, không cần PySpark. Ra 12 hình (`fig01`–`fig12`) và 12 bảng trong `reports/tables/`.

**Việc 15. Cập nhật tài liệu** (`6798c5b`, 11:51)
- Thêm `docs/requirements_specification.docx` (777 KB).
- Sửa mục 7 (đạo đức / pháp lý) của `readme.txt` — commit này để sót chữ `li` thừa ở đầu dòng 94, đã gỡ ở bước sau (xem §4 #8).

**Việc 16. Kiểm tra lại test** (12/10)
- `python -m pytest`: **27 passed** trong 23 s, không cần Internet.

**Việc 17. Định danh nhà thầu trúng + sửa lỗi `wins_in_window`** (12/10, chưa commit; xử lý vấn đề #4)

Kiểm tra vấn đề #4 trên `packages.parquet` cho thấy hậu tố tên chỉ là phần nhỏ nhất; có 3 lỗi, xếp theo mức ảnh hưởng:

| Lỗi | Quy mô | Cách sửa |
|---|---|---|
| `wins_in_window` gán lệch dòng: `anomaly_frame` gán kết quả `groupby().rolling()` theo vị trí, nhưng pandas 3.0.6 trả các nhóm theo thứ tự khác với frame | 534.383 gói (50,2%) sai số lần thắng; **269.848 gói (25,3%) sai cờ `repeat_winner`**, chỉ 48,2% số cờ đã xuất là đúng. Tổng số cờ không đổi (260.380) nên tỉ lệ 24,4% trông bình thường | `trailing_count()` trong `src/model/features.py`: đếm bằng `searchsorted` trên trục (nhóm, thời gian), không phụ thuộc thứ tự trả về |
| Khoá nhà thầu không ổn định: (a) 54.624 gói có nhiều mã (liên danh / gói nhiều phần) bị coi chuỗi ghép `A \| B` là một nhà thầu; (b) 15.182 gói của nhà thầu chưa đăng ký mang UUID / chuỗi hex sinh mới cho từng kết quả nên không bao giờ lặp | `repeat_winner` bị đếm thiếu: 260.380 → 283.168 gói (24,4% → 26,6%) sau khi sửa | `src/clean/contractors.py`: cột `nha_thau_key`, `so_nha_thau_trung`. Tách từng mã; nhà thầu chưa đăng ký định danh theo tên trong phạm vi một bên mời thầu |
| EDA nhóm theo tên thô: 4.417 mã được ghi dưới nhiều tên; ngược lại 1.146 tên dùng chung cho nhiều mã (vd 25 đơn vị cùng tên "Trung tâm Quan trắc tài nguyên và môi trường") | VNPT 3.340 → 3.351 gói khi gộp 12 cách viết; hậu tố `(LOẠI HÌNH DOANH NGHIỆP: …)` có ở 3.376 gói, gần như chỉ của VNPT (đó là tên đăng ký chính thức) | fig06, fig08, insight và network nhóm theo `nha_thau_key`; cột `nha_thau_chuan` là tên hiển thị đã gộp khoảng trắng và bỏ chú thích loại hình |

- Tên và mã trong API **không cùng thứ tự** (chỉ 12,5% khớp cùng vị trí, 99,2% khớp ở một vị trí nào đó), nên định danh chỉ dựa vào mã, không ghép tên với mã theo vị trí.
- Thay đổi cách đếm cần nêu trong report: thành viên liên danh / nhà thầu trúng một phần được tính một lần thắng; gói nhiều nhà thầu lấy tín hiệu của nhà thầu lặp lại nhiều nhất. Vì vậy top "số gói trúng" (fig06) có thêm các công ty dược. Top "tổng giá trúng" chỉ tính gói 1 nhà thầu vì giá của gói nhiều nhà thầu không tách được.
- Hạn chế còn lại: 7.910 mã chỉ xuất hiện trong gói nhiều nhà thầu nên chưa có tên hiển thị (bảng network in mã); 1.402 gói của nhà thầu chưa đăng ký trùng tên với một nhà thầu có mã tại cùng bên mời thầu nhưng chưa được gộp.
- Chạy lại `clean → eda → model → report` (~11 phút). Test: **50 passed** (thêm `tests/test_contractors.py`, test hồi quy cho lỗi lệch dòng). Số liệu §3.2, §3.5, §3.6 bên dưới đã cập nhật.

---

## 3. Kết quả

### 3.1. Dataset

| Chỉ số | Giá trị |
|---|---|
| Phạm vi thời gian | 02/10/2024 – 02/10/2026 (24 tháng) |
| Bản ghi notify thô (TBMT + KQLCNT) | 1.254.549 |
| Bị loại do trùng `ma_tbmt` | 0 |
| KHLCNT sau dedupe | 802.186 (loại 2) |
| Tỉ lệ join KHLCNT | 96,9% |
| Bị loại vì không phải NSNN (`planType = KHAC`) | 145.560 |
| **Gói thầu cuối cùng** | **1.108.989** (56 cột) |
| Đã có kết quả (giá trúng) | 1.070.058 (96,5%) |
| Có dấu hiệu vốn vay (heuristic) | 504 |
| Tổng giá gói thầu | ≈ 3.488.140 tỷ đồng |

**Field thiếu:** `thoi_gian_thuc_hien_hop_dong` 100% (do D4); `ten_du_an` 3,3%; `tinh_thanh` 2,8% (chủ yếu "Toàn quốc" 4.754 gói và "Ngoài lãnh thổ Việt Nam" 571 gói); `so_nha_thau_tham_du` 2,1%; các field còn lại 0%.

**Bất hợp lệ / outlier (được gắn cờ):** `gia_trung_thau ≤ 0`: 106 · `gia_trung_thau > gia_goi_thau`: 2.450 · tỉ lệ < 0,3: 3.787 · tỉ lệ > 1,2: 839.

### 3.2. EDA

- **Địa lý:** top 5 tỉnh (Hà Nội, Hồ Chí Minh, Hải Phòng, Hưng Yên, Ninh Bình) chiếm 38,0% số gói.
- **Lĩnh vực:** Tư vấn 45%, Hàng hoá 25%, Xây lắp 16%, Phi tư vấn 14%.
- **Mùa vụ:** đỉnh tháng 12/2025; tháng 12 chiếm 12,3% số gói.
- **Hình thức:** Chỉ định thầu 74% số gói nhưng chỉ 12,2% tổng giá trị; Cạnh tranh 24%.
- **Tiết kiệm:** 68,8% gói tiết kiệm < 1%; trung vị Cạnh tranh 1,9%, Chỉ định thầu 0,0%.
- **Cạnh tranh:** trong đấu thầu cạnh tranh, 51,9% gói chỉ có 1 nhà thầu; tiết kiệm trung vị 0,7% (1 nhà thầu) so với 7,0% (≥ 2 nhà thầu).
- **Tập trung:** 13,0% trong 30.839 bên mời thầu (≥ 5 gói) có HHI > 0,25. Nhà thầu có mặt trong nhiều gói trúng nhất: VNPT (3.506 gói, tính cả liên danh / trúng một phần).

### 3.3. Kiểm tra độ lệch dữ liệu ở các tháng gần đây (yêu cầu của `team-plan.md`)

Tỉ lệ gói có kết quả theo tháng đăng TBMT (tính từ `packages.parquet`):

| Giai đoạn | % gói có KQ |
|---|---|
| 10/2024 – 07/2026 | 95,9% – 97,9% (ổn định) |
| 08/2026 | 95,6% |
| **09/2026** | **88,8%** |
| **10/2026 (đến 02/10)** | **88,9%** |

→ Đúng như cảnh báo ở D2: gói đăng gần ngày crawl chưa có KQ, sẽ thiếu vĩnh viễn nếu không crawl lại. **Cần crawl lại từ ~01/07/2026** (dư một chút so với 3 tháng để chắc).

### 3.4. Bài toán 1 — dự đoán % tiết kiệm

300.000 dòng được lấy mẫu; train 203.694, test 96.306 (đăng sau 02/04/2026). Feature: `linh_vuc, tinh_thanh, hinh_thuc_raw, plan_type, phuong_thuc, log_gia_goi, nam, thang_trong_nam, qua_mang`.

| Model | test RMSE | test MAE | test R² | cv R² (5-fold) |
|---|---|---|---|---|
| Median (tham chiếu) | 0,0615 | **0,0231** | −0,162 | −0,145 |
| Linear Regression | 0,0545 | 0,0302 | 0,087 | 0,166 |
| Random Forest | 0,0532 | 0,0277 | 0,128 | 0,220 |
| **LightGBM** | **0,0525** | 0,0268 | **0,153** | **0,228** |

- Feature quan trọng nhất: `log_gia_goi` (RF 0,31 · LightGBM 0,31), `tinh_thanh` (0,16 · 0,24), `hinh_thuc_raw`, `qua_mang`, `thang_trong_nam`.
- **Đọc kết quả cho đúng:** mô hình thắng baseline về RMSE và R², nhưng **MAE của baseline "luôn đoán trung vị" (0,0231) vẫn thấp hơn cả 3 mô hình**. Lý do: phân phối tiết kiệm lệch mạnh, 68,8% gói < 1%, và baseline đoán gần 0 nên đúng với đa số gói. R² 0,15 là mức khiêm tốn, cần nói rõ trong report, không nên trình bày như mô hình "dự đoán tốt".

### 3.5. Bài toán 2 — điểm bất thường thống kê

1.065.432 gói có kết quả; mỗi thuật toán gắn cờ top 5% = 53.272 gói.

| Số thuật toán đồng thuận | Số gói |
|---|---|
| 0 | 921.590 |
| 1 | 128.771 |
| 2 | 14.168 |
| 3 | **903** |

| Cặp | Jaccard (gói bị gắn cờ) | Spearman (điểm) |
|---|---|---|
| Rule-based ↔ Isolation Forest | 0,058 | 0,072 |
| Rule-based ↔ LOF | 0,017 | −0,076 |
| Isolation Forest ↔ LOF | 0,095 | 0,276 |

- Số liệu sau khi sửa ở Việc 17. So với lần chạy trước (1.173 gói đồng thuận 3/3): 596 gói có mặt ở cả hai lần; tập gắn cờ của từng thuật toán trùng 80,5% (rule-based), 83,6% (Isolation Forest), 64,4% (LOF). `repeat_winner` = 26,6% số gói.
- Ba thuật toán **ít trùng nhau**: mỗi cái bắt một kiểu tín hiệu khác. Trong tập rule-based gắn cờ, 100% là gói có 1 nhà thầu; trong tập LOF gắn cờ, 74,6% là chỉ định thầu (so với 76,0% toàn bộ), nên LOF gần như không chọn theo tín hiệu cạnh tranh (nhiều khả năng bắt các gói có đặc trưng hiếm; chưa kiểm chứng).
- Top 10 gói thầu (đồng thuận 3/3) đều thuộc **2 cặp bên mời thầu–nhà thầu** (không đổi so với lần chạy trước), mỗi cặp khoảng 15 gói của bên mời thầu đó trong 180 ngày, tỉ lệ giá trúng ≈ 99–100%. Chi tiết trong `reports/report_assets.md`, `reports/tables/anomaly_top.csv`.
- ⚠️ Đây là **điểm bất thường thống kê**, không phải kết luận vi phạm. Bước *đối chiếu định tính với tin thanh tra/kiểm toán công khai* vẫn để trống (R5 bổ sung).

### 3.6. Tuỳ chọn — K-means và network

- **K-means:** k tốt nhất = 3, silhouette 0,735. Hai cụm lớn: 233.043 gói (hàng hoá, cạnh tranh, tiết kiệm trung vị 1,9%) và 837.014 gói (tư vấn, 97,1% chỉ định thầu). **Cụm thứ 3 chỉ có 1 gói** (xem vấn đề #3).
- **Network (Louvain):** 184.091 nút, 690.357 cạnh, 1.752 cộng đồng, trong đó 178 cộng đồng có ≥ 2 bên mời thầu (trước Việc 17: 230.403 nút, 593.576 cạnh; nút giảm vì chuỗi ghép và UUID không còn là nút riêng, cạnh tăng vì mỗi thành viên liên danh có cạnh riêng). Nhiều cộng đồng "khép kín" (tỉ lệ khép kín 1,0), điển hình: 1 nhà thầu cung cấp cho nhiều trường học / chi cục cùng địa bàn.

---

## 4. Vấn đề còn mở / việc cần làm

| # | Vấn đề | Mức | Hướng xử lý |
|---|---|---|---|
| 1 | KQ bị thiếu ở 09–10/2026 (88,8% so với ~97%) | **Cao**, chặn dataset final | Xoá checkpoint của các ngày từ ~01/07/2026 trong `data/checkpoint.sqlite`, crawl lại với `--start/--end`; `dedupe_notices` tự giữ bản ở bước xa nhất. Sau đó chạy lại `clean` và kiểm tra lại bảng §3.3 |
| 2 | Chưa mở rộng 24 → 48 tháng (D2 đợt 2) | Trung bình | Đổi `months_back: 48`, chạy lại `crawl`; checkpoint bỏ qua phần đã có (~4,2 ngày nữa, có thể tách 2 tiến trình theo `--sources`). Cân nhắc làm cùng lượt với #1 |
| 3 | K-means có 1 gói với `tiet_kiem_pct ≈ −4,29×10¹²` làm hỏng cụm và đẩy silhouette lên 0,735 | Trung bình | Loại các gói bị gắn cờ outlier (`ty_le` ngoài [0,3; 1,2], `gia_trung_thau ≤ 0`) trước khi K-means; chạy lại và báo silhouette mới |
| 4 | ~~Tên nhà thầu còn hậu tố kiểu `(LOẠI HÌNH DOANH NGHIỆP: CÔNG TY TNHH)` (thấy ở top nhà thầu, 3.340 gói)~~ | — | ✅ Đã sửa 12/10/2026 (chưa commit), xem Việc 17. Hậu tố chỉ là phần nhỏ; lỗi chính là `wins_in_window` gán lệch dòng |
| 5 | Outlier giá chưa quyết định xử lý (2.450 gói giá trúng > giá gói; 106 gói giá ≤ 0) | Thấp–TB | Xác định đây là lỗi nhập liệu hay có thật; ghi quyết định vào `config.yaml` (`ratio_outlier_*`) |
| 6 | Regression R² thấp (0,153), baseline trung vị thắng về MAE | Thấp | Thử `target: log_gia_trung`; thử phân loại "có tiết kiệm / không"; ghi rõ hạn chế (thiếu `thoi_gian_thuc_hien`, D4) |
| 7 | Anomaly: 3 phương pháp ít đồng thuận; chưa có đối chiếu định tính | Thấp | R5 tìm vài vụ có tin thanh tra/kiểm toán công khai để đối chiếu; trình bày theo "tín hiệu" chứ không "vi phạm" |
| 8 | ~~`readme.txt` dòng 94 có `li` thừa (commit `6798c5b`) và ghi "19 test" trong khi thực tế 27 test~~ | — | ✅ Đã sửa 12/10/2026 (chưa commit) |
| 9 | Written report chưa viết | — | Dùng `reports/report_assets.md` + §3 nhật ký này làm nguyên liệu |

---

## 5. Nguồn số liệu & cách tái lập

| Số liệu | Nằm ở đâu |
|---|---|
| Khảo sát Phase 0 | `reports/phase0/probe_results.json`, `reports/phase0_feasibility.md` |
| Thống kê crawl | `logs/workstation/crawl_stats_20261002_174150.json`, `logs/workstation/full_crawl.log` |
| Parse / clean / model | `logs/parse_raw_*.log`, `clean_raw_*.log`, `model_raw_*.log` (12/10) |
| Chất lượng dữ liệu | `reports/data_quality.md` |
| Kết quả EDA, model, anomaly | `reports/report_assets.md`, `reports/tables/*.csv|json`, `reports/figures/*.png` |
| Tỉ lệ có KQ theo tháng (§3.3) | tính trực tiếp từ `data/processed/packages.parquet` (12/10) |

```bash
# Tái lập từ dữ liệu raw đã có
python run_pipeline.py all                 # parse → clean → eda → model → report (~13 phút)

# Crawl (cần đặt email liên hệ; gate đã mở: approved_option "A")
$env:PTVN_CONTACT_EMAIL="ten@sis.hust.edu.vn"
python run_pipeline.py crawl [--sources tbmt,kqlcnt,khlcnt] [--start YYYY-MM-DD --end YYYY-MM-DD]

# Kiểm thử, không cần Internet
python -m pytest                           # 50 passed
```

## 6. Lịch sử commit

| Ngày | Commit | Nội dung |
|---|---|---|
| 25/09 | `cfcbe2c` | Tài liệu ban đầu, requirements, team-plan |
| 25/09 | `61b5891` | Crawler: checkpoint, client, es_query, raw_store, sources |
| 25/09 | `2220eb6` | config, logs, text helper |
| 25/09 | `d85b98d` | scripts: generate_fixture, make_zip, phase0_probe |
| 27/09 | `3333914` | clean: dedupe, integrate, normalize, quality |
| 27/09 | `ec1baae` | eda: insights, plots |
| 27/09 | `8281fe1` | model: anomaly, clustering, network, regression, features |
| 27/09 | `f74bf73` | parse: records |
| 27/09 | `d1216c3` | report: build_report |
| 27/09 | `d6023a2` | unit tests |
| 27/09 | `10a2a69` | probe_results.json, sample data, province_mapping |
| 27/09 | `5c39c7c` | run_pipeline, config, readme.txt, .gitignore, pytest.ini |
| 27/09 | `13a1f74` | D3: proxy nguồn vốn, heuristic `dau_hieu_von_vay` |
| 02/10 | `dd4966e` | quality notes D4, test gate luôn đóng |
| 02/10 | `e9d31cf` | config: contact email, `months_back` |
| 02/10 | `59c9abb` | Docs: gate decision D1–D5 |
| 02/10 | `59054ae` | 3 sơ đồ thiết kế hệ thống |
| 02/10 | `dcd0956` | Email liên hệ qua biến môi trường + validate trong pipeline |
| 02/10 | `bbd2370` | Docs: biến môi trường, User-Agent |
| 12/10 | `6798c5b` | Thêm `requirements_specification.docx`, sửa mục đạo đức/pháp lý |
