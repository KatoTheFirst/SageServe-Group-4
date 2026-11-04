"""
T29 / §2.1: θ = input TPS mỗi instance đạt được ở latency mục tiêu. Mục tiêu là TTFT P95 của Unified trong Table 1.
Mỗi mức tải: 1 vùng, số instance cố định, không co giãn, request IW lấy mẫu từ trace (giữ nguyên tỉ lệ IW-F/IW-N cả ngày).
Request chưa có TTFT khi bài kết thúc tính là vượt mục tiêu. θ nội suy tại điểm P95 cắt mục tiêu giữa hai mức liền kề.

Dùng: python benchmark_theta.py traces/composed_day_3regions.csv us1-4models data/theta_tps.csv --out results/theta_bench/a100
"""
import argparse
import concurrent.futures as cf
import glob
import os
import subprocess
import sys

import numpy as np
import pandas as pd

from compose_trace import COLS

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET_P95 = {"bloom-176b": 12.9, "llama2-70b": 34.5, "llama3.1-8b": 1.0, "llama3.2-3b": 1.0}     # Table 1, giây
ENDPOINT = {"llama2-70b": 0, "bloom-176b": 1, "llama3.1-8b": 2, "llama3.2-3b": 3}                 # thứ tự trong controller
INSTANCES = 6                # 2 deployment 3 instance (§4)
WARMUP, ARRIVE, DRAIN = 600, 2400, 1800
ROUTING_DELAY = 1            # configs/global_router/overheads/zero.yaml
LADDER = 100 * 1.25 ** np.arange(0, 32)      # 100 ... ~100k TPS/instance
REFINE = 10


def make_trace(iw, level, seed):
    """Poisson với input TPS/instance = level, mẫu request lấy có hoàn lại từ IW của mô hình."""
    rng = np.random.default_rng(seed)
    rate = level * INSTANCES / iw.prompt_size.mean()
    n = rng.poisson(rate * ARRIVE)
    df = iw.sample(n, replace=True, random_state=seed).reset_index(drop=True)
    df["arrival_timestamp"] = np.sort(rng.uniform(0, ARRIVE, n)).round(3)
    df["request_id"], df["regions"] = df.index, "012"
    return df[COLS]


def p95_with_unfinished(requested, finished_ttft):
    """TTFT P95 trên request đến trong cửa sổ đo; request chưa xong tính là vô cùng."""
    v = np.full(len(requested), np.inf)
    v[:len(finished_ttft)] = finished_ttft
    return float(np.quantile(v, 0.95, method="higher")) if len(v) else float("nan")


def crossing(levels, p95, target):
    """Điểm P95 cắt target (nội suy log giữa mức cuối còn đạt và mức đầu trượt); None nếu ngay mức thấp nhất đã trượt."""
    last = None
    for i, (l, p) in enumerate(zip(levels, p95)):
        if p > target:
            if last is None:
                return None
            lo, hi = levels[last], l
            if not np.isfinite(p):
                return float(lo)
            f = (np.log(target) - np.log(max(p95[last], 1e-9))) / (np.log(p) - np.log(max(p95[last], 1e-9)))
            return float(np.exp(np.log(lo) + f * (np.log(hi) - np.log(lo))))
        last = i
    return float(levels[last]) if last is not None else None


