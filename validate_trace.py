"""
Module kiểm tra tính hợp lệ toàn diện của tệp vết tải (Trace Validator)
dành cho hệ thống mô phỏng SageServe.

Kiểm tra:
1. Đầy đủ 15 cột bắt buộc theo chuẩn Trace.from_csv và Request.from_dict.
2. Không có giá trị rỗng (null/NaN).
3. arrival_timestamp không âm, đơn điệu tăng dần (đã sắp xếp).
4. prompt_size >= 1 và token_size >= 1.
5. client_tenant thuộc {0, 1, 2}.
6. regions là chuỗi 3 ký tự hoán vị hợp lệ của '0', '1', '2'.
7. workload_type thuộc {'prod', 'dev'}.
8. scenario thuộc {'IW-F', 'IW-N', 'NIW'}.
9. Thử nghiệm trực tiếp với Trace.from_csv(csv_path, siloed=False) và populate_requests().
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np

REQUIRED_COLUMNS = [
    "request_id",
    "batch_id",
    "client_tenant",
    "request_type",
    "scenario",
    "sla",
    "utility",
    "regions",
    "model_type",
    "workload_type",
    "application_id",
    "arrival_timestamp",
    "batch_size",
    "prompt_size",
    "token_size",
]

VALID_REGIONS = {"012", "021", "102", "120", "201", "210"}
VALID_WORKLOADS = {"prod", "dev"}
VALID_SCENARIOS = {"IW-F", "IW-N", "NIW"}

def validate_trace_file(csv_path: str, verbose: bool = True) -> bool:
    if not os.path.exists(csv_path):
        print(f"[-] ERROR: File {csv_path} does not exist!")
        return False

    print(f"[*] Validating trace file: {csv_path}")
    file_size_mb = os.path.getsize(csv_path) / (1024 * 1024)
    print(f"    File size: {file_size_mb:.2f} MB")

    try:
        df = pd.read_csv(csv_path, dtype={"regions": str})
    except Exception as e:
        print(f"[-] ERROR reading CSV: {e}")
        return False

    num_rows = len(df)
    print(f"    Total rows: {num_rows:,}")
    if num_rows == 0:
        print("[-] ERROR: Trace file is empty!")
        return False

    errors = []

    # 1. Check columns
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        errors.append(f"Missing required columns: {missing_cols}")

    # 2. Check nulls
    null_counts = df[REQUIRED_COLUMNS].isnull().sum()
    null_cols = null_counts[null_counts > 0]
    if not null_cols.empty:
        errors.append(f"Columns containing NaN/null values: {null_cols.to_dict()}")

    # 3. Check arrival_timestamp
    if "arrival_timestamp" in df.columns:
        timestamps = df["arrival_timestamp"].values
        if (timestamps < 0).any():
            errors.append("Negative arrival_timestamp detected!")
        diffs = np.diff(timestamps)
        if (diffs < 0).any():
            errors.append("arrival_timestamp is NOT monotonically non-decreasing (trace not sorted)!")

    # 4. Check prompt_size and token_size
    if "prompt_size" in df.columns and (df["prompt_size"] < 1).any():
        errors.append("prompt_size has values < 1!")
    if "token_size" in df.columns and (df["token_size"] < 1).any():
        errors.append("token_size has values < 1!")

    # 5. Check regions
    if "regions" in df.columns:
        invalid_regions = set(df["regions"].dropna()) - VALID_REGIONS
        if invalid_regions:
            errors.append(f"Invalid regions values detected: {invalid_regions}")

    # 6. Check client_tenant
    if "client_tenant" in df.columns:
        invalid_tenants = set(df["client_tenant"].dropna()) - {0, 1, 2}
        if invalid_tenants:
            errors.append(f"Invalid client_tenant values detected: {invalid_tenants}")

    # 7. Check workload_type
    if "workload_type" in df.columns:
        invalid_workloads = set(df["workload_type"].dropna()) - VALID_WORKLOADS
        if invalid_workloads:
            errors.append(f"Invalid workload_type values detected: {invalid_workloads}")

    # 8. Check scenario
    if "scenario" in df.columns:
        unique_scenarios = set(df["scenario"].dropna())
        invalid_scenarios = unique_scenarios - VALID_SCENARIOS
        if invalid_scenarios:
            # Non-fatal warning if custom scenario name used
            print(f"    [!] Warning: Non-standard scenario names: {invalid_scenarios}")

    if errors:
        print("[-] VALIDATION FAILED with the following errors:")
        for err in errors:
            print(f"    * {err}")
        return False

    print("[+] Data integrity checks PASSED!")

    # 9. Test end-to-end loading with SageServe Trace class
    print("[*] Testing end-to-end loading via Trace.from_csv()...")
    try:
        import simulator
        if simulator.sim is None:
            simulator.sim = type("DummySim", (), {"time": 0.0})()
        from trace import Trace
        t = Trace.from_csv(csv_path, siloed=False)
        first_batch = t.populate_requests()
        print(f"[+] Successfully loaded and unpacked first batch: {len(first_batch)} requests via Trace.from_csv!")
    except Exception as e:
        print(f"[-] ERROR in Trace.from_csv(): {e}")
        import traceback
        traceback.print_exc()
        return False

    if verbose:
        duration_sec = df["arrival_timestamp"].max() - df["arrival_timestamp"].min()
        print("\n=== TRACE METRICS & BREAKDOWN ===")
        print(f"  Duration: {duration_sec:.1f}s ({duration_sec / 3600:.2f} hours, {duration_sec / 86400:.2f} days)")
        print(f"  Request Rate: {num_rows / max(1, duration_sec):.2f} req/s ({num_rows / max(1, duration_sec) * 60:.1f} req/min)")
        print(f"  Models: {df['model_type'].value_counts().to_dict()}")
        print(f"  Workloads: {df['workload_type'].value_counts().to_dict()}")
        if "scenario" in df.columns:
            print(f"  Workload Classes: {df['scenario'].value_counts().to_dict()}")
        print(f"  Client Tenants: {df['client_tenant'].value_counts().to_dict()}")
        print(f"  Prompt tokens (Mean/Median/P90): {df['prompt_size'].mean():.1f} / {df['prompt_size'].median():.1f} / {df['prompt_size'].quantile(0.9):.1f}")
        print(f"  Generated tokens (Mean/Median/P90): {df['token_size'].mean():.1f} / {df['token_size'].median():.1f} / {df['token_size'].quantile(0.9):.1f}")
        print("=================================\n")

    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate SageServe Trace CSV file")
    parser.add_argument("csv_path", type=str, help="Path to CSV trace file to validate")
    args = parser.parse_args()

    success = validate_trace_file(args.csv_path)
    sys.exit(0 if success else 1)
