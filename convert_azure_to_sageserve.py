import argparse
import os
import random
import numpy as np
import pandas as pd

def process_file(csv_path, model_name, max_seconds=10800):
    print(f"Reading {csv_path} for model {model_name}...")
    df = pd.read_csv(csv_path)
    df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"], format="mixed")
    t_start = df["TIMESTAMP"].iloc[0]
    df["arrival_timestamp"] = (df["TIMESTAMP"] - t_start).dt.total_seconds().astype(int)
    
    # Filter 3 hours
    df = df[(df["arrival_timestamp"] >= 0) & (df["arrival_timestamp"] <= max_seconds)].copy()
    print(f"  Rows in first {max_seconds}s: {len(df)}")
    
    df["model_type"] = model_name
    df["prompt_size"] = df["ContextTokens"].clip(lower=1, upper=8192).astype(int)
    df["token_size"] = df["GeneratedTokens"].clip(lower=1, upper=8192).astype(int)
    return df[["arrival_timestamp", "model_type", "prompt_size", "token_size"]]

def main():
    parser = argparse.ArgumentParser(description="Convert Azure LLM trace to SageServe format")
    parser.add_argument("--code_csv", type=str, default="traces/raw_azure/AzureLLMInferenceTrace_code_3h.csv")
    parser.add_argument("--conv_csv", type=str, default="traces/raw_azure/AzureLLMInferenceTrace_conv_3h.csv")
    parser.add_argument("--output_csv", type=str, default="traces/azure_trace_3h.csv")
    parser.add_argument("--duration_hours", type=int, default=3)
    parser.add_argument("--sample_ratio", type=float, default=0.35, help="Subsample ratio to match cluster capacity")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    max_seconds = args.duration_hours * 3600

    df_code = process_file(args.code_csv, "bloom-176b", max_seconds)
    df_conv = process_file(args.conv_csv, "llama2-70b", max_seconds)

    # Combine both datasets
    df = pd.concat([df_code, df_conv], ignore_index=True)
    df = df.sort_values(by="arrival_timestamp").reset_index(drop=True)
    print(f"Combined total requests before sampling: {len(df)}")

    if args.sample_ratio < 1.0:
        df = df.sample(frac=args.sample_ratio, random_state=args.seed).sort_values(by="arrival_timestamp").reset_index(drop=True)
        print(f"Sampled to {len(df)} requests (ratio={args.sample_ratio})")

    num_requests = len(df)
    region_permutations = ["012", "021", "102", "120", "201", "210"]

    records = []
    for req_id in range(num_requests):
        row = df.iloc[req_id]
        arrival_t = int(row["arrival_timestamp"])
        m_type = str(row["model_type"])
        p_size = int(row["prompt_size"])
        t_size = int(row["token_size"])

        # Multi-region assignment
        reg_str = random.choice(region_permutations)
        primary_reg = int(reg_str[0])

        # 70% prod (interactive), 30% dev (non-interactive)
        is_prod = (random.random() < 0.70)
        w_type = "prod" if is_prod else "dev"
        sla = 10 if is_prod else -1
        utility = 3 if is_prod else 0

        records.append({
            "request_id": req_id,
            "batch_id": -1,
            "client_tenant": primary_reg,
            "request_type": 2,
            "scenario": "EnterpriseSydney",
            "sla": sla,
            "utility": utility,
            "regions": reg_str,
            "model_type": m_type,
            "workload_type": w_type,
            "application_id": 0,
            "arrival_timestamp": arrival_t,
            "batch_size": 1,
            "prompt_size": p_size,
            "token_size": t_size,
        })

    df_out = pd.DataFrame(records)
    os.makedirs(os.path.dirname(args.output_csv), exist_ok=True)
    df_out.to_csv(args.output_csv, index=False)
    print(f"Successfully generated {args.output_csv}:")
    print(f"  Requests: {len(df_out)}")
    print(f"  Time span: {df_out['arrival_timestamp'].min()}s - {df_out['arrival_timestamp'].max()}s ({(df_out['arrival_timestamp'].max()+1)/3600:.2f} hours)")
    print(f"  Models: {df_out['model_type'].value_counts().to_dict()}")
    print(f"  Workload: {df_out['workload_type'].value_counts().to_dict()}")

if __name__ == "__main__":
    main()
