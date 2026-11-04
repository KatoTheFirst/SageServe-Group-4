"""Bài `burst` cả ngày (§7.2.7, Fig. 16a): sau mỗi burst x8, thời gian đến khi bộ nhớ Llama-2/Bloom hồi về < 70%
và vi phạm SLA IW trong 1 giờ tính từ đầu burst.
Dùng: python experiments/analyze_burst_day.py D:/SageServe_results/v2/full/burst
Thời điểm burst: inject_burst.py trên composed_day_3regions_v2 (giây 7200, 55800, 65400)."""
import glob
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyze_s4 import ROUTING_DELAY, concat, sla_of

BURSTS = (7200, 55800, 65400)
WINDOW = 3 * 3600       # tìm lần cuối bộ nhớ > 70% trong 3 giờ sau burst (hoặc đến burst kế)

root = sys.argv[1]
for k in ("reactive", "lt_i", "lt_u", "lt_ua"):
    d = f"{root}/{k}"
    m = pd.concat(pd.read_csv(f, usecols=["time", "instance", "memory", "max_memory"]) for f in glob.glob(f"{d}/memory/*.csv"))
    m["model"] = m.instance.str.split("_").str[1]
    g = concat(f"{d}/global_router/*.csv")
    g = g[g.workload_type == "prod"]
    arrival = g.completion_time - g.response_time
    miss = g.ttft - ROUTING_DELAY > sla_of(g)
    cells = []
    for i, start in enumerate(BURSTS):
        end = min(start + WINDOW, BURSTS[i + 1] if i + 1 < len(BURSTS) else 86400)
        for model in ("llama2-70b", "bloom-176b"):
            u = m[(m.model == model) & (m.time >= start) & (m.time < end)].groupby("time")[["memory", "max_memory"]].sum()
            u = u.memory / u.max_memory
            high = u[u > 0.7]
            rec = float(high.index.max() - start) if len(high) else 0.0
            w = (g.model_type == model) & (arrival >= start) & (arrival < start + 3600)
            cells.append(f"{model[:5]} {rec:5.0f}s {100 * miss[w].mean():5.1f}%")
        cells.append("|")
    print(f"{k:9s} " + " ".join(cells))
