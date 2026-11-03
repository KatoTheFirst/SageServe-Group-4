"""§7.2.6: phần vi phạm IW-F không lập lịch nào tránh được – request IW-F có thời gian prefill tối thiểu (không chờ) > 1 s.
Prefill tối thiểu theo độ dài prompt = phân vị 1% của (ttft − trễ định tuyến) trong từng nhóm 256 token, đo trên bài FCFS.
Dùng: python experiments/analyze_sched_floor.py D:/SageServe_results/v2/full/sched/sla60 traces/composed_day_3regions_12to15_v2.csv"""
import glob
import sys

import numpy as np
import pandas as pd

root, trace = sys.argv[1], sys.argv[2]
tr = pd.read_csv(trace)
total = 0
n_all = 0
for m in ("bloom-176b", "llama2-70b"):
    d = pd.concat(pd.read_csv(f) for f in glob.glob(f"{root}/fcfs/detailed/*_{m}_*/*.csv"))
    floor = (d.ttft_times - d.queue_times).groupby(d.prompt_sizes // 256).quantile(.01)
    t = tr[(tr.model_type == m) & (tr.scenario == "IW-F")]
    over = floor.reindex(t.prompt_size // 256).values > 1
    total += over.sum()
    n_all += len(t)
    print(f"{m}: IW-F {len(t)}, prefill tối thiểu > 1 s: {100 * np.mean(over):.1f}%")
print(f"Mọi mô hình (Llama-3.x không vượt 1 s): {100 * total / len(tr[tr.scenario == 'IW-F']):.1f}% request IW-F")
