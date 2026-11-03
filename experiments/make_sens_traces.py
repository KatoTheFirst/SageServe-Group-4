"""Pha 3 (SENSITIVITY.md): biến thể trace từ bản cắt v2 12–15h, `traces/composed_day_3regions_12to15_v2.csv`.
sens_flat, sens_spike: dạng tải trong phút phẳng / có gai (IW); sens_rate50, sens_rate150: tải ±50%;
sens_burst_in, sens_burst_out: 1 burst x8 dài 10 phút trong / ngoài 20 phút cuối giờ.
Dùng: python experiments/make_sens_traces.py [--out_dir traces]  (chạy từ thư mục repo)"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import make_trace_v2 as V

BASE = "traces/composed_day_3regions_12to15_v2.csv"


def save(x, n, out):
    x = x.sort_values("arrival_timestamp", kind="stable").reset_index(drop=True)
    x["request_id"] = x.index
    x.to_csv(f"{out}/sens_{n}.csv", index=False)
    print(n, len(x))


def sens(d, out):
    r = np.random.default_rng(3)          # một bộ sinh dùng chung, theo thứ tự flat → spike → rate150
    save(V.reshape_minutes(d.copy(), d.scenario != "NIW", lambda g: np.ones(60), r), "flat", out)
    save(V.reshape_minutes(d.copy(), d.scenario != "NIW", V.spike_weights([1.77, 1.77]), r), "spike", out)
    save(d.sample(frac=.5, random_state=3), "rate50", out)
    extra = d.sample(frac=.5, random_state=4).copy()
    extra["arrival_timestamp"] = (extra.arrival_timestamp + r.uniform(0, 60, len(extra))).clip(0, 10799.9).round(3)
    save(pd.concat([d, extra]), "rate150", out)


def burst(d, out):
    for n, start in (("in", 3600 + 2400), ("out", 3600 + 600)):
        w = d[(d.workload_type == "prod") & (d.arrival_timestamp >= start) & (d.arrival_timestamp < start + 600)]
        r = np.random.default_rng(5)
        p = [d]
        for _ in range(7):
            c = w.copy()
            c["arrival_timestamp"] = (start + r.random(len(c)) * 600).round(3)
            p.append(c)
        o = pd.concat(p, ignore_index=True).sort_values("arrival_timestamp", kind="stable").reset_index(drop=True)
        o["request_id"] = o.index
        o.to_csv(f"{out}/sens_burst_{n}.csv", index=False)
        print(f"burst_{n}", len(o))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", default="traces")
    a = ap.parse_args()
    d = pd.read_csv(BASE, dtype={"regions": str})
    sens(d, a.out_dir)
    burst(d, a.out_dir)


if __name__ == "__main__":
    main()
