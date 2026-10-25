"""
Ghép trace chính từ các nguồn mở để đáp ứng các yêu cầu của bài báo SageServe.

- IW: Azure LLM Inference 2024 (1 tuần, thời điểm đến + số token thật).
      code -> IW-F (TTFT < 1 s), conversation -> IW-N (TTFT < 1 phút)  [§2.2: code generation thuộc nhóm "fast"]
- Mô hình: Azure không có nhãn -> chia theo tỉ trọng lưu lượng thật từng giờ của 4 luồng ServeGen.
      Gán theo thứ hạng lưu lượng: luồng đông nhất -> bloom-176b (mô hình A của bài báo: lớn nhất, đông nhất).
- Vùng: không nguồn mở nào có -> ma trận nhu cầu theo (tầng, mô hình) từ §3/Fig. 4 (T7/2025): East > Central > West,
      mô hình A East ≈ 4-6x West (IW-F), mô hình B cao nhất ở Central (IW-F) và West (IW-N), NIW ở West rất ít.
      Đỉnh RPS từng ô lấy theo bảng ước lượng Fig. 4 của third_party/fork_trace_sim/workload.py (PEAK_RPS).
      §4 chỉ có 1 vùng: dùng --single_region (mọi request về westus).
- NIW: batch job offline thật của ServeGen, rải đều suốt ngày, chia đều 4 mô hình, IW:NIW = 3:1 (Phụ lục A).
- Giới hạn token theo bảng hiệu năng: prompt <= 8192, output <= 4096.

Dùng:
  python compose_trace.py --output_csv traces/composed_week.csv
  python compose_trace.py --days 1 --start_day 4 --single_region --niw_ratio 7 --sample_frac <...> \
      --output_csv traces/composed_s4_westus.csv                                    # §4: West, thứ Ba 14/5
"""
import argparse
import os

import numpy as np
import pandas as pd

from preprocess_servegen import (MAX_PROMPT, MAX_TOKENS, MODELS, REGION_ORDERS, generate_niw, load_rates_grid,
                                 read_rates)
from validate_trace import validate_trace_file

AZURE = "traces/raw_azure_week/AzureLLMInferenceTrace_{}_1week.csv"
TIERS = {"code": ("IW-F", 1, 5.0), "conv": ("IW-N", 60, 3.0)}          # scenario, sla (s), utility
SIM_MODELS_BY_RANK = ["bloom-176b", "llama2-70b", "llama3.1-8b", "llama3.2-3b"]   # = mô hình A, B, C, D
# Đỉnh RPS theo vùng (west, central, east) cho mô hình A..D, ước lượng từ Fig. 4 -> chỉ dùng làm tỉ lệ chia vùng.
PEAK_RPS = {
    "IW-F": {"west": [70, 40, 10, 5], "central": [70, 190, 20, 10], "east": [400, 60, 20, 10]},
    "IW-N": {"west": [49, 70, 21, 7], "central": [35, 14, 10, 4], "east": [140, 63, 28, 7]},
    "NIW": {"west": [1.6, 2.4, 4, 0.8], "central": [8, 12, 32, 4], "east": [24, 32, 80, 8]},
}


def region_probs(tier, model):
    """Xác suất (west, central, east) của một request theo tầng và mô hình."""
    i = SIM_MODELS_BY_RANK.index(model)
    p = np.array([PEAK_RPS[tier][r][i] for r in ("west", "central", "east")], dtype=float)
    return p / p.sum()
COLS = ["request_id", "batch_id", "client_tenant", "request_type", "scenario", "sla", "utility", "regions",
        "model_type", "workload_type", "application_id", "arrival_timestamp", "batch_size", "prompt_size",
        "token_size"]


