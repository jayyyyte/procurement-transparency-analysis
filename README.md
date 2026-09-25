# Vietnam Procurement Transparency Analysis

Capstone IT4142E (SOICT – HUST): crawl dữ liệu đấu thầu công khai từ `muasamcong.mpi.gov.vn` → làm sạch & tích hợp → EDA → dự đoán % tiết kiệm (Linear Regression / Random Forest / LightGBM) và điểm bất thường thống kê (Rule-based / Isolation Forest / LOF).

- **Hướng dẫn cài đặt & chạy:** [`readme.txt`](readme.txt)
- **Trạng thái hiện tại — gate Phase 0:** [`reports/phase0_feasibility.md`](reports/phase0_feasibility.md) (full crawl đang chờ chủ dự án duyệt)
- **Đặc tả & phân vai:** [`docs/requirements.md`](docs/requirements.md), [`docs/team-plan.md`](docs/team-plan.md)

```bash
pip install -r requirements.txt
python -m pytest
python scripts/generate_fixture.py && python run_pipeline.py all --data fixture   # chạy thử trên dữ liệu tổng hợp
```
