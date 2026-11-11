# PLAN_MAPPING – đối chiếu Plan 12 tuần với repo (4/11/2026)

Nguồn: tab "Phân công chi tiết" của `Plan 12 tuần SageServe.xlsx` (file không nằm trong repo). Bảng này chỉ ghi bằng chứng có trong repo (code, test, tài liệu, Release). Cột "Trạng thái" là đánh giá theo bằng chứng đó, **không** thay cột Trạng thái của file xlsx:
- **đủ**: đầu ra của Plan có trong repo.
- **một phần**: có một phần, hoặc đầu ra nằm ở `output/` (báo cáo cá nhân, không đẩy lên GitHub).
- **chưa**: không có bằng chứng trong repo.

| Đầu việc | Người phụ trách | Đầu ra theo Plan | Bằng chứng trong repo | Trạng thái |
|---|---|---|---|---|
| T01–T10 | cả nhóm | chốt hướng, phân công, chủ đề | không có trong repo (xlsx ghi Hoàn thành) | chưa |
| T11 | Trần Tuấn Đạt | phạm vi + chỉ số thành công; repo + phân công | repo, `README.md`, `CLAUDE.md` (luật làm việc); tiêu chí chấm ở đầu `RESULTS.md` | một phần (tài liệu phạm vi SMART không có trong repo) |
| T12 | Dương Tiến Đạt | tóm tắt forecast + notebook mẫu | `generate_causal_arima_forecasts.py`; báo cáo ở `output/` | một phần |
| T13 | Vũ Hoàng Ân | môi trường tái lập + log chạy mẫu | `requirements.txt`, `REPRODUCE.md` mục 1, `python -m pytest` (89 test, gồm `tests/test_end_to_end.py`) | đủ |
| T14 | Đoàn Việt Đức | sơ đồ kiến trúc + bảng tham số | bảng tham số ở `REPRODUCE.md` mục 4; không có sơ đồ | một phần |
| T15 | Bùi Thanh Sơn | danh mục thí nghiệm + khung báo cáo | danh mục tuyên bố cần tái hiện ở `RESULTS.md`; khung báo cáo ở ngoài repo | một phần |
| T16 | Trần Tuấn Đạt | "System config v1" | `configs/controller/us3-3models.yaml`, `us3-4models.yaml`; tài liệu ở `output/` | một phần |
| T17 | Dương Tiến Đạt | notebook + bảng periodicity theo tier | cổng T2 (ACF lag 24 giờ theo tier) ở `TRACE_SPEC.md`, chấm bằng `qualify_trace.py`; notebook ở `output/` | một phần |
| T18 | Vũ Hoàng Ân | script tiền xử lý + dataset dev | `preprocess_servegen.py`, `compose_trace.py`, `fork_trace.py`, `make_trace_v2.py`, `validate_trace.py`, `qualify_trace.py`; trace ở Release `traces-v1`, `traces-v2` | đủ |
| T19 | Đoàn Việt Đức | ghi chú code walkthrough | `configs/controller/us1-llama70b.yaml`; ghi chú ở `output/` | một phần |
| T20 | Bùi Thanh Sơn | hình characterization v1 + nháp mục 3 | hình ở `output/` | chưa (trong repo) |
| T21 | Trần Tuấn Đạt | interface spec v1 | không có | chưa |
| T22 | Dương Tiến Đạt | forecast v0 + MAPE | `generate_causal_arima_forecasts.py` (ARIMA-60), `compare_forecasters.py`; chưa thấy chọn (p,d,q) theo AIC | một phần |
| T23 | Vũ Hoàng Ân | instance-hours Siloed vs Unified | `run.sh s4`, `configs/controller/us1-4models{,-siloed}.yaml`; `RESULTS.md` dòng §4 | đủ |
| T24 | Đoàn Việt Đức | heuristic reactive + unit test | `arbiter.py` (70/30, cooldown 15 s), Queue Manager NIW trong `simulator.py`; `tests/test_paper_rules.py`, `tests/test_pending_instances.py` | đủ |
| T25 | Bùi Thanh Sơn | bảng so sánh Fig. 8, Table 1 | `analyze_s4.py`; `RESULTS.md` dòng §4 Fig. 8a, Table 1 | đủ |
| T26 | Trần Tuấn Đạt | tài liệu công thức ILP + solver | công thức ở `REPRODUCE.md` mục 4 dòng "ILP §5"; `long_term_allocation.py` | một phần (không có tài liệu riêng) |
| T27 | Dương Tiến Đạt | so sánh forecast + module v1 | dự báo cho mọi cặp mô hình–vùng (`traces/forecasts/`, Release `traces-v2`); `compare_forecasters.py`, kết quả Phụ lục B chỉ có trên v1 (`git show 27345e2:REPRODUCE.md`) | một phần |
| T28 | Vũ Hoàng Ân | hook forecast trong simulator + log | `global_arbiter.forecast_mode=online`, `forecast_log.csv`; `tests/test_load_predictor.py` | đủ |
| T29 | Đoàn Việt Đức | bảng θ, α, σ | `benchmark_theta.py`, `data/theta_tps*_v2.csv`, `tests/test_benchmark_theta.py`; α, σ ở `REPRODUCE.md` mục 4 | đủ |
| T30 | Bùi Thanh Sơn | hình dự báo vs thực + nháp mục Forecast | `forecast_log.csv`, `experiments/analyze_hourly_miss.py`, `RESULTS.md` dòng "Nguyên nhân độ trễ"; hình ở `output/` | một phần |
| T31 | Trần Tuấn Đạt | optimizer v0 + unit test | `long_term_allocation.py`, `tests/test_ilp.py` | đủ |
| T32 | Dương Tiến Đạt | pipeline Forecast→ILP | `global_arbiter.py` (đỉnh dự báo giờ tới + β); `run.sh beta` (D18) | đủ |
| T33 | Vũ Hoàng Ân | hook ILP mỗi giờ, log δ và thời gian giải | ILP mỗi giờ, quyết định ghi ở `global_ariber_logs.csv`; không ghi thời gian giải | một phần |
| T34 | Đoàn Việt Đức | Autoscaler nhận δ | `arbiter.py` (`scale_up_from_spot`, `scale_up_from_spot_other`, `scale_down_to_spot`) | đủ |
| T35 | Bùi Thanh Sơn | bảng runtime ILP | `bench_ilp.py`; không có bảng kết quả trong repo | một phần |
| T36 | Trần Tuấn Đạt | demo giữa kỳ + biên bản | `tests/test_end_to_end.py`; demo, biên bản ở ngoài repo | một phần |
| T37 | Dương Tiến Đạt | LT-UA + test | `global_arbiter_ARIMA_checking` trong `arbiter.py`, `tests/test_ltua_ratio.py` | đủ |
| T38 | Vũ Hoàng Ân | runner thí nghiệm batch | `experiments/run.sh`, `run_all.sh`, `run_sens.sh`, `run_patched.py` | đủ |
| T39 | Đoàn Việt Đức | routing/scaling hoàn chỉnh | LT-I, LT-U trong `arbiter.py`; `region_router.py`; JSQ ở `model_endpoint_router.py` | đủ |
| T40 | Bùi Thanh Sơn | checklist nghiệm thu + báo cáo nháp | `check_paper_rules.py`, `docs/REPORT.md` | một phần |
| T41 | Trần Tuấn Đạt | end-to-end v1 + bộ tham số chốt | `RESULTS.md`, `DECISIONS.md` (D1–D23) | đủ |
| T42 | Dương Tiến Đạt | forecast v2 + so sánh MAPE | không đổi ARIMA-60 (D16, D17); chỉ có chẩn đoán oracle/oracle_smooth | chưa |
| T43 | Vũ Hoàng Ân | bộ log Siloed / Reactive / LT-I/U/UA | `run.sh s4`, `run.sh lt`; số ở `RESULTS.md` (kết quả mô phỏng không đẩy, lệnh tái tạo có) | đủ |
| T44 | Đoàn Việt Đức | bản fix + test hồi quy | các sửa khởi động, ILP đếm instance chờ (`REPRODUCE.md` mục 4); `tests/test_pending_instances.py`, `tests/test_paper_rules.py` | đủ |
| T45 | Bùi Thanh Sơn | notebook phân tích tự động + bảng sơ bộ | dạng script: `analyze_s4.py`, `analyze_waste.py`, `experiments/analyze_*.py`, `experiments/reactive_behavior.py` | một phần (script thay notebook) |
| T46 | Trần Tuấn Đạt | kế hoạch thí nghiệm + ablation ε/β | `run.sh week`; ε, β ở `SENSITIVITY.md`; β 5/15% ở `RESULTS.md` (D18) | đủ |
| T47 | Dương Tiến Đạt | bảng ablation forecast | ảnh hưởng chất lượng dự báo lên instance-hours: `run.sh oracle`, `experiments/analyze_oracle.py`; chưa chạy mô hình dự báo thay thế trong mô phỏng | một phần |
| T48 | Vũ Hoàng Ân | kết quả chính + script reproduce | `run_all.sh`, Release `traces-v2`, `RESULTS.md`; mỗi thí nghiệm một seed (mô phỏng tất định) | một phần (không nhiều seed) |
| T49 | Đoàn Việt Đức | so sánh baseline + burst/scalability | `run.sh chiron`, `burst`, `scale5`; `RESULTS.md` §7.2.3, §7.2.5, §7.2.7 | đủ |
| T50 | Bùi Thanh Sơn | bảng kết quả chính + so sánh bài báo | `RESULTS.md` | đủ |
| T51 | Trần Tuấn Đạt | báo cáo v2 | `docs/REPORT.md` (bản nhóm, chưa đối chiếu với số v2) | một phần |
| T52 | Dương Tiến Đạt | mục Forecast + notebook sạch | không có | chưa |
| T53 | Vũ Hoàng Ân | repo sạch, README, requirements/Docker, tag release, demo | `README.md`, `REPRODUCE.md`, `requirements.txt`, Release `traces-v1`, `traces-v2`; không có Docker | một phần |
| T54 | Đoàn Việt Đức | mục hệ thống + slide | không có | chưa |
| T55 | Bùi Thanh Sơn | slide v1 + báo cáo ghép | `plot_slides.py` (biểu đồ cho slide); slide ở ngoài repo | một phần |
| T56–T60 | cả nhóm | báo cáo cuối, trình bày, demo, retrospective | không có | chưa |
