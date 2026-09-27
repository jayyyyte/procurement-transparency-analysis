# Requirement Specification: Phân tích Minh bạch Đấu thầu Đầu tư công Việt Nam

**Project type:** Capstone project — môn Introduction to Data Science (IT4142E), SOICT - HUST
**Doc version:** 1.1
**Ngày tạo:** 2026-09-25

---

## 1. Project Overview

Xây dựng pipeline end-to-end: crawl dữ liệu đấu thầu công khai từ Hệ thống mạng đấu thầu quốc gia (`muasamcong.mpi.gov.vn`), làm sạch & tích hợp thành dataset có cấu trúc, phân tích khám phá (EDA), và xây model dự đoán/anomaly detection trên các gói thầu sử dụng vốn ngân sách nhà nước (NSNN) — gồm chi đầu tư công và chi thường xuyên, xem mục 3.5.

**Ràng buộc bắt buộc của môn học (không thương lượng):**
- Dữ liệu phải tự crawl, **không được dùng dataset có sẵn** (Kaggle, data.gov, v.v.)
- Deliverables cuối cùng: source code (zip), `readme.txt` (hướng dẫn setup/chạy), written report

---

## 2. Scope

### 2.1 In Scope
- Crawl 3 loại thông tin trên hệ thống mạng đấu thầu quốc gia:
  - **TBMT** — Thông báo mời thầu
  - **KHLCNT** — Kế hoạch lựa chọn nhà thầu
  - **KQLCNT** — Kết quả lựa chọn nhà thầu
- Phạm vi: toàn quốc, tất cả lĩnh vực, **gói thầu dùng vốn ngân sách nhà nước** (đầu tư công + chi thường xuyên, định nghĩa ở mục 3.5), khoảng thời gian **3-4 năm gần nhất** (mặc định: 2022-09 → 2026-09, để cấu hình được qua tham số, không hard-code) — kéo dài để có dữ liệu lớn hơn cho phân tích trend & modeling
- Data cleaning, chuẩn hoá, join 3 nguồn theo mã gói thầu/mã dự án
- EDA + visualization
- Modeling: (a) dự đoán giá trúng thầu / % tiết kiệm so với giá gói thầu (regression), (b) phát hiện gói thầu có tín hiệu bất thường về cạnh tranh (anomaly/rule-based scoring) — chi tiết thuật toán ở mục 7
- Written report tự động sinh phần số liệu/biểu đồ (không cần tự sinh toàn bộ văn bản báo cáo)

### 2.2 Out of Scope
- Không crawl dữ liệu từ mạng xã hội, group Facebook, hay nguồn cần đăng nhập
- Không thực hiện bất kỳ hành động nào có thể vi phạm ToS/pháp luật (không bypass CAPTCHA nếu có, không login giả mạo)
- Không đưa ra kết luận buộc tội/gian lận — chỉ báo cáo dưới dạng "tín hiệu bất thường về mặt thống kê"
- Dashboard/web app thời gian thực — output là notebook/script + report, không phải sản phẩm production
- Gói thầu dùng vốn tự có của doanh nghiệp nhà nước hoặc nguồn xã hội hoá (loại kế hoạch KHAC), vốn tư nhân, dự án PPP và lựa chọn nhà đầu tư. Gói vốn vay ODA / trái phiếu Chính phủ **không** bị loại riêng (chúng thuộc NSNN, xem mục 3.5)

### 2.3 Phased Delivery Plan — **quan trọng, có gate giữa các phase**

| Phase | Nội dung | Điều kiện để sang phase tiếp |
|---|---|---|
| **Phase 0 — Feasibility POC** | Crawl thử ~50-100 record từ 1 loại (TBMT), xác minh: trang có JS-render không, cần login không, cấu trúc URL/pagination, các field thực tế lấy được | Crawl thành công ≥80% field mong muốn từ POC. Nếu không khả thi với scope hiện tại → báo lại để điều chỉnh (giảm phạm vi tỉnh/lĩnh vực) |
| **Phase 1 — Full Crawl** | Crawl toàn bộ TBMT + KHLCNT + KQLCNT theo phạm vi đã chốt | Dataset thô lưu đầy đủ, có log crawl (số record, lỗi, thời gian) |
| **Phase 2 — Clean & Integrate** | Chuẩn hoá, dedupe, join 3 bảng | Dataset sạch, schema rõ ràng, có data quality report (% thiếu field, outlier) |
| **Phase 3 — EDA** | Phân tích phân bố theo tỉnh/ngành/thời gian/hình thức lựa chọn nhà thầu | Bộ biểu đồ + insight summary |
| **Phase 4 — Modeling** | Regression giá trúng thầu + anomaly scoring (xem mục 7) | Model + metrics đánh giá (không chỉ train, phải có validation) |
| **Phase 5 — Packaging** | Đóng gói source code, viết README, chuẩn bị số liệu cho written report | Chạy lại được từ đầu theo README trên máy sạch |

