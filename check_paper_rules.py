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
import yaml


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


with open(f"{a.run}/run.log", encoding="utf-8", errors="replace") as log:
    lines = [line for line in log if "SCALE_EVENT," in line or "SCALEUP_WASTE," in line]
events = pd.DataFrame(
    [line.strip().split("SCALE_EVENT,", 1)[1].split(",") for line in lines if "SCALE_EVENT," in line],
    columns=["timestamp", "region", "model", "trigger", "action",
             "ready_before", "pending_before", "ready_after", "pending_after"],
)
for column in ["timestamp", "ready_before", "pending_before", "ready_after", "pending_after"]:
    events[column] = pd.to_numeric(events[column])

# 1. Kiểm tra mẫu số máy đang phục vụ và quyết định co giãn (gồm cả máy đang chờ).
mem = concat(f"{a.run}/memory/*.csv")
parts = mem.instance.str.split("_")
mem["ep"] = parts.str[0] + "_" + parts.str[1]
single_region = parts.str[0].nunique() == 1
ready = mem[mem.time > 900].groupby(["ep", "time"]).instance.nunique().droplevel("time")
allocated = events.assign(ep=events.region + "_" + events.model).set_index("ep")
states = pd.concat([allocated.ready_before + allocated.pending_before, allocated.ready_after + allocated.pending_after])
counts = pd.concat([ready, states]).groupby(level=0).max()
allocated_minimum = states.groupby(level=0).min()
ready_minimum = ready.groupby(level=0).min()
config_file = os.path.join(a.run, ".hydra", "config.yaml")
limits = {}
cooldown = 15
if os.path.isfile(config_file):
    with open(config_file, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    cooldown = config.get("scaling_interval", cooldown)
    limits = {
        f"{region['region_name']}_{endpoint['model_name']}":
            (endpoint.get("min_instances", 2), endpoint.get("max_instances"))
        for region in config["controller"]["regions"] for endpoint in region["model_endpoints"]
    }
over, under = {}, {}
for ep, count in counts.items():
    legacy_cap = (16 if ep.endswith("-p") else 4) if a.siloed else 20
    minimum, maximum = limits.get(ep, (2, legacy_cap if single_region else None))
    if maximum is not None and count > maximum:
        over[ep] = int(count)
    if allocated_minimum.get(ep, minimum) < minimum or ready_minimum.get(ep, 2) < 2:
        under[ep] = int(min(allocated_minimum.get(ep, minimum), ready_minimum.get(ep, minimum)))
check("Số instance trong giới hạn", not over and not under,
      f"vượt trần {over or 'không'}, dưới sàn {under or 'không'}")

# 2. NIW không được thả trước thời điểm gửi (§6.2).
g = concat(f"{a.run}/global_router/*.csv")
t = pd.read_csv(a.trace, usecols=["request_id", "arrival_timestamp", "workload_type"]).set_index("request_id")
niw = g[g.workload_type == "dev"].join(t.arrival_timestamp, on="request_id")
early = (niw.completion_time - niw.response_time < niw.arrival_timestamp - 1e-6).sum()
check("NIW không chạy trước khi gửi", early == 0, f"{early} / {len(niw)} request vi phạm")

# 3. Quyết định theo request chịu cooldown. LT-I có thể đổi nhiều instance cùng mốc giờ.
gaps = []
if not events.empty:
    reactive = events[events.trigger == "request"].sort_values("timestamp")
    gaps = list(reactive.groupby(["region", "model"]).timestamp.diff().dropna())
else:
    # Kết quả cũ chỉ ghi thời điểm tăng máy. Suy ra lần giảm từ ảnh chụp trạng thái.
    files = glob.glob(f"{a.run}/arbiters/*/*.csv")
    arb = pd.concat(pd.read_csv(f).assign(region=os.path.basename(os.path.dirname(f))) for f in files)
    arb = arb.sort_values("timestamp", kind="stable")
    arb["prod"] = arb["prod"].astype(int)
    ups = [line.strip().split("SCALEUP_WASTE,", 1)[1].split(",") for line in lines if "SCALEUP_WASTE," in line]
    ups = pd.DataFrame([(float(u[0]), u[1], u[4] if len(u) > 4 else None) for u in ups],
                       columns=["timestamp", "model", "region"])
    for (region, model), x in arb.groupby(["region", "model"]):
        downs = x[x["prod"].diff().fillna(0) < 0].timestamp
        up = ups[(ups.model == model) & (ups.region.isna() | (ups.region == region))].timestamp
        gaps += list(pd.concat([downs, up]).drop_duplicates().sort_values().diff().dropna())
if events.empty:
    short = sum(gap < cooldown - 1e-6 for gap in gaps)
    rule = f"≥ {cooldown}"
else:
    short = sum(gap <= cooldown for gap in gaps)
    rule = f"> {cooldown}"
check(f"Cooldown {rule} s giữa các lần co giãn", short == 0,
      f"{len(gaps)} khoảng cách, {short} vi phạm, nhỏ nhất {min(gaps) if gaps else float('nan'):.3f} s")

# 4. Mọi IW và NIW đều được xử lý (§4: cả hai cách chạy hết trace).
n_trace = t.workload_type.value_counts()
done = g.workload_type.value_counts()
for wt, name in [("prod", "IW"), ("dev", "NIW")]:
    ratio = done.get(wt, 0) / n_trace.get(wt, 1)
    check(f"{name} hoàn thành trong ngày", ratio > 0.999, f"{done.get(wt, 0):,} / {n_trace.get(wt, 0):,} ({ratio:.1%})")

sys.exit(0 if all(results) else 1)
