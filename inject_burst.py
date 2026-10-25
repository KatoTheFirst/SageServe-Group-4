"""
F11 (§7.2.7): chèn burst bất ngờ vào trace – "randomly increasing the incoming load to 8x".
Bài báo không nói thời lượng/thời điểm -> mặc định: 3 cửa sổ 10 phút mỗi ngày, chọn ngẫu nhiên (không chồng nhau),
IW trong cửa sổ được nhân lên --mult lần (bản sao rải đều ngẫu nhiên trong cửa sổ). NIW giữ nguyên.
Sau khi chèn: sinh lại dự báo bằng generate_causal_arima_forecasts.py (ARIMA chỉ dùng quá khứ nên vẫn "bất ngờ").

Dùng: python inject_burst.py traces/composed_day_3regions.csv traces/composed_day_3regions_burst8.csv
"""
import argparse

import numpy as np
import pandas as pd


def inject(df, mult, window, per_day, rng):
    days = int(np.ceil(df.arrival_timestamp.max() / 86400))
    slots = rng.choice(np.arange(0, days * 86400 - window, window), size=per_day * days, replace=False)
    parts = [df]
    for start in sorted(slots):
        w = df[(df.workload_type == "prod") & (df.arrival_timestamp >= start) & (df.arrival_timestamp < start + window)]
        for _ in range(mult - 1):
            c = w.copy()
            c["arrival_timestamp"] = (start + rng.random(len(c)) * window).round(3)
            parts.append(c)
    out = pd.concat(parts, ignore_index=True).sort_values("arrival_timestamp", kind="stable").reset_index(drop=True)
    out["request_id"] = out.index
    return out, sorted(int(s) for s in slots)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("output_csv")
    ap.add_argument("--mult", type=int, default=8)
    ap.add_argument("--window", type=int, default=600, help="giây mỗi burst")
    ap.add_argument("--per_day", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    df = pd.read_csv(a.trace, dtype={"regions": str})
    out, slots = inject(df, a.mult, a.window, a.per_day, np.random.default_rng(a.seed))
    out.to_csv(a.output_csv, index=False)
    print(f"[+] {a.output_csv}: {len(df):,} -> {len(out):,} request; burst x{a.mult} tại (giây): {slots}")


if __name__ == "__main__":
    main()