⚠️ **Claude Code không được skip Phase 0.** Nếu crawl thực tế khó hơn dự kiến (JS-heavy, rate-limit gắt, cấu trúc khác mô tả bên dưới), dừng lại và báo cáo thay vì cố gắng ép chạy toàn bộ scope.

---

## 3. Data Sources

### 3.1 Nguồn chính
`https://muasamcong.mpi.gov.vn` — Hệ thống mạng đấu thầu quốc gia (Bộ Kế hoạch và Đầu tư quản lý)

### 3.2 Đã xác minh (qua khảo sát sơ bộ)
- Trang chủ có các block danh sách dạng bảng cho từng loại: TBMT, KHLCNT, KQLCNT, kết quả lựa chọn nhà đầu tư, v.v.
- Mỗi block có nút "Xem thêm" → có cơ chế phân trang/xem danh sách đầy đủ
- Dữ liệu hiển thị dạng text có cấu trúc (tên gói thầu, bên mời thầu, thời điểm) — gợi ý có thể server-render, nhưng **chưa xác nhận chắc chắn** việc trang chi tiết và trang tìm kiếm nâng cao có cần JS render hay không

### 3.3 CẦN CLAUDE CODE VERIFY TRƯỚC (chưa biết, không được giả định)
- [ ] Trang tìm kiếm nâng cao dùng GET (URL param) hay POST (session/form state)?
- [ ] Có bị chặn bởi CAPTCHA ở bước tìm kiếm/xem chi tiết không?
- [ ] Trang chi tiết từng gói thầu có URL pattern ổn định (crawl theo ID) hay chỉ truy cập qua click từ danh sách?
- [ ] Các field mong muốn (giá gói thầu, giá trúng thầu, số nhà thầu tham dự, hình thức lựa chọn nhà thầu) có thực sự xuất hiện ở trang chi tiết không, hay chỉ có ở KQLCNT?
- [ ] Rate limit/chặn IP nếu request tần suất cao — cần test với delay hợp lý trước

### 3.4 Data Fields cần thu thập (mục tiêu, có thể điều chỉnh sau Phase 0)

| Field | Nguồn (TBMT/KHLCNT/KQLCNT) | Ghi chú |
|---|---|---|
| `ma_goi_thau` | Cả 3 | Khóa để join |
| `ten_goi_thau` | TBMT, KQLCNT | |
| `ten_du_an` | KHLCNT | |
| `chu_dau_tu` | KHLCNT | |
| `ben_moi_thau` | TBMT, KQLCNT | |
| `tinh_thanh` | Suy ra từ địa chỉ bên mời thầu hoặc field trực tiếp nếu có | |
| `linh_vuc` | TBMT/KHLCNT | Xây lắp/Hàng hóa/Tư vấn/Phi tư vấn/Hỗn hợp |
| `nguon_von` | KHLCNT | API không có field này → proxy `planType`. **Lọc giữ DTPT, TX, DTMS; loại KHAC** (mục 3.5) |
| `hinh_thuc_lua_chon_nha_thau` | TBMT | Đấu thầu rộng rãi/Chỉ định thầu/Chào hàng cạnh tranh/... |
| `gia_goi_thau` | KHLCNT | |
| `gia_trung_thau` | KQLCNT | |
| `nha_thau_trung_thau` | KQLCNT | |
| `so_nha_thau_tham_du` | KQLCNT (nếu có) | Field quan trọng cho anomaly detection |
| `thoi_diem_dong_mo_thau` | TBMT | |
| `thoi_gian_thuc_hien_hop_dong` | KQLCNT | |
| `ngay_dang_tai` | Cả 3 | Dùng cho time-series/trend |

