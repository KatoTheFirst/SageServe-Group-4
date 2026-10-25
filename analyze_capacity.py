"""
Đo năng lực 1 instance trong simulator: TPS đầu vào mỗi instance gánh theo từng phút, so với bộ nhớ hiệu dụng.
So sánh với bài báo §2.1 (8x A100): Llama2-70B 68–293 TPS, Bloom-176B 50–177 TPS (Q1–Q3).

Dùng: python analyze_capacity.py <thư mục kết quả> <trace.csv> [data/theta_tps.csv]
Đo θ: chạy Reactive trên giờ cao điểm của trace chính rồi truyền file θ (giữ θ cũ cho mô hình không lên 60%).
"""
import glob
import os
import sys

import pandas as pd

run, trace = sys.argv[1], sys.argv[2]
mem = pd.concat(pd.read_csv(f) for f in glob.glob(f"{run}/memory/*.csv"))
mem["model"] = mem["instance"].str.split("_").str[1].str.replace(r"-[pd]$", "", regex=True)
mem["minute"] = (mem.time // 60).astype(int)
per_t = mem.groupby(["model", "time"]).agg(minute=("minute", "first"), n=("instance", "nunique"),
                                          used=("memory", "sum"), cap=("max_memory", "sum"))
per_min = per_t.groupby(["model", "minute"]).agg(instances=("n", "mean"), used=("used", "mean"), cap=("cap", "mean"))
per_min["mem_util"] = per_min.used / per_min.cap

t = pd.read_csv(trace, usecols=["model_type", "arrival_timestamp", "prompt_size"])
t["minute"] = (t.arrival_timestamp // 60).astype(int)
tps = t.groupby(["model_type", "minute"]).prompt_size.sum().div(60).rename("input_tps")
tps.index.names = ["model", "minute"]
df = per_min.join(tps, how="inner")
df["tps_per_instance"] = df.input_tps / df.instances

rows = []
for m, x in df.groupby(level="model"):
    hot = x[x.mem_util.between(0.6, 0.8)]
    rows.append({"model": m, "instances_max": x.instances.max(), "mem_util_p95": x.mem_util.quantile(.95),
                 "tps/inst median": x.tps_per_instance.median(), "tps/inst max": x.tps_per_instance.max(),
                 "phút có bộ nhớ 60-80%": len(hot),
                 "tps/inst khi bộ nhớ 60-80%": hot.tps_per_instance.median() if len(hot) else None,
                 "extrap": (x.tps_per_instance * 0.7 / x.mem_util)[x.mem_util > 0.05].median()})
res = pd.DataFrame(rows)
# θ cho ILP (§5): TPS 1 instance gánh khi bộ nhớ hiệu dụng ở quanh ngưỡng tăng máy 70% (60–80%), đo trên bài
# Reactive của trace chính (bài đó tự giữ bộ nhớ quanh 70%). Mô hình không bao giờ lên 60% (luôn ở mức sàn) giữ θ cũ.
res["theta_tps"] = res["tps/inst khi bộ nhớ 60-80%"]
if len(sys.argv) > 3 and os.path.exists(sys.argv[3]):
    old = pd.read_csv(sys.argv[3]).set_index("model").theta_tps
    res["theta_tps"] = res.theta_tps.fillna(res.model.map(old))
res = res.round(2)
print(res.to_string(index=False))
if len(sys.argv) > 3:
    res[["model", "theta_tps"]].to_csv(sys.argv[3], index=False)
    print("[+] θ ->", sys.argv[3])
