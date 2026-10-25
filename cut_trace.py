"""
Cắt một cửa sổ giờ [start_h, end_h) của trace và đặt lại gốc thời gian về 0 (dùng cho bài chạy ngắn ở giờ cao điểm).
Trace dùng LT cần sinh lại dự báo cho bản cắt (generate_causal_arima_forecasts.py).

Dùng: python cut_trace.py traces/composed_day_3regions.csv 12 15 traces/composed_day_3regions_12to15.csv
"""
import sys

import pandas as pd

src, start_h, end_h, dst = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
t = pd.read_csv(src, dtype={"regions": str})
t = t[(t.arrival_timestamp >= start_h * 3600) & (t.arrival_timestamp < end_h * 3600)].copy()
t["arrival_timestamp"] = (t.arrival_timestamp - start_h * 3600).round(3)
t["request_id"] = range(len(t))
t.to_csv(dst, index=False)
print(f"[+] {dst}: {len(t):,} request, giờ {start_h:g}–{end_h:g} của {src}")
