"""
Pipeline Tiền Xử Lý Vết Tải (Trace Preprocessing Pipeline) cho SageServe.

Hỗ trợ:
- 3 phân lớp tải công việc (Workload Classes):
  + IW-F (Interactive Workload - Fast): SLA=1s, Utility=5.0 (50%)
  + IW-N (Interactive Workload - Normal): SLA=10s, Utility=3.0 (20%)
  + NIW (Non-Interactive Workload): SLA=86400s (hoặc -1), Utility=1.0 (30%)
- 3 Vùng (Regions): 0 (westus), 1 (centralus), 2 (eastus).
- 4 Mô hình (Models):
  + Canonical: llama2-70b, bloom-176b, llama3.1-8b, llama3.2-3b
  + Symbolic: A, B, C, D
- Chuẩn hóa định dạng tương thích 100% với Trace.from_csv và Request.from_dict.
- Hỗ trợ tạo tập dev nhỏ (1–2 ngày) với hệ số subsample tùy biến.
"""

import os
import sys
import argparse
import random
import numpy as np
import pandas as pd
from validate_trace import validate_trace_file

CANONICAL_MODELS = ["llama2-70b", "bloom-176b", "llama3.1-8b", "llama3.2-3b"]
SYMBOLIC_MODELS = ["A", "B", "C", "D"]
MODEL_WEIGHTS = [0.35, 0.25, 0.25, 0.15]  # A: 35%, B: 25%, C: 25%, D: 15%

# Phân bổ tỷ lệ các lớp tải: IW-F (50%), IW-N (20%), NIW (30%)
WORKLOAD_CLASSES = ["IW-F", "IW-N", "NIW"]
WORKLOAD_PROBABILITIES = [0.50, 0.20, 0.30]

def get_regions_for_tenant(client_tenant: int) -> str:
    """
    Sinh thứ tự ưu tiên 3 vùng (regions) dựa trên vùng xuất phát của client,
    khớp theo thuật toán trong notebooks/traces.ipynb của tác giả SageServe.
    """
    if client_tenant == 0:
        return "012" if random.random() < 0.5 else "021"
    elif client_tenant == 1:
        return "120" if random.random() < 0.5 else "102"
    elif client_tenant == 2:
        return "201" if random.random() < 0.5 else "210"
    return "012"

def load_and_normalize_raw_azure(code_csv: str, conv_csv: str, max_seconds: int):
    """
    Đọc dữ liệu thô từ Azure LLM Inference Traces và chuyển đổi TIMESTAMP sang giây.
    """
    print(f"[*] Reading Code trace: {code_csv}...")
    df_code = pd.read_csv(code_csv)
    df_code["TIMESTAMP"] = pd.to_datetime(df_code["TIMESTAMP"], format="mixed")

    print(f"[*] Reading Conversation trace: {conv_csv}...")
    df_conv = pd.read_csv(conv_csv)
    df_conv["TIMESTAMP"] = pd.to_datetime(df_conv["TIMESTAMP"], format="mixed")

    # Tính mốc thời gian bắt đầu chung
    t_start = min(df_code["TIMESTAMP"].iloc[0], df_conv["TIMESTAMP"].iloc[0])

    df_code["arrival_timestamp"] = (df_code["TIMESTAMP"] - t_start).dt.total_seconds().astype(int)
    df_conv["arrival_timestamp"] = (df_conv["TIMESTAMP"] - t_start).dt.total_seconds().astype(int)

    # Lọc theo khoảng thời gian yêu cầu
    df_code = df_code[(df_code["arrival_timestamp"] >= 0) & (df_code["arrival_timestamp"] <= max_seconds)].copy()
    df_conv = df_conv[(df_conv["arrival_timestamp"] >= 0) & (df_conv["arrival_timestamp"] <= max_seconds)].copy()

    df_code["prompt_size"] = df_code["ContextTokens"].clip(lower=1, upper=8192).astype(int)
    df_code["token_size"] = df_code["GeneratedTokens"].clip(lower=1, upper=4096).astype(int)

    df_conv["prompt_size"] = df_conv["ContextTokens"].clip(lower=1, upper=8192).astype(int)
    df_conv["token_size"] = df_conv["GeneratedTokens"].clip(lower=1, upper=4096).astype(int)

    # Gộp 2 luồng
    combined_df = pd.concat([
        df_code[["arrival_timestamp", "prompt_size", "token_size"]],
        df_conv[["arrival_timestamp", "prompt_size", "token_size"]]
    ], ignore_index=True)

    combined_df = combined_df.sort_values(by="arrival_timestamp").reset_index(drop=True)

    # Nếu thời gian yêu cầu lớn hơn khoảng thời gian thô hiện có, mở rộng chu kỳ
    current_span = combined_df["arrival_timestamp"].max() if len(combined_df) > 0 else 0
    if max_seconds > current_span and current_span > 0:
        cycles_needed = int(np.ceil((max_seconds - current_span) / current_span))
        print(f"[*] Extending trace to cover full {max_seconds/3600:.1f}h (current span: {current_span/3600:.1f}h, {cycles_needed} cycles)...")
        dfs_to_concat = [combined_df]
        for c in range(1, cycles_needed + 1):
            cycle_df = combined_df.copy()
            cycle_df["arrival_timestamp"] += c * (current_span + 1)
            dfs_to_concat.append(cycle_df)
        combined_df = pd.concat(dfs_to_concat, ignore_index=True)
        combined_df = combined_df[combined_df["arrival_timestamp"] <= max_seconds].copy()
        combined_df = combined_df.sort_values(by="arrival_timestamp").reset_index(drop=True)

    print(f"[+] Total raw requests in range 0..{max_seconds}s ({max_seconds/3600:.1f}h): {len(combined_df):,}")
    return combined_df

