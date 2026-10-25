"""
Kiểm tra trên kết quả mô phỏng rằng các quy tắc của bài báo (§4, §6.1-6.2) được tuân thủ.

Dùng: python check_paper_rules.py <thư mục kết quả> <trace.csv> [--siloed]
In PASS/FAIL cho từng quy tắc; thoát mã 1 nếu có FAIL.
"""
import argparse
import glob
import os
import sys

import pandas as pd


def concat(pattern):
    return pd.concat((pd.read_csv(f) for f in sorted(glob.glob(pattern))), ignore_index=True)


ap = argparse.ArgumentParser()
ap.add_argument("run")
ap.add_argument("trace")
ap.add_argument("--siloed", action="store_true")
a = ap.parse_args()
results = []


def check(name, ok, detail):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


# 1. Giới hạn số instance: Unified tối đa 20/mô hình; Siloed tối đa 16 (IW) + 4 (NIW); tối thiểu 2 (§4).
mem = concat(f"{a.run}/memory/*.csv")
mem["ep"] = mem.instance.str.split("_").str[1]
cnt = mem[mem.time > 900].groupby(["ep", "time"]).instance.nunique().groupby("ep").agg(["min", "max"])
cap = {ep: (16 if ep.endswith("-p") else 4) if a.siloed else 20 for ep in cnt.index}
over = {ep: int(r["max"]) for ep, r in cnt.iterrows() if r["max"] > cap[ep]}
under = {ep: int(r["min"]) for ep, r in cnt.iterrows() if r["min"] < 2}
check("Số instance trong giới hạn", not over and not under,
      f"vượt trần {over or 'không'}, dưới 2 {under or 'không'} (sau 15 phút đầu)")

# 2. NIW không được thả trước thời điểm gửi (§6.2).
g = concat(f"{a.run}/global_router/*.csv")
t = pd.read_csv(a.trace, usecols=["request_id", "arrival_timestamp", "workload_type"]).set_index("request_id")
niw = g[g.workload_type == "dev"].join(t.arrival_timestamp, on="request_id")
early = (niw.completion_time - niw.response_time < niw.arrival_timestamp - 1e-6).sum()
check("NIW không chạy trước khi gửi", early == 0, f"{early} / {len(niw)} request vi phạm")

# 3. Cooldown 15 s giữa hai QUYẾT ĐỊNH co giãn của cùng endpoint (§4). Máy tăng chỉ vào phục vụ sau thời gian lấy lại
#    spot/khởi động, nên dùng thời điểm quyết định: tăng = dòng SCALEUP_WASTE trong run.log, giảm = lúc số máy giảm (tức thì).
files = glob.glob(f"{a.run}/arbiters/*/*.csv")
arb = pd.concat(pd.read_csv(f).assign(region=os.path.basename(os.path.dirname(f))) for f in files)
arb = arb.sort_values("timestamp", kind="stable")  # giữ thứ tự log khi trùng thời điểm
arb["prod"] = arb["prod"].astype(int)
ups = [line.strip().split("SCALEUP_WASTE,")[1].split(",") for line in open(f"{a.run}/run.log", encoding="utf-8", errors="ignore")
       if "SCALEUP_WASTE," in line]
ups = pd.DataFrame([(float(u[0]), u[1], u[4] if len(u) > 4 else None) for u in ups], columns=["timestamp", "model", "region"])
gaps = []
for (region, model), x in arb.groupby(["region", "model"]):
    downs = x[x["prod"].diff().fillna(0) < 0].timestamp
    up = ups[(ups.model == model) & (ups.region.isna() | (ups.region == region))].timestamp
    # một quyết định có thể lấy 2 instance cùng lúc (lập deployment mới tối thiểu 2) -> gộp cùng thời điểm
    gaps += list(pd.concat([downs, up]).drop_duplicates().sort_values().diff().dropna())
short = sum(gp < 15 - 1e-6 for gp in gaps)
check("Cooldown ≥ 15 s giữa các lần co giãn", short == 0,
      f"{len(gaps)} khoảng cách, {short} khoảng < 15 s, nhỏ nhất {min(gaps) if gaps else float('nan'):.1f} s")

# 4. Mọi IW và NIW đều được xử lý (§4: cả hai cách chạy hết trace).
n_trace = t.workload_type.value_counts()
done = g.workload_type.value_counts()
for wt, name in [("prod", "IW"), ("dev", "NIW")]:
    ratio = done.get(wt, 0) / n_trace.get(wt, 1)
    check(f"{name} hoàn thành trong ngày", ratio > 0.999, f"{done.get(wt, 0):,} / {n_trace.get(wt, 0):,} ({ratio:.1%})")

sys.exit(0 if all(results) else 1)
