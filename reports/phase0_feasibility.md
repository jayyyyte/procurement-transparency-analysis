# Phase 0 — Feasibility Report (POC crawl muasamcong.mpi.gov.vn)

**Ngày khảo sát:** 2026-09-25 · **Người thực hiện:** R1/R2 (Claude Code hỗ trợ) · **Dữ liệu máy đọc:** `reports/phase0/probe_results.json` · **Tái lập:** `python scripts/phase0_probe.py`

## 1. Kết luận

| Tiêu chí gate (requirements §2.3) | Kết quả |
|---|---|
| Crawl thử ~50–100 record TBMT | ✅ 100 TBMT + 50 KQLCNT + 50 KHLCNT (`data/sample/phase0_*.jsonl`) |
| ≥ 80% field mong muốn (§3.4) | ✅ 15/16 field có trong response danh sách (94%). Nếu không tính `nguon_von` (chỉ là proxy) thì 14/16 (88%) |
| Crawl được bằng HTTP thuần (không cần JS render/login) | ✅ Qua API JSON, **nhưng** có vấn đề reCAPTCHA (xem §3, câu 2) |
| Tốc độ đủ cho full scope trong timeline | ⚠️ 48 tháng × 3 nguồn ≈ **4,2 triệu bản ghi ≈ 10 ngày crawl liên tục** ở mức 1 request/2s. Timeline chỉ dành 1 tuần (tuần 2) |

**Đề xuất:** kỹ thuật đã khả thi, nhưng **full crawl vẫn bị khoá** (`crawl.approved_option: null`). Chủ dự án/giảng viên cần chốt các quyết định ở §5, đặc biệt là D1 (dùng endpoint không gắn reCAPTCHA) và D2 (phạm vi/thời gian).

## 2. Cách khảo sát

- Tổng cộng **~100 request đơn lẻ**, cách nhau ≥ 2s, User-Agent ghi rõ mục đích học thuật. Không có 403/429/challenge; mọi response là 200, trừ 3 request cố ý test giới hạn (đều nhận 400).
- Đọc JavaScript của chính trang web (trang chủ, trang tìm kiếm) để biết endpoint và payload, thay vì đoán.
- **Không** giải, trích xuất hay dùng lại token reCAPTCHA. Endpoint có reCAPTCHA chỉ được gọi **1 lần không token** để ghi nhận phản hồi, và dữ liệu (nếu có) bị bỏ.

## 3. Trả lời các câu hỏi cần verify (§3.3)

1. **Tìm kiếm nâng cao dùng GET hay POST?** Là **POST JSON** (payload kiểu Elasticsearch) tới `/o/egp-portal-contractor-selection-v2/services/smart/search?token=<reCAPTCHA>`. Trang là Liferay + Vue: danh sách **không có trong HTML**, chỉ tải qua API.
2. **Có CAPTCHA không?**
   - **Có** ở tìm kiếm nâng cao: Google **reCAPTCHA v3** (vô hình), token gắn vào `?token=`. Gọi không có token nhận **HTTP 400**, tức server thực sự kiểm tra token.
   - **Không** ở `/o/egp-portal-home/services/smart/search`. Đây là endpoint chính trang chủ gọi để hiển thị khối "Thông báo mời thầu", dùng **cùng index** `es-contractor-selection` và nhận cùng bộ lọc (loại tin, bước, khoảng ngày).
   - Endpoint này bị giới hạn **pageSize ≤ 10** (lớn hơn thì trả "PageSize unsatisfactory!!!") và `totalElements` tối đa 10.000.
3. **Trang chi tiết có URL ổn định không?** Có pattern `/web/guest/contractor-selection?render=detail&type=…&stepCode=…&id=…&notifyId=…`, nhưng GET trực tiếp nhận thông báo *"egp-portal-contractor-selection-v2 tạm thời không có"*. API chi tiết không lộ trong HTML tĩnh, nên cần recon bằng DevTools nếu muốn lấy thêm field (xem D4). Đây **không phải điều kiện bắt buộc**: 15/16 field đã có ở API danh sách.
4. **Các field giá gói thầu, giá trúng thầu, số nhà thầu, hình thức có ở đâu?** Tất cả nằm trong **bản ghi danh sách** (§4). Bản ghi TBMT, khi gói thầu đã có kết quả (`stepCode = notify-contractor-step-4-kqlcnt`), chứa luôn `bidWinningPrice`, `contractorName`, `numBidderJoin`. Đã kiểm tra 10/10 bản ghi ngày 12/03/2025.
5. **Rate limit / chặn IP?** Ở mức 1 request/2s không thấy giới hạn nào. Latency server khoảng 0,3–0,5s. Chưa test tần suất cao hơn, và **không nên** test.