### 3.5 Phạm vi thời gian & địa lý
- Thời gian: 3-4 năm gần nhất (mặc định 48 tháng tính từ ngày chạy crawler — **để config qua CLI arg/config file**, không hard-code ngày)
- Địa lý: toàn quốc
- Lĩnh vực: tất cả
- Nguồn vốn: **giữ gói thầu dùng vốn ngân sách nhà nước**, cả chi đầu tư lẫn chi thường xuyên (đã chốt ở gate Phase 0, quyết định D3):
  - API danh sách không có field nguồn vốn, nên dùng loại kế hoạch `planType` của KHLCNT làm proxy.
  - **DTPT** (đầu tư phát triển) = đầu tư công theo nghĩa hẹp. Gồm mọi nguồn cân đối qua NSNN: ngân sách trung ương, ngân sách địa phương, trái phiếu Chính phủ, vốn vay ODA / vay ưu đãi (các khoản Nhà nước vay được hạch toán vào NSNN).
  - **TX** (chi thường xuyên) và **DTMS** (dự toán mua sắm) = chi thường xuyên của NSNN, không phải đầu tư công nhưng vẫn là tiền ngân sách và vẫn đấu thầu công khai. Giữ lại để dataset lớn hơn; `plan_type` là feature của model nên model vẫn phân biệt được hai nhóm.
  - **KHAC**: loại. Mẫu Phase 0 cho thấy nhóm này chủ yếu là vốn tự có của doanh nghiệp nhà nước (điện lực, ngân hàng, cảng) và nguồn xã hội hoá ở trường học (sữa bán trú, căn tin).
  - "Đầu tư công" trong tên đề tài được hiểu theo nghĩa rộng là đấu thầu dùng vốn NSNN. Muốn chỉ lấy đầu tư công nghĩa hẹp: đặt `clean.nsnn_plan_types: [DTPT]`.
  - **Giới hạn đã biết:** không tách được gói vốn vay ODA / trái phiếu khỏi DTPT vì thiếu field nguồn vốn. Cột heuristic `dau_hieu_von_vay` (từ khoá ODA, vốn vay, WB, ADB, JICA, trái phiếu… trong tên dự án/gói thầu) dùng cho EDA và phân tích độ nhạy, không dùng để lọc. Gói ODA áp dụng quy định đấu thầu của nhà tài trợ có thể không được đăng trên hệ thống.

> ⚠️ Lưu ý volume: toàn quốc + tất cả lĩnh vực + 36-48 tháng + 3 loại thông tin nhiều khả năng ra **hàng trăm nghìn đến cả triệu record** — lớn hơn đáng kể so với bản trước. Nếu Phase 0 cho thấy tốc độ crawl quá chậm để hoàn thành trong timeline, **báo cáo lại thay vì tự ý cắt giảm scope** — đây là quyết định cần thảo luận với chủ dự án. Với volume này, cân nhắc ưu tiên phương án lưu trữ dạng Parquet + xử lý bằng PySpark ngay từ Phase 1 thay vì để tới lúc pandas không kham nổi.

---

## 4. Functional Requirements

**FR-1 — Crawler module**
- Input: danh sách category cần crawl (TBMT/KHLCNT/KQLCNT), khoảng thời gian. Site không hỗ trợ filter nguồn vốn server-side (Phase 0), nên lọc NSNN làm ở bước clean
- Output: raw HTML lưu lại (bắt buộc — để không phải crawl lại khi đổi logic parse) + file log (số request, lỗi, retry)
- Cơ chế: rate limiting cấu hình được (mặc định thận trọng, vd 1 request/1-2s), retry với backoff, resumable (lưu checkpoint để chạy lại không crawl trùng)
- Tôn trọng `robots.txt` của domain

**FR-2 — Storage & Schema**
- Raw layer: HTML/JSON thô theo từng batch, có timestamp
- Structured layer: theo schema mục 3.4, lưu dạng file (Parquet/CSV) hoặc SQLite — Claude Code đề xuất phương án phù hợp với volume thực tế sau Phase 0

**FR-3 — Cleaning & Integration**
- Chuẩn hoá: định dạng ngày tháng, tiền tệ (VNĐ), tên tỉnh/thành (dùng mapping chuẩn 63 tỉnh thành hoặc theo đơn vị hành chính hiện hành)
- Dedupe theo `ma_goi_thau`
- Join TBMT + KHLCNT + KQLCNT theo `ma_goi_thau`/`ten_du_an`
- Data quality report: % record thiếu field quan trọng, số outlier phát hiện

**FR-4 — EDA & Visualization**
- Phân bố gói thầu theo tỉnh, theo lĩnh vực, theo thời gian (trend theo tháng/quý)
- Tỷ lệ các hình thức lựa chọn nhà thầu (đấu thầu rộng rãi vs chỉ định thầu vs khác)
- Phân bố % chênh lệch giá trúng thầu / giá gói thầu
- Top nhà thầu theo số gói thầu thắng / tổng giá trị trúng thầu

