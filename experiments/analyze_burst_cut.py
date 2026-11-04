"""Pha 3, burst trên bản cắt: 1 burst x8 10 phút trong hoặc ngoài 20 phút cuối giờ. In instance-hours, vi phạm, P95, thời gian bộ nhớ hồi về < 70%.
Dùng: python experiments/analyze_burst_cut.py D:/SageServe_results/v2/sens2"""
import glob
import os
import sys

import pandas as pd

sys.path.insert(0, os.getcwd())
from analyze_s4 import ROUTING_DELAY, analyze, sla_of

root = sys.argv[1]
for name, start in (("burst_in", 6000), ("burst_out", 4200)):
    print(f"== {name}: burst tại giây {start}")
    for k in ("reactive", "lt_u", "lt_ua", "lt_ua_nodown"):
        d = f"{root}/{name}/{k}"
        r = analyze(d, 1)[0]
        m = pd.concat(pd.read_csv(f, usecols=["time", "instance", "memory", "max_memory"]) for f in glob.glob(f"{d}/memory/*.csv"))
        m["model"] = m.instance.str.split("_").str[1]
        rec = {}
        for model in ("llama2-70b", "bloom-176b"):
            u = m[(m.model == model) & (m.time >= start)].groupby("time")[["memory", "max_memory"]].sum()
            u = u.memory / u.max_memory
            high = u[u > 0.7]
            rec[model] = float(high.index.max() - start) if len(high) else 0.0
        print(f"{k:13s} IH {r.instance_hours.sum():7.2f} | SLA L2 {r['iw_sla_miss_%']['llama2-70b']:5.2f} Bl {r['iw_sla_miss_%']['bloom-176b']:5.2f} | P95 L2 {r.iw_ttft_p95['llama2-70b']:7.1f} Bl {r.iw_ttft_p95['bloom-176b']:7.1f} | hồi bộ nhớ L2 {rec['llama2-70b']:6.0f} s Bl {rec['bloom-176b']:6.0f} s")
