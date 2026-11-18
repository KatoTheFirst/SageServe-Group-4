# SageServe end-to-end v1 trên Azure DEV-1D

**LT-UA online hoàn thành 35.000/35.000 request.** Kết quả bằng Reactive ở 552 instance-hours, IW TTFT P95 2,657 s và tỷ lệ vi phạm SLA 8,224%. Chốt ε = 0,90, β = 0,10, LT-UA tăng ở ≥ 5× và giảm ở ≤ 0,5× dự báo trong 20 phút cuối giờ.

## Thiết lập và tiêu chí

Dùng commit `85aa1abb85d707dc6dd033d52cf9eac71bfcb680`, Python 3.11.18, statsmodels 0.15.0, PuLP 2.9.0/CBC, seed mô phỏng 0. Cấu hình `us3-4models` mô phỏng A100 ở 3 vùng với 4 mô hình, FCFS, `data/perf_model_4models.csv` và θ từ `data/theta_tps_v2.csv`. Chạy tới 90.000 giây để ghi cả request đến cuối cửa sổ 24 giờ.

Checkout thiếu bản DEV-1D lịch sử 30.539 request trong [REPORT.md](REPORT.md). Bản chạy này tái tạo DEV-1D canonical 24 giờ bằng `preprocess_traces.py`, lấy mẫu 35.000 request với seed 42. Trong 24 giờ đầu theo mốc UTC chung, chỉ luồng Code có dữ liệu vì Conversation bắt đầu ngày 12/05. Trace có 24.490 IW (17.475 IW-F và 7.015 IW-N), 10.510 NIW, 0,41 request/s và trung vị 9 token đầu ra. SHA-256 của trace là `d85b328e45354fdbc6c986ad3ede7381882d454461bbc7a904351d4d084b1f71`. [Azure LLM Inference Trace 2024](https://github.com/Azure/AzurePublicDataset/blob/master/AzureLLMInferenceDataset2024.md)

So LT-UA với Reactive để đo chi phí và SLA, và với LT-U để đo phần đóng góp của luật ARIMA. Dùng instance-hours của các instance đang phục vụ, lấy số lớn nhất mỗi khối 15 phút rồi chia 4, tính trên `[3600, 86400)`. Đo TTFT/E2E P95 trên toàn bộ request IW đã hoàn thành. Khi kiểm SLA IW, trừ 1 giây trễ cố định của router theo quy ước repo và áp SLA của trace (IW-F 1 s, IW-N 10 s). Đo SLA NIW theo E2E ≤ 24 giờ. Mốc so sánh bài báo là tiết kiệm 23,38% instance-hours của Llama-2 và giữ độ trễ/SLO trong §7.2.1–7.2.2. [SageServe v3, §7.2](https://arxiv.org/html/2502.14617v3#S7.SS2)

## Kết quả end-to-end

| Chế độ | Hoàn thành IW / NIW | Instance-hours tổng | Instance-hours Llama-2 | IW TTFT P95 | IW E2E P95 | IW vi phạm SLA |
|---|---:|---:|---:|---:|---:|---:|
| Reactive | 24.490 / 10.510 | 552 | 138 | 2,657 s | 5,180 s | 8,224% |
| LT-U offline | 24.490 / 10.510 | 552 | 138 | 2,657 s | 5,180 s | 8,224% |
| LT-UA offline | 24.490 / 10.510 | 552 | 138 | 2,657 s | 5,180 s | 8,224% |
| **LT-UA online (v1)** | **24.490 / 10.510** | **552** | **138** | **2,657 s** | **5,180 s** | **8,224%** |

Log của cả bốn bài trùng từng request theo ID và các chỉ số đã ghi. Toàn bộ vi phạm IW đến từ IW-F (11,525% IW-F), IW-N và NIW đều 0%. LT-UA tiết kiệm **0%** so với Reactive, thấp hơn mốc bài báo **23,38 điểm phần trăm** trên Llama-2. P95 bằng Reactive và IW-F vẫn trượt mục tiêu SLA tuyệt đối. Log node của Reactive cho thấy 2.011/2.014 lần trượt IW-F có riêng thời gian prefill vượt 1 s, tập trung ở Bloom và Llama-2. [SageServe v3, §7.2](https://arxiv.org/html/2502.14617v3#S7.SS2)

## Sai lệch và nguyên nhân

- **Forecast.** ARIMA-60 online dự báo thấp hơn đỉnh thực ở cả 276 ô giờ × vùng × mô hình sau warm-up. MAPE đỉnh là 78,33%, WAPE 76,30% và bias −76,30%. ARIMA offline canh đúng giờ có MAPE 78,31% và WAPE 76,24%. Baseline dùng đỉnh giờ trước có MAPE 28,29% và WAPE 26,06%. Tải mỏng khiến 36,27% số phút của từng cặp vùng–mô hình không có IW. Đỉnh theo phút do số ít request tạo ra cao hơn nhiều so với mức ARIMA dự báo.
- **ILP.** CBC trả `Optimal` 24/24 lần trong mỗi bài LT-UA offline và online. Đối chiếu `n + δ` với các ràng buộc cục bộ, toàn cục và không âm đều đạt. Cả 288 mục tiêu giờ × vùng × mô hình bằng 1 instance, trong khi autoscaler giữ tối thiểu 2 instance mỗi endpoint. Sau warm-up, 2 × 12 endpoint × 23 giờ tương ứng đúng 552 instance-hours.
- **LT-UA.** Mục tiêu ILP dưới sàn để lại `changes < 0`, nên điều kiện `changes == 0` của nhánh so tải/dự báo không đạt. Cả hai bài LT-UA ghi 0 lần đánh giá tỷ lệ. Tác động đến độ trễ và chi phí trùng với LT-U trên trace này.
- **Lệch lịch offline.** ILP chạy trên request đầu tiên đủ 3.600 giây kể từ lần trước. Vì vậy 18/24 lần giải lệch ít nhất một phút khỏi đầu giờ, tối đa 103 giây. Đọc dự báo offline từ phút hiện tại kéo vào một phút phát hành từ giờ kế tiếp ở 18 lần đó. MAPE của log offline vì vậy là 75,82%, thấp hơn MAPE 78,31% khi canh đúng giờ. Dùng mode online cho cấu hình chốt để fit từ dữ liệu đã quan sát. Warm-up giờ 0 dùng trung bình giờ 0 theo quy ước repo.

## Đối chứng ngưỡng LT-UA

Đối chứng dùng cùng trace và forecast online. Wrapper nâng mục tiêu sau ILP lên tối thiểu 2 instance để tái hiện điều kiện mà LT-UA cần trước khi so tỷ lệ. Ba bài đều hoàn thành 35.000 request, và log ghi nhận co giãn thực theo cả hai chiều.

| Ngưỡng tăng / giảm | Số lần tăng thực | Số lần giảm thực | Instance-hours tổng | So với 552 của v1 | IW TTFT P95 | IW vi phạm SLA |
|---|---:|---:|---:|---:|---:|---:|
| 5× / 0,5× | 408 | 167 | 700,75 | +26,95% | 2,657 s | 8,224% |
| 3× / 0,5× | 1.051 | 404 | 920,75 | +66,80% | 2,657 s | 8,224% |
| 5× / 0,25× | 408 | 147 | 708,25 | +28,31% | 2,657 s | 8,224% |

Cặp 5× / 0,5× dùng ít instance-hours nhất trong ba cặp thử. Cả ba cặp có cùng tỷ lệ vi phạm SLA và cùng TTFT P95 đến ba chữ số thập phân. Vì vậy 5× / 0,5× là cặp chốt v1. Trên trace mỏng, tỷ lệ tải thực/dự báo có thể vượt ngưỡng dù cấp thêm instance chỉ làm tăng chi phí.

## Bằng chứng chạy

Cả 13 bài mô phỏng có exit code 0, đủ 35.000 ID duy nhất mỗi bài. Tất cả 288 lần gọi CBC trả `Optimal`. Kiểm lại ràng buộc cục bộ, toàn cục và số instance không âm từ log đạt ở mọi bài có ILP. Nhóm test `test_optimizer`, `test_ilp`, `test_ltua_ratio`, `test_load_predictor` đạt 47/47.

- [Chỉ số theo cấu hình](../results/e2e_v1/metrics.csv) và [theo mô hình](../results/e2e_v1/metrics_by_model.csv)
- [Sai số dự báo](../results/e2e_v1/forecast_metrics.csv)
- [runner](../results/e2e_v1/run_matrix.py) và [script tổng hợp](../results/e2e_v1/summarize.py)

## Bộ tham số chốt cho v1

| Tham số | Giá trị | Cách áp dụng |
|---|---:|---|
| ε | **0,90** | Năng lực ở từng vùng phải đạt ít nhất 90% đỉnh dự báo đã cộng đệm NIW. |
| β | **0,10** | Cộng 10% TPM NIW trung bình của 3.600 giây trước vào đỉnh dự báo IW. |
| Ngưỡng LT-UA | **Tăng ≥ 5×, giảm ≤ 0,5×** | So TPM IW thực trong 60 giây gần nhất với dự báo, trong 20 phút cuối giờ và khi đã đạt mục tiêu ILP. |
| Ngưỡng bộ nhớ | **Tăng > 70%, giảm < 30%** | Điều khiển theo mức sử dụng bộ nhớ hiệu dụng. Cooldown **15 s** giữa các lần co giãn. |
| Ngưỡng NIW | **< 60% cấp 1, < 50% cấp 2** | Queue Manager theo mức sử dụng bộ nhớ. |
| Dự báo và nhịp giải | **ARIMA-60 online, ILP mỗi 3.600 s** | 60 phút huấn luyện, 60 phút dự báo, ILP chạy theo request. |

Ablation trên mã hiện hành thay từng tham số một. ε thử 0,63 và 1,00, β thử 0,05 và 0,15, ngưỡng tăng thử 3× và ngưỡng giảm thử 0,25×. Cả sáu biến thể offline có cùng log cấp phát, bộ nhớ và request theo SHA-256 với LT-UA offline gốc. Với forecast online, ngay cả khi dùng β = 0,15, đỉnh vùng lớn nhất sau khi chuẩn hóa theo θ chỉ bằng 41,89% năng lực một instance. Vì thế một instance mỗi vùng vẫn thỏa cả ràng buộc cục bộ và toàn cục cho dải ε/β đã thử. Chốt ε và β theo bộ gốc của repo cho trace dev này.

Cấu hình trên là mốc v1 cho DEV-1D. Mật độ request thấp và sàn autoscaler giới hạn khả năng suy rộng sang tải sản xuất hoặc burst.

## Tái lập

Dùng môi trường từ `requirements.txt` với các phiên bản ghi trong `results/e2e_v1/environment.txt`. Nếu cần tái tạo trace, tải 134.217.728 byte đầu của Code và 33.554.432 byte đầu của Conversation từ [Azure dataset release](https://github.com/Azure/AzurePublicDataset/releases/tag/dataset-llm-2024). Cắt byte sau ký tự xuống dòng cuối cùng của từng file để bỏ dòng tải dở. SHA-256 sau khi cắt của Code là `d724e5c269ef62984e49ee88d00d3dee03582648b0ee392c40e834438e4df985`, Conversation là `118de99691339dc4700e25b39750dfb11ff8ccd85168428e9a64a71214015246`.

```powershell
$r = 'results/e2e_v1'
$env:PYTHONIOENCODING = 'utf-8'
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
python preprocess_traces.py --code_csv "$r/setup/code-full-complete.csv" --conv_csv "$r/setup/conv-complete.csv" --output_csv "$r/azure_trace_dev_1day.csv" --duration_hours 24 --target_requests 35000 --seed 42
python generate_causal_arima_forecasts.py --trace "$r/azure_trace_dev_1day.csv" --output_dir "$r/forecasts" --workers 4
python "$r/run_matrix.py"
python "$r/summarize.py"
```

Lệnh chạy cấu hình chốt bằng runner gốc của repo

```powershell
$ltua = 0..2 | ForEach-Object { "controller.regions.$_.arbiter=global_arbiter_ARIMA_checking" }
python run.py controller=us3-4models trace=random_trace trace.filename=azure_trace_dev_1day "trace.path=$r/azure_trace_dev_1day.csv" performance_model.db_path=data/perf_model_4models.csv global_arbiter.theta_file=data/theta_tps_v2.csv "global_arbiter.arima_traces=$r/forecasts" global_arbiter.forecast_mode=online global_arbiter.epsilon=0.9 long_term_scaling=True end_time=90000 "output_dir=$r/replay" @ltua
```
