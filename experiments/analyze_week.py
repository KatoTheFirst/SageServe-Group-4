"""Bài `week` (§7.2.7): instance-hours và vi phạm SLA IW theo từng ngày, mỗi chiến lược.
Dùng: python experiments/analyze_week.py <thư mục week> [--day0 4]   (day0: thứ của ngày đầu, 0 = thứ Hai; trace bắt đầu thứ Sáu)
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyze_s4 import ROUTING_DELAY, concat, sla_of

RUNS = ["reactive", "lt_i", "lt_u", "lt_ua"]
DAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]


def per_day(d, day0):
    mem = concat(f"{d}/memory/*.csv")
    mem["model"] = mem["instance"].str.split("_").str[1]
    mem = mem[mem.time < 7 * 86400]     # bỏ mẫu cuối đúng mốc 7 ngày (ngày thứ 8 giả)
    count = mem[mem.time >= 3600].groupby(["model", "time"]).instance.nunique().reset_index()    # bỏ giờ 0 như analyze_s4 --skip_hours 1
    count["bin"] = count.time // 900
    per15 = count.groupby(["model", "bin"]).instance.max().reset_index()
    ih = (per15.groupby(per15.bin // 96).instance.sum() / 4).rename("ih")
    g = concat(f"{d}/global_router/*.csv")
    iw = g[g.workload_type == "prod"].copy()
    iw["miss"] = iw.ttft - ROUTING_DELAY > sla_of(iw)
    arrival = iw.completion_time - iw.response_time
    miss = (100 * iw.groupby(arrival // 86400).miss.mean()).rename("iw_miss_%")
    out = pd.concat([ih, miss], axis=1)
    out.index = [DAYS[(int(i) + day0) % 7] for i in out.index]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("week")
    ap.add_argument("--day0", type=int, default=4)
    a = ap.parse_args()
    t = pd.concat({r: per_day(f"{a.week}/{r}", a.day0) for r in RUNS}, axis=1)
    for r in RUNS[1:]:
        t[(r, "vs_reactive_%")] = 100 * (t[(r, "ih")] / t[("reactive", "ih")] - 1)
    print(t.round(2).to_string())
    wk = t.index.isin(["T7", "CN"])
    for name, rows in (("ngày thường", ~wk), ("cuối tuần", wk)):
        s = t[rows].xs("ih", axis=1, level=1).sum()
        print(f"{name}: " + ", ".join(f"{r} {s[r]:.1f} ({100 * (s[r] / s['reactive'] - 1):+.1f}%)" for r in RUNS))


if __name__ == "__main__":
    main()