def run_level(model, level, iw, a, seed=0):
    tag = f"_bench_{os.path.basename(a.out)}_{model}_{level:.0f}"
    out = f"{a.out}/{model}/{level:.0f}"
    trace = f"{ROOT}/traces/{tag}.csv"
    df = make_trace(iw, level, seed)
    df.to_csv(trace, index=False)
    counts = [f"controller.regions.0.model_endpoints.{i}.instance_count={INSTANCES if m == model else 2}" for m, i in ENDPOINT.items()]
    cmd = [sys.executable, "run.py", "performance_model.db_path=data/perf_model_4models.csv", f"end_time={ARRIVE + DRAIN}",
           "trace=random_trace", f"trace.filename={tag}", f"controller={a.controller}", "short_term_scaling=False",
           "long_term_scaling=False", "scaling_level=0", f"output_dir={out}"] + counts
    os.makedirs(os.path.dirname(out), exist_ok=True)
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    os.remove(trace)
    if p.returncode or "TraceSimulator completed" not in p.stdout + p.stderr:
        raise RuntimeError(f"{tag}: {(p.stdout + p.stderr)[-1500:]}")
    g = pd.concat(pd.read_csv(f, usecols=["request_id", "ttft"]) for f in glob.glob(f"{out}/global_router/*.csv"))
    win = df[df.arrival_timestamp.between(WARMUP, ARRIVE)]
    ttft = g[g.request_id.isin(win.request_id)].ttft.values - ROUTING_DELAY
    return {"model": model, "level_tps": level, "requests": len(win), "finished": len(ttft),
            "ttft_p95": p95_with_unfinished(win, ttft)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("controller")
    ap.add_argument("theta_csv")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--models", nargs="*", default=list(TARGET_P95))
    ap.add_argument("--hour", type=int, help="Chỉ lấy mẫu request của giờ này (đo năng lực ở tỉ lệ IW-F/IW-N của giờ đó)")
    a = ap.parse_args()
    a.out = a.out.rstrip("/")
    t = pd.read_csv(a.trace, dtype={"regions": str})
    t = t[t.workload_type == "prod"]
    if a.hour is not None:
        t = t[t.arrival_timestamp // 3600 == a.hour]
    os.makedirs(a.out, exist_ok=True)
    rows = []
    cached = pd.read_csv(f"{a.out}/curve.csv") if os.path.exists(f"{a.out}/curve.csv") else pd.DataFrame()
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for model in a.models:                  # các mức tăng dần theo đợt, dừng ngay đợt có mức trượt
            iw, done = t[t.model_type == model], []
            if len(cached) and (cached.model == model).any():       # đã có đường cong thô
                rows += cached[cached.model == model].to_dict("records")
                continue
            # trên tổng tải IW giờ cao nhất thì 1 instance đã đủ, θ không còn ảnh hưởng ILP và mức tải cao chạy rất lâu
            peak = iw.prompt_size.groupby(iw.arrival_timestamp // 3600).sum().max() / 3600
            ladder = LADDER[:np.searchsorted(LADDER, peak) + 1]
            for i in range(0, len(ladder), a.workers):
                res = list(ex.map(lambda l: run_level(model, l, iw, a), ladder[i:i + a.workers]))
                done += res
                print(*[f"{model} {r['level_tps']:.0f}: P95 {r['ttft_p95']:.2f} ({r['finished']}/{r['requests']})" for r in res], sep="\n", flush=True)
                if any(r["ttft_p95"] > TARGET_P95[model] for r in res):
                    break
            rows += done
        # khuỷu rất dốc -> tinh chỉnh: thêm các mức giữa hai mức bao quanh điểm cắt
        for model in a.models:
            x = pd.DataFrame(rows).query("model == @model").sort_values("level_tps")
            over = x.ttft_p95.values > TARGET_P95[model]
            if not over.any() or over[0]:
                continue
            k = over.argmax()
            levels = np.linspace(x.level_tps.values[k - 1], x.level_tps.values[k], REFINE + 2)[1:-1]
            rows += list(ex.map(lambda l: run_level(model, l, t[t.model_type == model], a), levels))
    res = pd.DataFrame(rows).sort_values(["model", "level_tps"])
    res.to_csv(f"{a.out}/curve.csv", index=False)
    old = pd.read_csv(a.theta_csv).set_index("model").theta_tps
    theta = {m: crossing(x.level_tps.values, x.ttft_p95.values, TARGET_P95[m]) for m, x in res.groupby("model")}
    for m, v in theta.items():
        if v is None:
            raise SystemExit(f"{m}: mức thấp nhất đã vượt mục tiêu {TARGET_P95[m]} s")
        old[m] = round(v, 2)
    if "llama4-sub" in old:
        old["llama4-sub"] = old["llama2-70b"]     # §7.2.5: mô hình thứ 5 dùng profile Llama-2
    old.rename("theta_tps").to_csv(a.theta_csv)
    print("[+] θ:", theta, "->", a.theta_csv)


if __name__ == "__main__":
    main()
