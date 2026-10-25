"""
Cổng G10 – tải đủ để co giãn, đo TRỰC TIẾP từ một bài chạy Reactive (không dựa vào θ):
sau giờ khởi động, số instance lớn nhất (theo 15 phút) của mô hình A, B ở MỌI vùng phải ≥ 4 (= 2 x sàn 1 deployment).
Nếu không, mọi chiến lược đều nằm ở mức sàn và ra kết quả trùng nhau, không kiểm chứng được §7.

Dùng: python check_g10.py results/<bài Reactive> [--skip_hours 1]
"""
import argparse
import glob
import sys

import pandas as pd

MODELS = ["bloom-176b", "llama2-70b"]     # mô hình A, B của bài báo
NEED = 4

ap = argparse.ArgumentParser()
ap.add_argument("run")
ap.add_argument("--skip_hours", type=float, default=1)
a = ap.parse_args()
m = pd.concat(pd.read_csv(f) for f in glob.glob(f"{a.run}/memory/*.csv"))
m = m[m.time >= 3600 * a.skip_hours]
m["region"] = m.instance.str.split("_").str[0]
m["model"] = m.instance.str.split("_").str[1].str.replace(r"-[pd]$", "", regex=True)
m = m[m.model.isin(MODELS)]
c = m.groupby(["model", "region", "time"]).instance.nunique().reset_index()
peak = c.groupby(["model", "region"]).instance.max()
print(peak.unstack().to_string())
ok = (peak >= NEED).all() and len(peak) == len(MODELS) * m.region.nunique()
print(f"\n[{'PASS' if ok else 'FAIL'}] G10 – instance lớn nhất của A, B ở mọi vùng ≥ {NEED} (nhỏ nhất: {peak.min()})")
sys.exit(0 if ok else 1)
