"""
T29 / §2.1: θ = input TPS mỗi instance đạt được ở latency mục tiêu. Mục tiêu là TTFT P95 của Unified trong Table 1.
Mỗi mức tải: 1 vùng, số instance cố định, không co giãn, request IW lấy mẫu từ trace (giữ nguyên tỉ lệ IW-F/IW-N cả ngày).
Request chưa có TTFT khi bài kết thúc tính là vượt mục tiêu. θ nội suy tại điểm P95 cắt mục tiêu giữa hai mức liền kề.

Dùng: python benchmark_theta.py traces/composed_day_3regions.csv us1-4models data/theta_tps.csv --out results/theta_bench/a100

D42 (phương án a, b; mặc định giữ cách cũ): --instances 1 --target iwn60 đo θ(a) = TPS lớn nhất mà TTFT P95 của IW-N ≤ 60 s
(§2.2) và θ(b) = mức lớn nhất mà hàng đợi không tăng ở nửa sau cửa sổ đến (độ dốc ≤ 0 hoặc tăng ≤ 5%) VÀ ≥ 99% request
trong cửa sổ xong trước khi hết thời gian xả. Kết quả ghi theta_d42.json cạnh curve.csv; θ không xác định thì ghi null.
--levels L1 L2 ...: chỉ chạy đúng các mức này (đo thử), không tinh chỉnh, không ghi θ.
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
TARGET_IWN = 60.0            # D42 (a): SLA IW-N §2.2 "< 1 min … at the 95th percentile"


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
    g = pd.concat(pd.read_csv(f, usecols=["request_id", "ttft", "completion_time"]) for f in glob.glob(f"{out}/global_router/*.csv"))
    win = df[df.arrival_timestamp.between(WARMUP, ARRIVE)]
    ttft = g[g.request_id.isin(win.request_id)].ttft.values - ROUTING_DELAY
    win_n = win[win.scenario == "IW-N"]
    ttft_n = g[g.request_id.isin(win_n.request_id)].ttft.values - ROUTING_DELAY
    return {"model": model, "level_tps": level, "requests": len(win), "finished": len(ttft),
            "ttft_p95": p95_with_unfinished(win, ttft), "requests_iwn": len(win_n), "ttft_p95_iwn": p95_with_unfinished(win_n, ttft_n),
            **saturation(df, g, len(ttft) / max(len(win), 1))}


def in_system(df, g, t):
    """Số request đã đến mà chưa xong tại các thời điểm t (request chưa xong khi hết bài tính là còn trong hệ thống)."""
    arr, done = np.sort(df.arrival_timestamp.values), np.sort(g.completion_time.values)
    return np.searchsorted(arr, t, side="right") - np.searchsorted(done, t, side="right")


def saturation(df, g, finished_frac):
    """D42 (b): nửa sau cửa sổ đến, số request trong hệ thống không tăng (độ dốc ≤ 0 hoặc cuối ≤ 1,05 × đầu) VÀ ≥ 99% xong."""
    t = np.arange((WARMUP + ARRIVE) / 2, ARRIVE + 1e-9, 60.0)
    n = in_system(df, g, t)
    slope = float(np.polyfit(t, n, 1)[0])
    ok = (slope <= 0 or n[-1] <= 1.05 * n[0]) and finished_frac >= 0.99
    return {"q_start": int(n[0]), "q_end": int(n[-1]), "q_slope_per_s": slope, "finished_frac": finished_frac, "sat_ok": bool(ok)}


def theta_b(x):
    """D42 (b): mức lớn nhất còn sat_ok trước mức trượt đầu tiên (thang tăng dần); None nếu mức thấp nhất đã trượt."""
    best = None
    for l, ok in zip(x.level_tps.values, x.sat_ok.values):
        if not ok:
            break
        best = float(l)
    return best


def main():
    global INSTANCES
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("controller")
    ap.add_argument("theta_csv")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--models", nargs="*", default=list(TARGET_P95))
    ap.add_argument("--hour", type=int, help="Chỉ lấy mẫu request của giờ này (đo năng lực ở tỉ lệ IW-F/IW-N của giờ đó)")
    ap.add_argument("--instances", type=int, default=INSTANCES, help="D42: số instance cố định (bài báo §2.1: 1 instance)")
    ap.add_argument("--target", choices=["table1", "iwn60"], default="table1", help="D42 (a): iwn60 = TTFT P95 của IW-N ≤ 60 s")
    ap.add_argument("--levels", type=float, nargs="*", help="D42: chỉ chạy các mức này (đo thử), không ghi θ")
    a = ap.parse_args()
    a.out = a.out.rstrip("/")
    INSTANCES = a.instances
    target = TARGET_P95 if a.target == "table1" else {m: TARGET_IWN for m in TARGET_P95}
    col = "ttft_p95" if a.target == "table1" else "ttft_p95_iwn"
    t = pd.read_csv(a.trace, dtype={"regions": str})
    t = t[t.workload_type == "prod"]
    if a.hour is not None:
        t = t[t.arrival_timestamp // 3600 == a.hour]
    os.makedirs(a.out, exist_ok=True)
    rows = []
    if a.levels:
        with cf.ThreadPoolExecutor(a.workers) as ex:
            res = [r for m in a.models for r in ex.map(lambda l: run_level(m, l, t[t.model_type == m], a), a.levels)]
        pd.DataFrame(res).to_csv(f"{a.out}/thu.csv", index=False)
        print(pd.DataFrame(res).to_string(), flush=True)
        return
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
                # D42: với iwn60 đi tiếp tới khi cả (a) vượt 60 s và (b) có mức trượt, để θ(b) không bị cắt sớm
                if any(r[col] > target[model] for r in res) and (a.target == "table1" or not all(r["sat_ok"] for r in res)):
                    break
            rows += done
        # khuỷu rất dốc -> tinh chỉnh: thêm các mức giữa hai mức bao quanh điểm cắt
        for model in a.models:
            x = pd.DataFrame(rows).query("model == @model").sort_values("level_tps")
            over = x[col].values > target[model]
            if not over.any() or over[0]:
                continue
            k = over.argmax()
            levels = np.linspace(x.level_tps.values[k - 1], x.level_tps.values[k], REFINE + 2)[1:-1]
            rows += list(ex.map(lambda l: run_level(model, l, t[t.model_type == model], a), levels))
    res = pd.DataFrame(rows).sort_values(["model", "level_tps"])
    res.to_csv(f"{a.out}/curve.csv", index=False)
    if a.target == "iwn60":         # D42: không ghi đè file θ; θ không xác định thì null
        import json
        out = {m: {"theta_a": crossing(x.level_tps.values, x.ttft_p95_iwn.values, TARGET_IWN), "theta_b": theta_b(x),
                   "muc_cao_nhat": float(x.level_tps.max())}     # θ bằng mức cao nhất nghĩa là "≥ mức đó" (trần thang)
               for m, x in res.groupby("model")}
        json.dump(out, open(f"{a.out}/theta_d42.json", "w"), indent=1)
        print("[+] θ D42:", out, flush=True)
        return
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
