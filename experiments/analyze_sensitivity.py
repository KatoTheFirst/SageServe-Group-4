"""Pha 3: bảng độ nhạy khoảng cách Reactive − LT-UA (instance-hours) và lãng phí khi tăng máy. Bỏ giờ đầu.
Dùng: python experiments/analyze_sensitivity.py D:/SageServe_results/v2/sens [--out SENS.csv]"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.getcwd())
from analyze_s4 import analyze


def waste(run):
    t = {"reclaim_spot": 0.0, "spin_up": 0.0}
    n = 0
    for line in open(f"{run}/run.log", encoding="utf-8", errors="ignore"):
        if "SCALEUP_WASTE," in line:
            at, _, kind, sec = line.strip().split("SCALEUP_WASTE,")[1].split(",")[:4]
            if float(at) >= 3600:
                t[kind] += float(sec) / 3600
                n += 1
    return t["reclaim_spot"], t["spin_up"], n


def row(run):
    r = analyze(run, 1)[0]
    w = waste(run)
    return {"ih": r.instance_hours.sum(), "ih_llama2": r.instance_hours["llama2-70b"], "ih_bloom": r.instance_hours["bloom-176b"],
            "sla_l2": r["iw_sla_miss_%"]["llama2-70b"], "sla_bl": r["iw_sla_miss_%"]["bloom-176b"],
            "p95_l2": r.iw_ttft_p95["llama2-70b"], "p95_bl": r.iw_ttft_p95["bloom-176b"],
            "waste": w[0] + w[1], "spin_up_h": w[1], "events": w[2]}


ap = argparse.ArgumentParser()
ap.add_argument("root")
ap.add_argument("--out")
a = ap.parse_args()
rows = {}
for n in sorted(os.listdir(a.root)):
    for k in ("reactive", "lt_ua"):
        p = f"{a.root}/{n}/{k}"
        if os.path.isdir(p):
            rows[(n, k)] = row(p)
d = pd.DataFrame(rows).T
base = d.loc[("base", "reactive")]
out = []
for n in d.index.levels[0]:
    r = d.loc[(n, "reactive")] if (n, "reactive") in d.index else base
    u = d.loc[(n, "lt_ua")] if (n, "lt_ua") in d.index else None
    x = {"yếu tố": n, "Reactive IH": r.ih, "Reactive lãng phí": r.waste, "Reactive sự kiện": r.events}
    if u is not None:
        x |= {"LT-UA IH": u.ih, "khoảng cách tổng %": 100 * (1 - u.ih / r.ih), "khoảng cách Llama-2 %": 100 * (1 - u.ih_llama2 / r.ih_llama2),
              "khoảng cách Bloom %": 100 * (1 - u.ih_bloom / r.ih_bloom), "LT-UA lãng phí": u.waste, "giảm lãng phí %": 100 * (1 - u.waste / r.waste) if r.waste else float("nan"),
              "SLA L2 R→U": f"{r.sla_l2:.1f}→{u.sla_l2:.1f}", "P95 L2 R→U": f"{r.p95_l2:.1f}→{u.p95_l2:.1f}"}
    out.append(x)
res = pd.DataFrame(out).round(2)
print(res.to_string(index=False))
if a.out:
    res.to_csv(a.out, index=False)
