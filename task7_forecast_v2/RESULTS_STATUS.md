# Trạng thái so sánh Forecast v1/v2

- **Trace thật SageServe v2:** chưa có trong phiên làm việc này. Không có kết quả MAPE v2 trên trace thật để khẳng định mô hình tốt hơn.
- **V1 tham khảo từ Task 4 cũ:** MAPE ARIMA 88.27% (trung bình theo model-region, AIC 18 bậc, 60 phút history, 6 cửa sổ); **KHÔNG** phải v1 đối chứng dùng trong code mới, nên không lấy làm cột MAPE so sánh trực tiếp.
- **Demo SYNTHETIC:** v1 minute MAPE 27.76%, v2 20.42%; v1 peak-MAPE 33.54%, v2 44.53%. Chỉ để kiểm thử pipeline, 2 giờ đánh giá, không dùng trong báo cáo nghiên cứu.
- **Lệnh để thu kết quả thật:** xem README.md, dùng `traces/composed_week_3regions_v2.csv`, `--start-weekday 0`, `--eval-last-hours 72`.
- File `mape_v1_v2_comparison.csv` và `mape_v1_v2_overall.csv` sẽ được tự tạo sau khi thực thi bằng dữ liệu thật.
