"""
Trace thứ hai (kiểm chứng chéo): bộ sinh trace tổng hợp của fork SreenathKarthick11/Sage-Serve (PR #13,
mlops/trace_sim/workload.py, commit 14325f4), tham số ước lượng từ Fig. 3-6, 10 của bài báo.

Sửa 4 lỗi trước khi đưa vào simulator:
  1. NIW gắn workload_type=prod -> 'dev' theo SLA (86400 s); batch_id = -1 để NIW đi qua Queue Manager.
  2. scenario luôn 'EnterpriseSydney' -> IW-F / IW-N / NIW theo SLA.
  3. client_tenant 0-49 -> mã vùng 0 west, 1 central, 2 east.
  4. prompt tới 32000 token -> cắt ở 8192 (giới hạn bảng hiệu năng); output <= 4096.
Mô hình A, B, C, D -> bloom-176b, llama2-70b, llama3.1-8b, llama3.2-3b (A lớn nhất, như bài báo).

Mã gốc (MIT) được chép nguyên trong third_party/fork_trace_sim/.
Dùng: python fork_trace.py --rate_scale 0.109 --start_day 1 --days 1 --regions 0 --output_csv traces/fork_s4_westus.csv
"""
import argparse
import importlib.util

import numpy as np
import pandas as pd

from preprocess_servegen import MAX_PROMPT, MAX_TOKENS
from validate_trace import validate_trace_file

TIER_BY_SLA = {1: "IW-F", 60: "IW-N", 86400: "NIW"}
REGION_ID = {"west": 0, "central": 1, "east": 2}
MODEL_MAP = {"A": "bloom-176b", "B": "llama2-70b", "C": "llama3.1-8b", "D": "llama3.2-3b"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workload_py", default="third_party/fork_trace_sim/workload.py")
    ap.add_argument("--rate_scale", type=float, default=0.002)
    ap.add_argument("--start_day", type=int, default=0)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--regions", type=int, nargs="+", default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--output_csv", default="traces/fork_week.csv")
    a = ap.parse_args()

    spec = importlib.util.spec_from_file_location("fork_workload", a.workload_py)
    wl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wl)
    w = wl.Workload(rate_scale=a.rate_scale, seed=a.seed)

    keep = set(a.regions) if a.regions is not None else {0, 1, 2}
    chunks, start, end = [], a.start_day * 86400, (a.start_day + a.days) * 86400
    for t0 in range(start, end, 60):
        rows = [r for region, _, r in w.requests_between(t0, t0 + 60) if REGION_ID[region] in keep]
        if rows:
            chunks.append(pd.DataFrame(rows))
    df = pd.concat(chunks, ignore_index=True)

    df["scenario"] = df.sla.map(TIER_BY_SLA)                                   # lỗi 2
    df["workload_type"] = np.where(df.scenario == "NIW", "dev", "prod")         # lỗi 1
    df["batch_id"], df["batch_size"] = -1, 1
    df["client_tenant"] = df.regions.str[0].astype(int)                         # lỗi 3 (vùng nhận request)
    df["prompt_size"] = df.prompt_size.clip(1, MAX_PROMPT)                      # lỗi 4
    df["token_size"] = df.token_size.clip(1, MAX_TOKENS)
    df["model_type"] = df.model_type.map(MODEL_MAP)
    df["arrival_timestamp"] = (df.arrival_timestamp - start).round(3)
    df = df.sort_values("arrival_timestamp", kind="stable").reset_index(drop=True)
    df["request_id"] = df.index
    df[wl.COLUMNS].to_csv(a.output_csv, index=False)
    print(f"[+] {a.output_csv}: {len(df):,} request ({(df.workload_type == 'prod').sum():,} IW + "
          f"{(df.workload_type == 'dev').sum():,} NIW)")
    if not validate_trace_file(a.output_csv, verbose=True):
        raise RuntimeError("Validation FAILED")


if __name__ == "__main__":
    main()
