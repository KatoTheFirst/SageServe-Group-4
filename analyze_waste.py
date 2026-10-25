"""
F12 (§7.2.4): GPU-giờ lãng phí khi tăng máy = tổng thời gian GPU đã cấp nhưng instance chưa phục vụ
(khởi động 600 s, lấy lại spot ~60 s), cộng từ các dòng SCALEUP_WASTE trong run.log.
Bài báo: SageServe (LT) giảm ~70% so với Reactive.

Dùng: python analyze_waste.py results/lt_day/reactive results/lt_day/lt_ua ...
"""
import os
import sys

import pandas as pd

rows = []
for run in sys.argv[1:]:
    for line in open(os.path.join(run, "run.log"), encoding="utf-8", errors="ignore"):
        if "SCALEUP_WASTE," in line:
            t, model, kind, sec = line.strip().split("SCALEUP_WASTE,")[1].split(",")[:4]   # (+ vùng ở bản mới)
            rows.append({"run": os.path.basename(run.rstrip("/\\")), "model": model.removesuffix("-p").removesuffix("-d"),
                         "kind": kind, "hours": float(sec) / 3600})
d = pd.DataFrame(rows)
res = d.pivot_table(index="run", columns="kind", values="hours", aggfunc="sum", fill_value=0)
res["events"] = d.groupby("run").size()
res["total_gpu_hours"] = res.drop(columns="events").sum(axis=1)
print(res.round(2).to_string())