**FR-5 — Modeling**
- Model 1 (regression): dự đoán giá trúng thầu hoặc % tiết kiệm, dựa trên đặc trưng gói thầu (lĩnh vực, giá gói thầu, tỉnh, hình thức lựa chọn nhà thầu...). Cần train/test split, báo cáo metric (RMSE/MAE/R²)
- Model 2 (anomaly/risk scoring): kết hợp nhiều tín hiệu (số nhà thầu tham dự = 1, % giá trúng/giá gói bất thường cao, 1 nhà thầu thắng liên tiếp nhiều gói trong thời gian ngắn tại cùng bên mời thầu). Trình bày kết quả dưới dạng **"điểm bất thường thống kê"**, không kết luận vi phạm/gian lận
- Danh sách thuật toán cụ thể cần thử & so sánh cho từng model: xem **mục 7 — Algorithms to be used**
- Optional (nếu còn thời gian): network analysis (`networkx`) — đồ thị chủ đầu tư ↔ nhà thầu để tìm cụm bất thường

**FR-6 — Reporting output**
- Sinh sẵn các bảng số liệu, biểu đồ (file ảnh/HTML) theo cấu trúc written report của môn học: giới thiệu bài toán & dataset, phương pháp, kết quả đánh giá, thành phần code chính, khó khăn & hướng giải quyết

---

## 5. Non-Functional Requirements

- **Politeness:** rate limit cấu hình được, User-Agent rõ ràng, tôn trọng robots.txt
- **Resumability:** crawl có thể dừng/chạy lại mà không mất tiến độ hoặc crawl trùng
- **Reproducibility:** `requirements.txt` (hoặc `pyproject.toml`), README mô tả rõ setup + cách chạy từng bước (crawl → clean → EDA → model)
- **Logging:** log đầy đủ cho crawler (bắt buộc để debug khi site thay đổi cấu trúc) và cho model training
- **Scalability (optional, nếu volume thực tế lớn):** cân nhắc dùng PySpark cho bước cleaning/aggregation nếu dataset đủ lớn để làm nổi bật kỹ thuật big data (liên hệ Lecture 8 của môn học) — không bắt buộc nếu volume vừa phải, pandas là đủ

---

## 6. Suggested Tech Stack (đề xuất, Claude Code có thể điều chỉnh)

- Crawl: Python `requests` + `BeautifulSoup`; dùng `Selenium`/`Playwright` **chỉ khi Phase 0 xác nhận cần JS render**
- Storage: SQLite (đơn giản, query được) hoặc Parquet nếu volume lớn
- Cleaning/EDA: `pandas`, `matplotlib`/`seaborn`
- Modeling: `scikit-learn` (xem mục 7 cho danh sách đầy đủ thuật toán dự kiến so sánh)
- Optional: `networkx` (network analysis), `pyspark` (nếu cần scale)

---

## 7. Algorithms to be used (So sánh nhiều thuật toán/mô hình)

Tiêu chí chấm điểm capstone bao gồm "sự phù hợp & chất lượng của phương pháp được chọn" và "sự chặt chẽ trong đánh giá thực nghiệm" (slide 10 đề bài). Vì vậy mỗi bài toán ML **phải thử ít nhất 2-3 thuật toán và so sánh bằng metric cụ thể** — không chỉ chọn 1 thuật toán rồi dừng.

### 7.1 Bài toán 1 — Dự đoán giá trúng thầu / % tiết kiệm (Regression)

| Thuật toán | Vai trò | Ghi chú |
|---|---|---|
| Linear Regression | Baseline | Đơn giản, dễ diễn giải hệ số ảnh hưởng |
| Random Forest Regressor | Model chính | Xử lý tốt quan hệ phi tuyến, categorical feature |
| Gradient Boosting (XGBoost/LightGBM) | Model nâng cao (optional nếu còn thời gian) | Thường cho kết quả tốt hơn Random Forest trên tabular data |

- **Input features:** lĩnh vực, giá gói thầu, tỉnh/thành, hình thức lựa chọn nhà thầu, nguồn vốn (proxy: loại kế hoạch DTPT/TX/DTMS), thời gian thực hiện hợp đồng
- **Metric so sánh:** RMSE, MAE, R² trên tập test (train/test split hoặc k-fold cross-validation) — trình bày bảng so sánh 3 model cạnh nhau
- **Feature importance** (từ Random Forest/Gradient Boosting) dùng để giải thích yếu tố ảnh hưởng giá trúng thầu — có giá trị cho phần "kết luận mới" trong written report

