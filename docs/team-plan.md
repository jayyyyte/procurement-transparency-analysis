# Phân chia công việc — Team 5 người (2 Data / 2 AI / 1 DevOps-Cloud)

**Project:** procurement-transparency-vn
**Course:** IT4142E — Data Science, HUST

---

## Nguyên tắc chia việc

Chia theo đúng chuyên môn thay vì chia đều theo module: **Data track** sở hữu toàn bộ pipeline dữ liệu (crawl → clean → schema) và bàn giao dataset sạch cho **AI track** làm EDA sâu + modeling; **DevOps/Cloud** lo hạ tầng & vận hành xuyên suốt cả dự án, không phải chờ tới cuối mới đóng gói.

## Mốc thời gian tổng thể

Dự án chạy xuyên suốt kỳ học (~11-12 tuần làm việc thực tế trong tổng 16 tuần môn học), có 2 mốc chính:

- **Progress Report** — 1 tuần dành riêng để báo cáo tiến độ giữa kỳ (ngày cụ thể: TBA theo lịch lớp). Không phải deadline hoàn thành dự án, chỉ là checkpoint — cần show được: crawl đã chạy được (feasibility đã confirm), dataset draft, EDA sơ bộ.
- **Final Report + Presentation** — 2-3 tuần cuối kỳ. Đây mới là deadline thật cho toàn bộ deliverables (source code, `readme.txt`, written report, slide + demo 15').

Các task dưới đây gắn deadline theo 2 mốc này (và theo tuần tương đối kể từ lúc team bắt đầu làm), thay vì chia cứng theo từng tuần lịch.

---

## Phân vai

| Vai trò | Người phụ trách | Nhiệm vụ chính | Output |
|---|---|---|---|
| **Data Lead** | **Linh** | Schema design (FR-2), cleaning & integration (FR-3), data quality report, chuẩn hoá domain rule, điều phối chung pipeline dữ liệu, **chốt go/no-go sau Phase 0**, tổng hợp report cuối | Schema, cleaning pipeline, data quality report |
| **Data Engineer** | _(điền tên)_ | Implement crawler FR-1 cho cả 3 loại (TBMT/KHLCNT/KQLCNT) | Raw data 3 nguồn, crawl log |
| **AI Engineer — Regression track** | _(điền tên)_ | EDA phần giá/feature (FR-4), implement & so sánh 3 thuật toán regression (mục 7.1) | Model + bảng so sánh metric |
| **AI Engineer — Anomaly track** | _(điền tên)_ | EDA phần tín hiệu bất thường (FR-4), implement & so sánh rule-based/Isolation Forest/LOF (mục 7.2) | Risk scoring model + case cụ thể |
| **DevOps/Cloud** | _(điền tên)_ | Môi trường & reproducibility, infra crawler, storage setup, automation pipeline, đóng gói cuối cùng | Setup scripts, automation, package cuối |

---

## Task & Deadline theo từng vai trò

### Data Lead — Linh
| Task | Deadline | Output |
|---|---|---|
| Thiết kế schema (mục 3.4) | Tuần 1 | Schema doc |
| Go/no-go decision dựa trên kết quả Phase 0 | Ngay sau khi Data Engineer báo kết quả POC (~cuối tuần 1) | Quyết định scope chính thức |
| Cleaning pipeline khung, chạy thử trên data POC | Tuần 1-2 | Pipeline script nháp |
| Clean + join dataset bản draft (đủ để demo tiến độ) | **Trước Progress Report** | Dataset draft + data quality report sơ bộ |
| ⚠️ Yêu cầu Data Engineer crawl lại ~3 tháng cuối (lấy KQ của gói TBMT lúc crawl chưa có KQ, xem `phase0_feasibility.md` §6 D2), kiểm tra % gói có KQ theo tháng không tụt ở cuối | Ngay trước khi chốt dataset final | Dataset không lệch ở các tháng gần đây |
| Hoàn thiện dataset final (full scope), bàn giao AI team | Trước khi AI team bước vào train chính thức (giữa giai đoạn sau Progress Report) | Dataset final |
| Tổng hợp & rà soát written report + slide cuối | Trước Final Report ít nhất vài ngày (buffer) | Report/slide hoàn chỉnh |

### Data Engineer
| Task | Deadline | Output |
|---|---|---|
| Phase 0 POC (crawl thử TBMT/KHLCNT/KQLCNT) | Tuần 1 | Kết quả feasibility |
| Scale crawl full scope (toàn quốc, 36-48 tháng) | Có phần lớn dữ liệu **trước Progress Report**; hoàn tất toàn bộ trước khi bàn giao dataset final cho Data Lead | Raw dataset đầy đủ |
| Fix lỗi crawl phát sinh, bổ sung field thiếu | Liên tục tới khi Data Lead xác nhận dataset final đủ dùng | - |
| Viết README phần crawl/data source | Trước Final Report | - |

### AI Engineer — Regression track
| Task | Deadline | Output |
|---|---|---|
| Research thuật toán, code khung (chạy trên mock/data POC) | Tuần 1-2, song song lúc crawl | Code khung |
| EDA phần giá/feature trên dataset draft | Ngay khi có dataset draft, **trước Progress Report** | EDA sơ bộ |
| Train + so sánh Linear Regression / Random Forest / Gradient Boosting (mục 7.1) trên dataset final | Sau khi nhận dataset final; xong trước Final Report ít nhất 1 tuần để còn thời gian viết report | Model + bảng metric |
| Viết phần regression cho written report + slide | Trước Final Report | - |

### AI Engineer — Anomaly track
| Task | Deadline | Output |
|---|---|---|
| Research rule-based signals + Isolation Forest/LOF, code khung | Tuần 1-2, song song lúc crawl | Code khung |
| EDA phần tín hiệu bất thường trên dataset draft | Ngay khi có dataset draft, **trước Progress Report** | EDA sơ bộ |
| Train + so sánh rule-based / Isolation Forest / LOF (mục 7.2) trên dataset final | Sau khi nhận dataset final; xong trước Final Report ít nhất 1 tuần | Risk scoring model + case cụ thể |
| Viết phần anomaly detection cho written report + slide | Trước Final Report | - |

### DevOps/Cloud
| Task | Deadline | Output |
|---|---|---|
| Setup infra cho Phase 0 POC (rate-limit, retry, logging, checkpoint) | Tuần 1, song song Data Engineer chạy POC | Infra sẵn sàng |
| Setup environment/reproducibility (`requirements.txt`/Docker) | Tuần 2 | Môi trường chuẩn |
| Storage setup (SQLite/Parquet), giám sát crawl job full scope | Song song giai đoạn crawl, tới khi Data Engineer crawl xong | Storage layer, monitoring |
| Automation script chạy toàn bộ pipeline (crawl→clean→EDA→model) 1 lệnh | **Trước Progress Report** (để demo tiến độ dễ dàng) | Script automation |
| Đóng gói source code cuối, verify chạy được trên máy sạch | Trước Final Report | Package cuối |

---

## Lưu ý quan trọng

- Ngày chính xác của Progress Report chưa công bố (TBA) — team nên tự đặt deadline nội bộ sớm hơn ngày thật vài ngày để có buffer.
- 2 AI Engineer **không cần chờ dataset final** mới bắt đầu — dùng dataset draft ngay sau khi có để làm EDA + code khung, tránh dồn việc vào giai đoạn cuối.
- Môn học yêu cầu **mỗi thành viên tự contribute vào written report và presentation** — mỗi người viết phần mình phụ trách, Linh chỉ tổng hợp & rà soát chứ không viết hộ toàn bộ.
- Dùng chung 1 repo Git, mỗi người làm branch riêng theo track, merge vào `main` sau khi test chạy được.
