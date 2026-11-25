"""Số tham khảo Fig. 16b (KHÔNG dùng để chấm): TTFT P95 IW Llama-2 theo khối 3 h, ngày thường so với cuối tuần, 4 bài week.
TTFT như analyze_s4 (cột ttft, chưa trừ độ trễ router) để khớp RESULTS; giờ đến = completion_time − response_time; trace bắt đầu thứ Sáu.
Dùng: python fig16b_week.py <thư mục week> <csv ra>"""
import glob
import sys

import pandas as pd

d, out = sys.argv[1], sys.argv[2]
RUNS, DAYS, M = ["reactive", "lt_i", "lt_u", "lt_ua"], ["T2", "T3", "T4", "T5", "T6", "T7", "CN"], "llama2-70b"
COLS = ["completion_time", "response_time", "ttft", "workload_type", "model_type"]
rows, pooled = [], {}
for r in RUNS:
    g = pd.concat((pd.read_csv(f, usecols=COLS) for f in sorted(glob.glob(f"{d}/{r}/global_router/*.csv"))), ignore_index=True)
    g = g[(g.workload_type == "prod") & (g.model_type == M)]
    t = g.completion_time - g.response_time
    g = g.assign(bin=(t // 10800).astype(int), day=(t // 86400).astype(int))
    g = g[g.day < 7]
    g["we"] = g.day.map(lambda x: DAYS[(x + 4) % 7] in ("T7", "CN"))
    print(f"{r}: TTFT P95 cả tuần {g.ttft.quantile(.95):.2f} s (kiểm với S4)")
    b = g.groupby("bin").agg(p95=("ttft", lambda x: x.quantile(.95)), we=("we", "first"))
    rows.append(b.p95.rename(r))
    for k, sub in (("ngày thường", g[~g.we]), ("cuối tuần", g[g.we])):
        bb = b[b.we == (k == "cuối tuần")].p95
        pooled[(r, k)] = (sub.ttft.quantile(.95), bb.median(), bb.max())
    del g
t = pd.concat(rows, axis=1)
t.index = [f"{DAYS[(i * 3 // 24 + 4) % 7]} {i * 3 % 24:02d}h" for i in t.index]
t.to_csv(out)
print(t.round(2).to_string())
for k in ("ngày thường", "cuối tuần"):
    print(f"{k}: " + "; ".join(f"{r} P95 gộp {pooled[(r, k)][0]:.2f} s, trung vị khối 3 h {pooled[(r, k)][1]:.2f} s, max khối {pooled[(r, k)][2]:.2f} s" for r in RUNS))
for k in ("ngày thường", "cuối tuần"):
    print(f"LT-UA − LT-U {k}: P95 gộp {pooled[('lt_ua', k)][0] - pooled[('lt_u', k)][0]:+.2f} s, trung vị khối 3 h {pooled[('lt_ua', k)][1] - pooled[('lt_u', k)][1]:+.2f} s")