### 7.2 Bài toán 2 — Phát hiện gói thầu có tín hiệu bất thường (Anomaly / Risk Scoring)

| Thuật toán | Vai trò | Ghi chú |
|---|---|---|
| Rule-based composite score | Baseline, dễ diễn giải | Kết hợp tín hiệu: số nhà thầu tham dự = 1, % chênh giá bất thường, 1 nhà thầu thắng liên tiếp |
| Isolation Forest | Model chính (unsupervised) | Không cần label — phù hợp vì không có ground truth "vi phạm" |
| Local Outlier Factor (LOF) | Model so sánh (optional) | Đối chiếu kết quả với Isolation Forest để tăng độ tin cậy |

- **Vì không có label thật**, đánh giá bằng: (a) mức độ đồng thuận giữa các thuật toán — gói thầu bị nhiều thuật toán cùng gắn cờ đáng tin hơn, (b) đối chiếu định tính một số case với tin tức thanh tra/kiểm toán công khai (nếu tìm được) để làm bằng chứng gián tiếp
- Kết quả chỉ trình bày dưới dạng **"điểm bất thường thống kê"**, không kết luận vi phạm/gian lận (đã nêu ở mục 2.2, FR-5)

### 7.3 Optional — Kỹ thuật bổ sung nếu còn thời gian (Lecture 10+11)

| Thuật toán | Ứng dụng |
|---|---|
| K-means clustering | Phân khúc loại gói thầu/nhà thầu theo đặc trưng |
| Network analysis (`networkx`, community detection) | Phát hiện cụm chủ đầu tư ↔ nhà thầu bất thường |

---

## 8. Deliverables (map với yêu cầu môn học)

| Yêu cầu môn học (slide 9) | Tương ứng trong project này |
|---|---|
| Source code (1 file zip) | Toàn bộ code crawler + cleaning + EDA + modeling |
| `readme.txt` | Hướng dẫn setup, thứ tự chạy từng script, cách reproduce từ đầu |
| Giới thiệu bài toán & dataset | Từ mục 1, 3 doc này |
| Chi tiết phương pháp | Từ FR-3, FR-4, FR-5, mục 7 |
| Kết quả đánh giá, kết luận mới | Output Phase 3-4, bảng so sánh thuật toán ở mục 7 |
| Thành phần chính của code | Kiến trúc module (crawler/cleaner/eda/model) |
| Khó khăn & hướng giải quyết | Bắt buộc note lại các vấn đề gặp ở Phase 0 (site structure, rate limit...) |

---

## 9. Risks & Open Questions

1. **Feasibility crawl chưa được verify đầy đủ** — đây là rủi ro lớn nhất, xử lý bằng Phase 0 gate ở mục 2.3
2. **Thiếu ground truth cho anomaly detection** — không có label "vi phạm" chính thức, đánh giá chỉ dựa trên thống kê/threshold/đồng thuận giữa thuật toán, cần nêu rõ hạn chế này trong report
3. **Volume dữ liệu lớn (toàn quốc, 36-48 tháng, 3 loại)** có thể vượt thời gian crawl cho phép trong timeline capstone — nếu Phase 0 cho thấy tốc độ không đủ, cần quay lại thảo luận cắt giảm phạm vi (ví dụ giới hạn theo top N tỉnh có nhiều gói thầu nhất) thay vì tự ý xử lý

---

## 10. Acceptance Criteria

- [ ] Phase 0 hoàn thành với báo cáo rõ ràng: crawl được/không được, field nào lấy được, tốc độ ước tính cho full scope
- [ ] Dataset cuối cùng có schema đúng mục 3.4, có data quality report
- [ ] Ít nhất 5 biểu đồ EDA có insight rõ ràng (không chỉ vẽ cho có)
- [ ] Mỗi bài toán ML (regression, anomaly) có so sánh ít nhất 2 thuật toán theo mục 7, kèm bảng metric — không chỉ implement 1 thuật toán
- [ ] Model regression có train/test split và báo cáo metric
- [ ] Anomaly scoring có ví dụ cụ thể (list vài gói thầu điểm cao nhất) kèm giải thích tín hiệu
- [ ] Toàn bộ pipeline chạy lại được từ đầu theo README trên máy sạch
- [ ] Code có declare rõ mọi thư viện/package bên ngoài đã dùng (yêu cầu bắt buộc của môn học)
