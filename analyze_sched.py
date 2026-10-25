"""
So sánh bộ lập lịch hàng đợi (§7.2.6, Fig. 15): Q3 TTFT và % vi phạm SLA theo tầng IW-F / IW-N.
Hướng của bài báo: FCFS vi phạm IW-F > IW-N; PF ít vi phạm IW-F nhất nhưng IW-N nhiều nhất;
EDF và DPA nằm giữa (cân bằng hơn).

Dùng: python analyze_sched.py results/sched/fcfs results/sched/edf results/sched/pf results/sched/dpa
"""
import glob
import os
import sys

import pandas as pd

from analyze_s4 import ROUTING_DELAY, sla_of

TIER = {1: "IW-F", 60: "IW-N", 6: "IW-N"}     # SLA TTFT (giây) -> tầng: §2.2 (1 s, 60 s); 6 s = kịch bản phụ §7.2.6

rows = []
for run in sys.argv[1:]:
    g = pd.concat(pd.read_csv(f) for f in glob.glob(f"{run}/global_router/*.csv"))
    g = g[g.workload_type == "prod"]
    g["sla"] = sla_of(g)
    for sla, tier in TIER.items():
        x = g[g.sla == sla].ttft - ROUTING_DELAY
        if x.empty:      # mỗi kịch bản chỉ có một ngưỡng IW-N (60 s hoặc 6 s)
            continue
        rows.append({"policy": os.path.basename(run.rstrip("/\\")), "tier": tier, "n": len(x),
                     "ttft_q3": x.quantile(.75), "ttft_p95": x.quantile(.95), "sla_miss_%": 100 * (x > sla).mean()})
res = pd.DataFrame(rows).set_index(["policy", "tier"]).round(2)
print(res.unstack("tier").to_string())