def preprocess_trace_pipeline(
    code_csv: str,
    conv_csv: str,
    output_csv: str,
    duration_hours: float = 24.0,
    sample_ratio: float = 0.05,
    target_requests: int = None,
    naming: str = "canonical",
    seed: int = 42,
    validate: bool = True
) -> str:
    """
    Thực thi toàn bộ pipeline tiền xử lý và sinh tệp CSV chuẩn.
    """
    random.seed(seed)
    np.random.seed(seed)

    max_seconds = int(duration_hours * 3600)
    print(f"\n==================================================")
    print(f"[*] START TRACE PREPROCESSING PIPELINE")
    print(f"    Target Duration: {duration_hours} hours ({duration_hours/24:.2f} days)")
    print(f"    Model Naming: {naming}")
    print(f"    Output Path: {output_csv}")
    print(f"==================================================")

    df_raw = load_and_normalize_raw_azure(code_csv, conv_csv, max_seconds)

    # Subsampling
    if target_requests is not None and target_requests < len(df_raw):
        df = df_raw.sample(n=target_requests, random_state=seed).sort_values(by="arrival_timestamp").reset_index(drop=True)
        print(f"[*] Subsampled to exact target: {len(df):,} requests")
    elif sample_ratio < 1.0:
        df = df_raw.sample(frac=sample_ratio, random_state=seed).sort_values(by="arrival_timestamp").reset_index(drop=True)
        print(f"[*] Subsampled with ratio {sample_ratio}: {len(df):,} requests")
    else:
        df = df_raw

    num_requests = len(df)
    models_list = CANONICAL_MODELS if naming == "canonical" else SYMBOLIC_MODELS

    # Phân bổ ngẫu nhiên có trọng số cho 4 mô hình và 3 lớp tải
    assigned_models = np.random.choice(models_list, size=num_requests, p=MODEL_WEIGHTS)
    assigned_classes = np.random.choice(WORKLOAD_CLASSES, size=num_requests, p=WORKLOAD_PROBABILITIES)
    assigned_tenants = np.random.choice([0, 1, 2], size=num_requests)

    records = []
    for req_id in range(num_requests):
        row = df.iloc[req_id]
        arrival_t = int(row["arrival_timestamp"])
        p_size = int(row["prompt_size"])
        t_size = int(row["token_size"])
        model_name = assigned_models[req_id]
        w_class = assigned_classes[req_id]
        tenant = int(assigned_tenants[req_id])
        regions_str = get_regions_for_tenant(tenant)

        # Thiết lập SLA, Utility, workload_type theo 3 lớp tải
        if w_class == "IW-F":
            # Interactive Workload - Fast
            workload_type = "prod"
            sla = 1      # TTFT SLA < 1s
            utility = 5.0
            batch_id = -1
        elif w_class == "IW-N":
            # Interactive Workload - Normal
            workload_type = "prod"
            sla = 10     # Relaxed TTFT SLA
            utility = 3.0
            batch_id = -1
        else: # NIW
            # Non-Interactive Workload (Batch / Dev)
            workload_type = "dev"
            sla = 86400  # Soft deadline (24h)
            utility = 1.0
            batch_id = -1

        records.append({
            "request_id": req_id,
            "batch_id": batch_id,
            "client_tenant": tenant,
            "request_type": 2, # GENERATIVE_LLM
            "scenario": w_class,
            "sla": sla,
            "utility": utility,
            "regions": regions_str,
            "model_type": model_name,
            "workload_type": workload_type,
            "application_id": 0,
            "arrival_timestamp": arrival_t,
            "batch_size": 1,
            "prompt_size": p_size,
            "token_size": t_size,
        })

    df_out = pd.DataFrame(records)
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df_out.to_csv(output_csv, index=False)
    print(f"[+] Output written to: {output_csv} ({os.path.getsize(output_csv)/(1024*1024):.2f} MB)")

    if validate:
        print("\n[*] Running Validation Suite on generated trace...")
        is_valid = validate_trace_file(output_csv, verbose=True)
        if not is_valid:
            raise RuntimeError(f"Validation FAILED for {output_csv}")

    return output_csv

def main():
    parser = argparse.ArgumentParser(description="Preprocess Azure traces for SageServe (IW-F, IW-N, NIW, 3 regions, 4 models)")
    parser.add_argument("--code_csv", type=str, default="traces/raw_azure/AzureLLMInferenceTrace_code_1d.csv")
    parser.add_argument("--conv_csv", type=str, default="traces/raw_azure/AzureLLMInferenceTrace_conv_1d.csv")
    parser.add_argument("--output_csv", type=str, default="traces/azure_trace_dev_1day.csv")
    parser.add_argument("--duration_hours", type=float, default=24.0, help="Duration in hours (e.g. 24 for 1 day, 48 for 2 days)")
    parser.add_argument("--sample_ratio", type=float, default=0.03, help="Subsample ratio to produce a compact dev trace")
    parser.add_argument("--target_requests", type=int, default=None, help="Target exact request count (overrides sample_ratio)")
    parser.add_argument("--naming", type=str, choices=["canonical", "symbolic"], default="canonical", help="Model naming scheme")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no_validate", action="store_true", help="Skip validation")
    args = parser.parse_args()

    preprocess_trace_pipeline(
        code_csv=args.code_csv,
        conv_csv=args.conv_csv,
        output_csv=args.output_csv,
        duration_hours=args.duration_hours,
        sample_ratio=args.sample_ratio,
        target_requests=args.target_requests,
        naming=args.naming,
        seed=args.seed,
        validate=not args.no_validate
    )

if __name__ == "__main__":
    main()
