"""Pha 5 (D16–D18): chiến lược × dự báo (ARIMA, oracle, oracle_smooth) × trace (lt = trace chính, nov2024 = trace Nov).
Mỗi dòng: instance-hours so với Reactive cùng trace (Llama-2 và tổng 4 mô hình), vi phạm SLA IW, TTFT Q3/P95 của Llama-2.
Dùng: python experiments/analyze_oracle.py D:/SageServe_results/v2/full [--oracle_root E:/SageServe_results_p5] [--out bảng.csv]
Thư mục: ARIMA = <R>/<trace>/<chiến lược>, oracle = <O>/oracle/<trace>/<chiến lược>, oracle_smooth = <O>/oracle_smooth/<trace>/<chiến lược> (O = --oracle_root)."""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyze_s4 import analyze

L2 = "llama2-70b"
FORECASTS = {"ARIMA": "{R}/{t}/{s}", "oracle": "{O}/oracle/{t}/{s}", "oracle_smooth": "{O}/oracle_smooth/{t}/{s}"}


def row(base, run):
    """base, run: bảng thứ nhất của analyze_s4.analyze() cho Reactive và cho bài cần so."""
    return {"ih_l2": run.instance_hours[L2], "ih_l2_vs_R_%": 100 * (run.instance_hours[L2] / base.instance_hours[L2] - 1),
            "ih_total": run.instance_hours.sum(), "ih_total_vs_R_%": 100 * (run.instance_hours.sum() / base.instance_hours.sum() - 1),
            "miss_l2_%": run["iw_sla_miss_%"][L2], "ttft_q3_l2": run.iw_ttft_q3[L2], "ttft_p95_l2": run.iw_ttft_p95[L2]}


def table(R, traces=("lt", "nov2024"), strategies=("lt_i", "lt_u", "lt_ua"), O=None):
    """O: thư mục gốc của bài oracle nếu khác R (Pha 5 ghi oracle ở ổ khác vì D: đầy)."""
    O = O or R
    rows = []
    for t in traces:
        base = analyze(f"{R}/{t}/reactive", 1)[0]
        rows.append({"trace": t, "strategy": "reactive", "forecast": "-", **row(base, base)})
        for s in strategies:
            for f, pattern in FORECASTS.items():
                d = pattern.format(R=R, O=O, t=t, s=s)
                if os.path.isdir(d):
                    rows.append({"trace": t, "strategy": s, "forecast": f, **row(base, analyze(d, 1)[0])})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--oracle_root", help="mặc định = root")
    ap.add_argument("--out")
    a = ap.parse_args()
    t = table(a.root, O=a.oracle_root).round(2)
    print(t.to_string(index=False))
    if a.out:
        t.to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