def model_shares(raw, hours):
    """Tỉ trọng lưu lượng thật theo giờ (hours x 4) của 4 luồng ServeGen, sắp theo thứ hạng tổng lưu lượng."""
    g = load_rates_grid()                                              # 3 mô hình ngôn ngữ, 14 ngày, lỗ hổng đã nội suy
    hourly = g.assign(h=g.ts // 3600).groupby(["model", "h"]).rps.sum().unstack(0) / 6   # rps trung bình giờ
    r1 = read_rates(raw, "r1").groupby("ts").rate.sum()                # deepseek-r1: chỉ có ngày 0
    r1_hour = r1.groupby(r1.index // 3600).sum().div(6).reindex(range(24), fill_value=0)
    hourly["r1"] = np.tile(r1_hour.values, int(np.ceil(len(hourly) / 24)))[:len(hourly)]
    hourly = hourly.iloc[:hours]
    order = hourly.sum().sort_values(ascending=False).index
    print("[*] Thứ hạng lưu lượng ServeGen ->", dict(zip(order, SIM_MODELS_BY_RANK)))
    shares = hourly[order].div(hourly[order].sum(axis=1), axis=0).values
    return shares


AZURE_DAY0 = pd.Timestamp("2024-05-10", tz="UTC")                     # ngày đầu của trace Azure (thứ Sáu)


def load_iw(start_s, end_s, rng, sample_frac=1.0):
    """Đọc từng phần (file ~1,8 GB), chỉ giữ [start_s, end_s) tính từ 00:00 10/5/2024; có thể lấy mẫu.
    sample_frac > 1 (cần để qua cổng G10): lấy toàn bộ cửa sổ + phần lẻ (sample_frac - 1) của các ngày KẾ TIẾP
    cùng độ dài, dời về cùng khung giờ – vẫn là request thật, giữ hình dạng theo giờ."""
    parts = []
    span = end_s - start_s
    for key, (scenario, sla, utility) in TIERS.items():
        for d in pd.read_csv(AZURE.format(key), usecols=["TIMESTAMP", "ContextTokens", "GeneratedTokens"],
                             chunksize=5_000_000):
            d["arrival_timestamp"] = (pd.to_datetime(d.pop("TIMESTAMP"), format="mixed") - AZURE_DAY0).dt.total_seconds()
            for k in range(int(np.ceil(sample_frac))):          # k = 0: cửa sổ gốc; k ≥ 1: ngày kế tiếp
                frac = min(1.0, sample_frac - k)
                w = d[(d.arrival_timestamp >= start_s + k * span) & (d.arrival_timestamp < end_s + k * span)].copy()
                w["arrival_timestamp"] -= k * span
                if frac < 1:
                    w = w[rng.random(len(w)) < frac]
                parts.append(w.assign(scenario=scenario, sla=sla, utility=utility))
    iw = pd.concat(parts, ignore_index=True)
    iw["arrival_timestamp"] -= start_s
    print(f"[*] Azure ngày {start_s // 86400}..{end_s // 86400 - 1} (ngày 0 = thứ Sáu 10/5/2024): {len(iw):,} request IW")
    return iw.rename(columns={"ContextTokens": "prompt_size", "GeneratedTokens": "token_size"})


def build(output_csv, start_day, days, regions, niw_ratio, seed, raw="traces/raw_servegen", sample_frac=1.0,
          single_region=False, output_scale=1.0):
    rng = np.random.default_rng(seed)
    start_s, end_s = start_day * 86400, (start_day + days) * 86400
    iw = load_iw(start_s, end_s, rng, sample_frac)
    shares = model_shares(raw, (start_day + days) * 24)[start_day * 24:]
    hour = (iw.arrival_timestamp // 3600).astype(int).clip(upper=len(shares) - 1).values
    cdf = shares.cumsum(axis=1)[hour]
    idx = (rng.random(len(iw))[:, None] > cdf).sum(axis=1).clip(max=3)
    iw["model_type"] = np.array(SIM_MODELS_BY_RANK)[idx]
    iw["workload_type"] = "prod"

    niw = generate_niw(raw, list(MODELS), days, int(len(iw) / niw_ratio), rng, spread=True)
    niw["model_type"] = niw.model_type.map(dict(zip([MODELS[m][1] for m in MODELS], SIM_MODELS_BY_RANK)))
    df = pd.concat([iw, niw[iw.columns.intersection(niw.columns)]], ignore_index=True)
    df["client_tenant"] = 0
    if not single_region:
        for (tier, model), idx in df.groupby(["scenario", "model_type"]).groups.items():
            df.loc[idx, "client_tenant"] = rng.choice(3, size=len(idx), p=region_probs(tier, model))
    if regions is not None:
        df = df[df.client_tenant.isin(regions)]
    df = df.sort_values("arrival_timestamp", kind="stable").reset_index(drop=True)
    df["prompt_size"] = df.prompt_size.clip(1, MAX_PROMPT).astype(int)
    # Output Azure 2024 rất ngắn (trung vị ~25 token) nên request gần như không giữ bộ nhớ KV và simulator không phải
    # co giãn. --output_scale nhân output của IW (vẫn đúng §3/Fig. 10: phần lớn output < 1k), hiệu chỉnh bằng cổng G10.
    iw_rows = df.workload_type == "prod"
    df.loc[iw_rows, "token_size"] = df.loc[iw_rows, "token_size"] * output_scale
    df["token_size"] = df.token_size.clip(1, MAX_TOKENS).astype(int)
    df["arrival_timestamp"] = df.arrival_timestamp.round(3)
    df["regions"] = [REGION_ORDERS[c][i] for c, i in zip(df.client_tenant, rng.integers(0, 2, len(df)))]
    df["request_id"] = df.index
    df["batch_id"], df["request_type"], df["application_id"], df["batch_size"] = -1, 2, 0, 1
    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
    df[COLS].to_csv(output_csv, index=False)
    print(f"[+] {output_csv}: {len(df):,} request ({(df.workload_type == 'prod').sum():,} IW + "
          f"{(df.workload_type == 'dev').sum():,} NIW)")
    return df


def main():
    ap = argparse.ArgumentParser(description="Ghép trace Azure 2024 + ServeGen theo yêu cầu bài báo")
    ap.add_argument("--output_csv", default="traces/composed_week.csv")
    ap.add_argument("--start_day", type=int, default=0)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--regions", type=int, nargs="+", default=None, help="Chỉ giữ các vùng này (0 west, 1 central, 2 east)")
    ap.add_argument("--niw_ratio", type=float, default=3.0, help="Tỉ lệ IW:NIW (Phụ lục A: 3:1)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sample_frac", type=float, default=1.0, help="Lấy mẫu một phần IW (để kiểm tra đặc trưng)")
    ap.add_argument("--single_region", action="store_true", help="Mọi request về westus (thí nghiệm §4)")
    ap.add_argument("--output_scale", type=float, default=1.0, help="Nhân độ dài output của IW (hiệu chỉnh bằng G10)")
    ap.add_argument("--no_validate", action="store_true")
    a = ap.parse_args()
    build(a.output_csv, a.start_day, a.days, a.regions, a.niw_ratio, a.seed, sample_frac=a.sample_frac,
          single_region=a.single_region, output_scale=a.output_scale)
    if not a.no_validate and not validate_trace_file(a.output_csv, verbose=True):
        raise RuntimeError("Validation FAILED")


if __name__ == "__main__":
    main()