Phát hiện thêm:
- Server dùng khoá DH 1024-bit. OpenSSL 3 (Python 3.12+) từ chối với lỗi `DH_KEY_TOO_SMALL`. Cách xử lý là hạ SECLEVEL=1 **chỉ cho domain này**, vẫn verify chứng chỉ (`LegacyTLSAdapter` trong `src/crawler/client.py`).
- `robots.txt` = `User-Agent: * / Disallow:` (cho phép tất cả).
- Domain vẫn là `muasamcong.mpi.gov.vn` (HTTP 200).

## 4. Field coverage (§3.4) trên mẫu POC

| Field | Key trong API | Nguồn | Có dữ liệu | Ghi chú |
|---|---|---|---|---|
| `ma_goi_thau` | `notifyNo` (+ `planNo` cho KHLCNT) | TBMT/KQLCNT | 100% | Mã TBMT (IB…/DC…) làm khoá chính; `planNo` để join KHLCNT |
| `ten_goi_thau` | `bidName` | TBMT/KQLCNT | 100% | |
| `ten_du_an` | `pname` / `name` | KHLCNT | 100% | |
| `chu_dau_tu` | `investorName` | cả 3 | 100% | |
| `ben_moi_thau` | `procuringEntityName` → fallback `investorName` | TBMT | 100% | `procuringEntityName` chỉ có ~11% |
| `tinh_thanh` | `locations[].provName` | TBMT/KHLCNT | 100% | **KQLCNT không có location**: lấy qua KHLCNT (`planNo`) |
| `linh_vuc` | `investField` (HH/XL/TV/PTV/HON_HOP) | cả 3 | 100% | |
| `nguon_von` | *(không có)* → proxy `planType` | cả 3 | 100% | DTPT/TX/DTMS/KHAC, **không phải nguồn vốn gốc** (D3) |
| `hinh_thuc_lua_chon_nha_thau` | `bidForm` (DTRR, CHCT, CDTRG, …) | TBMT/KQLCNT | 100% | |
| `gia_goi_thau` | `bidPrice` | cả 3 | 100% | |
| `gia_trung_thau` | `bidWinningPrice` | KQLCNT / TBMT bước 4 | 100% | |
| `nha_thau_trung_thau` | `contractorName` (+ `winningCode` = MST) | KQLCNT / TBMT bước 4 | 100% | |
| `so_nha_thau_tham_du` | `numBidderJoin` | KQLCNT / TBMT bước 4 | 100% | Với chỉ định thầu rút gọn giá trị là 0 |
| `thoi_diem_dong_mo_thau` | `bidCloseDate`, `bidOpenDate` | TBMT | 100% | |
| `thoi_gian_thuc_hien_hop_dong` | *(không có)* | — | 0% | Chỉ có ở trang chi tiết (D4) |
| `ngay_dang_tai` | `publicDate`, `publicDateKqlcnt` | cả 3 | 100% | |

## 5. Volume & thời gian crawl ước tính

Lấy mẫu **16 ngày trải đều 48 tháng** (có cả cuối tuần và ngày lễ), đếm `totalElements` theo ngày:

| Nguồn | TB / ngày | Max / ngày |
|---|---|---|
| TBMT (`es-notify-contractor`, `caseKHKQ ≠ 1`) | 442 | 1.083 |
| KQLCNT (bước 4, theo `publicDateKqlcnt`) | 1.510 | 3.480 |
| … trong đó thuộc gói có TBMT (`caseKHKQ ≠ 1`) | 456 | 1.273 |
| KHLCNT (`es-plan-project-p`) | 946 | 2.033 |

Max mỗi ngày nhỏ hơn 10.000, nên **cửa sổ 1 ngày** đủ để vượt giới hạn phân trang. Crawler vẫn tự tách theo `investField` nếu có ngày vượt ngưỡng.

Thời gian ước tính ở 1 request/2s, 10 bản ghi/request, 1 tiến trình:

| Chiến lược | 48 tháng | 36 tháng | 24 tháng | 12 tháng |
|---|---|---|---|---|
| **S1**: 3 nguồn độc lập (mặc định) | 4,23 tr bản ghi · **9,9 ngày** | 7,4 ngày | 5,0 ngày | 2,5 ngày |
| **S2**: TBMT + KQLCNT chỉ `caseKHKQ=1` + KHLCNT | 3,57 tr · **8,4 ngày** | 6,3 ngày | **4,2 ngày** | 2,1 ngày |
| **S3**: như S2 nhưng bỏ KHLCNT | 2,18 tr · **5,2 ngày** | 3,9 ngày | 2,6 ngày | 1,3 ngày |

- S2 không mất dữ liệu: kết quả của gói có TBMT đã nằm trong bản ghi TBMT. Bật bằng `crawl.extra_filters.kqlcnt` trong config.
- S3 mất `ten_du_an`. Tỉnh của gói chỉ định thầu rút gọn khi đó phải suy từ mã chủ đầu tư.
- Chạy 2 tiến trình song song (R1: TBMT+KHLCNT, R2: KQLCNT) giảm một nửa thời gian thực, nhưng tổng tải lên site thành 1 request/s. Mức này vẫn trong khoảng "1 request/1–2s" của FR-1, nhưng cần được đồng ý (D2).
- Dung lượng: raw gzip khoảng 0,5–1 GB cho 48 tháng. `packages.parquet` vài trăm MB, pandas xử lý được; PySpark là tuỳ chọn.

