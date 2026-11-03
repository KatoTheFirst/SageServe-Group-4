"""Vi phạm SLA IW theo giờ: Reactive so với LT-U, kèm tỉ lệ đỉnh dự báo ARIMA / đỉnh thực (forecast_log.csv của LT-UA).
In các giờ LT-U vi phạm thêm nhiều nhất và tỉ lệ vi phạm SLA một tầng 60 s (D4).
Dùng: python experiments/analyze_hourly_miss.py D:/SageServe_results/v2/full/lt [--model llama2-70b] [--top 5]"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyze_s4 import ROUTING_DELAY, concat, sla_of

ap = argparse.ArgumentParser()
ap.add_argument("exp")
ap.add_argument("--model", default="llama2-70b")
ap.add_argument("--top", type=int, default=5)
a = ap.parse_args()

f = pd.read_csv(f"{a.exp}/lt_ua/forecast_log.csv")
f = f[(f.model == a.model) & (f.hour >= 1)].groupby("hour")[["pred_peak_tpm", "actual_peak_tpm"]].sum()
f["ratio"] = f.pred_peak_tpm / f.actual_peak_tpm
for r in ("reactive", "lt_u", "lt_ua"):
    g = concat(f"{a.exp}/{r}/global_router/*.csv")
    g = g[(g.workload_type == "prod") & (g.model_type == a.model)]
    ttft = g.ttft - ROUTING_DELAY
    hour = ((g.completion_time - g.response_time) // 3600).astype(int)
    f[f"miss_{r}"] = (ttft > sla_of(g)).groupby(hour).sum()
    print(f"{r}: vi phạm SLA theo tầng {100 * (ttft > sla_of(g)).mean():.2f}%, SLA một tầng 60 s {100 * (ttft > 60).mean():.2f}%")
f["extra"] = f.miss_lt_u - f.miss_reactive
top = f.extra.nlargest(a.top)
print(f"LT-U vi phạm thêm (ròng cả kỳ): {int(f.extra.sum())}; {a.top} giờ thêm nhiều nhất {sorted(top.index.tolist())}: {int(top.sum())}, "
      f"đỉnh dự báo / đỉnh thực ở các giờ đó {f.ratio[top.index].min():.2f}–{f.ratio[top.index].max():.2f}; mọi giờ: trung vị {f.ratio.median():.2f}")
