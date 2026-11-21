# SageServe Task 7 — Forecast v2 (retrain / burst / weekend)

## Phạm vi

Module **độc lập**, không sửa `generate_causal_arima_forecasts.py`, `global_arbiter.py` hay các file cũ của nhóm. Cột vùng, workload, đơn vị TPM và định dạng forecast tương thích code ở repo nhóm (đã đối chiếu với `generate_causal_arima_forecasts.py` / `global_arbiter.py` trên `main`, 21/11/2026).

- **v1 đối chứng:** native ARIMA lịch phát hành mỗi 60 phút, fit trên 60 phút trước đó, AIC chọn trong 5 bậc như `generate_causal_arima_forecasts.py` (một phần có các tham số khác với module Task 4 trước đây; không lấy nhầm MAPE cũ để coi là cùng protocol).
- **v2:** ARIMA fit 180 phút với Hampel làm sạch spike đơn độc; giữ burst kéo dài, khi burst mới xảy ra có thể retrain sớm và tăng forecast ngắn hạn rồi suy giảm; thông thường retrain 2 giờ trong tuần, mỗi giờ cuối tuần; kết hợp quan sát *quá khứ* cùng nhóm weekday/weekend khi có. Không có history phù hợp thì không tự bịa seasonal profile.
- **Các giới hạn:** Hành vi cuối tuần ở trace 7 ngày không có thứ Bảy/Chủ nhật của tuần trước; mới kiểm tra qua category weekday/weekend. Tính hiệu quả phải đo bằng backtest trên trace thật; thiết kế này **không bảo đảm** MAPE giảm. Forecast issue_time và timestamp tuân thủ định dạng simulator; giờ 0 dùng warmup có nhìn trước (giống native), và **không tính vào backtest**.
- **So sánh công bằng:** cùng series, 60 phút forecast, cùng origin, cùng actual; tính *minute MAPE* chỉ trên actual >0, *hourly peak MAPE* chỉ trên actual peak >0; RMSE và underpeak kèm theo. β NIW không cộng vào MAPE của IW.

## Cài đặt / kiểm thử (PowerShell, Python 3.11)

Trong thư mục gốc repo `SageServe-Group-4-Git`:

```powershell
# Copy toàn bộ thư mục Task 7 vào repository, ví dụ task7_forecast_v2/
.\.venv\Scripts\python.exe -m pip install numpy pandas statsmodels pytest
.\.venv\Scripts\python.exe -m pytest .\task7_forecast_v2\tests -q
```

### A. Chạy trên trace v2 **7 ngày** (đề xuất để thấy cuối tuần)

Theo `REPRODUCE.md`, `composed_week_3regions_v2.csv` bắt đầu `--start_day 0` (thứ Hai), nên `--start-weekday 0`.

```powershell
.\.venv\Scripts\python.exe .\task7_forecast_v2\forecast_v2.py `
  --trace .\traces\composed_week_3regions_v2.csv `
  --start-weekday 0 `
  --evaluation-start-hour 24 `
  --eval-last-hours 72 `
  --out .\results\task7_forecast_v2_week `
  --write-simulator-forecasts --write-niw
```

### B. Chạy trên trace v2 **1 ngày** (kiểm tra ngày thường; không kiểm tra được hiệu ứng cuối tuần)

Theo repo `compose_trace.py --start_day 4` (thứ Sáu), dùng `--start-weekday 4`:

```powershell
.\.venv\Scripts\python.exe .\task7_forecast_v2\forecast_v2.py `
  --trace .\traces\composed_day_3regions_v2.csv `
  --start-weekday 4 `
  --evaluation-start-hour 6 `
  --eval-last-hours 0 `
  --out .\results\task7_forecast_v2_day `
  --write-simulator-forecasts --write-niw
```

`--write-simulator-forecasts` sẽ tạo `simulator_forecasts/final_{model}_prod_1minute_region{r}_arima.csv`; `--write-niw` tạo `final_{model}_dev_region{r}_exact.csv`. Để **tích hợp vào simulator**, trỏ tham số `global_arbiter.arima_traces` tới thư mục `results/task7_forecast_v2_week/simulator_forecasts` và giữ `global_arbiter.forecast_mode=offline`. **Không ghi đè** `traces/forecasts/...` gốc. Dự báo giờ 0 theo native repo có warmup không nhân quả, xem ghi chú trên.

## File kết quả

- `mape_v1_v2_comparison.csv`: MAPE/RMSE v1, v2 và độ chênh theo từng model/region.
- `mape_v1_v2_overall.csv`: MAPE, peak-MAPE, RMSE, underpeak tổng hợp; `v2 - v1 < 0` là cải thiện.
- `mape_v1_v2_weekday_weekend.csv`: chia theo hai nhóm weekday/weekend trong cùng test.
- `mape_v1_v2_by_pair.csv`: tách rõ từng policy và mỗi model/region.
- `mape_v1_v2_detail.csv`: một dòng mỗi origin × policy, gồm thời gian, burst, retrain, kiểm tra cuối tuần.
- `minute_predictions_v1_v2.csv`: dùng để kiểm tra trực tiếp tương quan actual/forecast.
- `metadata.json`: SHA-256, cài đặt và phạm vi backtest.
- `simulator_forecasts/`: chỉ tạo khi bật cờ; dùng cho MILP/LT-UA.

## Phân tích nhanh

```powershell
Import-Csv .\results\task7_forecast_v2_week\mape_v1_v2_overall.csv | Format-Table -AutoSize
Import-Csv .\results\task7_forecast_v2_week\mape_v1_v2_comparison.csv | Format-Table -AutoSize
Import-Csv .\results\task7_forecast_v2_week\mape_v1_v2_detail.csv |
    Group-Object method,is_weekend | Select-Object Name,Count
```

### Cần kiểm tra trước khi nộp

1. Cả v1 và v2 đều có số cửa sổ bằng nhau, không có lỗi AIC nghiêm trọng hoặc NaN trên toàn bộ cửa sổ.
2. So sánh MAPE riêng weekday/weekend, peak MAPE, underpeak; giảm minute MAPE không đồng nghĩa giảm thiếu peak ở ILP.
3. Nếu MAPE v2 không cải thiện, báo đúng số liệu và điều chỉnh ngưỡng / window trên phần train-validation *khác* tập test; không tuning trực tiếp lên test.
4. Chạy simulator LT-U/LT-UA với file forecast mới và xem TTFT, SLA, instance-hours là bước tiếp theo, **không** tự suy ra từ MAPE.
5. Dữ liệu trace lớn, thời gian chạy có thể đáng kể do baseline v1 tối ưu AIC nhiều lần.

### Demo smoke test (DỮ LIỆU GIẢ LẬP, KHÔNG DÙNG ĐỂ BÁO CÁO THỰC NGHIỆM)

`examples/demo_trace_SYNTHETIC.csv` chỉ dùng thử pipeline; kết quả trong `examples/demo_output` không phải trace nhóm và không được coi là số MAPE của bài nghiên cứu.