## 6. Quyết định cần chủ dự án / giảng viên chốt

- **D1 — Dùng endpoint trang chủ (không reCAPTCHA) ở quy mô lớn?**
  - Lý do ủng hộ: endpoint công khai, chính trang chủ gọi không cần CAPTCHA, `robots.txt` cho phép, và tải được giữ thấp.
  - Lý do cần cân nhắc: cùng dữ liệu đó ở trang tìm kiếm nâng cao được bảo vệ bằng reCAPTCHA. Crawl hàng triệu bản ghi qua cửa ngõ khác có thể bị coi là **đi vòng qua ý định bảo vệ** của site (§2.2).
  - Nếu **đồng ý**, đặt `approved_option: "A"`. Nếu **không**, cần phương án khác: xin dữ liệu mở từ đơn vị vận hành, hoặc thu hẹp mạnh (phương án C).
- **D2 — Phạm vi thời gian & tốc độ:** chọn một trong
  - (a) 48 tháng với S2 và 2 tiến trình, khoảng 4,2 ngày, 1 request/s tổng;
  - (b) 24 tháng với S2 và 1 tiến trình, khoảng 4,2 ngày;
  - (c) 36 tháng với S3, khoảng 3,9 ngày.

  Requirements không cho Claude Code tự cắt scope.
- **D3 — Định nghĩa "vốn ngân sách nhà nước":** API danh sách không có field nguồn vốn. Mặc định dùng proxy `planType ∈ {DTPT, TX, DTMS}` và loại `KHAC` (~18% mẫu). Chấp nhận proxy này, hay cần recon API chi tiết để lấy nguồn vốn thật?
- **D4 — `thoi_gian_thuc_hien_hop_dong`:** bỏ field này (§7.1 liệt kê nó là feature), hay R1/R2 recon API chi tiết bằng DevTools? Nếu recon, mỗi gói thêm 1 request, tức khoảng 2–3 triệu request, **gấp ~6 lần** thời gian crawl. Đề xuất: bỏ, hoặc chỉ lấy cho một mẫu nhỏ.
- **D5:** điền email liên hệ của team vào `crawl.user_agent` trước khi chạy.

## 7. Khó khăn & hướng giải quyết (dùng cho written report)

| Khó khăn | Hướng giải quyết |
|---|---|
| Danh sách render bằng JS (Vue), HTML không chứa dữ liệu | Đọc JS của site để tìm API JSON; crawl API thay vì parse HTML (không cần Selenium) |
| Tìm kiếm nâng cao gắn reCAPTCHA v3 | Không vượt CAPTCHA; dừng và báo cáo (gate D1) |
| Server dùng DH key yếu, Python/OpenSSL 3 từ chối kết nối | Adapter TLS riêng cho domain, hạ SECLEVEL, vẫn verify chứng chỉ |
| pageSize ≤ 10, `totalElements` tối đa 10.000 | Cửa sổ 1 ngày, tự tách theo lĩnh vực nếu vượt ngưỡng; checkpoint từng trang |
| Không có field nguồn vốn, thời gian thực hiện HĐ | Proxy `planType` (D3); feature tự bị loại nếu trống (D4) |
| KQLCNT không có địa điểm | Lấy tỉnh qua join KHLCNT theo `planNo` |
| Sáp nhập tỉnh 01/07/2025 (63 → 34), dữ liệu vắt qua mốc | Giữ 2 cột `tinh_thanh_63` / `tinh_thanh_34` (`config/province_mapping.csv`) |
| Volume ~3,5–4,2 triệu bản ghi | Ước lượng sớm, chiến lược S2/S3, Parquet; PySpark tuỳ chọn |

## 8. Trạng thái code tại thời điểm gate

- **Crawler** (`src/crawler/`): rate limit + jitter, retry/backoff, circuit breaker (dừng khi gặp 403/challenge), checkpoint SQLite, raw gzip JSONL. Có test resumability bằng client giả. `run_pipeline.py crawl` bị khoá tới khi `approved_option` được đặt.
- **Phase 2–5** chạy end-to-end trên dữ liệu tổng hợp: `python run_pipeline.py all --data fixture`, khoảng 30s, ra 12 hình và các bảng so sánh model. Dữ liệu này không bao giờ dùng cho kết quả.
- Sau khi gate duyệt: đặt `approved_option: "A"`, cấu hình `start_date`/`extra_filters` theo D2, chạy `python run_pipeline.py crawl` rồi `python run_pipeline.py all`.
