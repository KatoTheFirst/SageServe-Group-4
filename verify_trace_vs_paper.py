"""
Đối chiếu đặc trưng của một trace (định dạng 15 cột SageServe) với số liệu bài báo (§3, §7.1, Fig. 3-6, 10).

Dùng: python verify_trace_vs_paper.py <trace.csv> --day0 <thứ của ngày 0: 0=Thứ Hai ... 6=Chủ Nhật>
"""
import argparse

import pandas as pd
from statsmodels.tsa.stattools import acf

ap = argparse.ArgumentParser()
ap.add_argument("trace")
ap.add_argument("--day0", type=int, default=0)
a = ap.parse_args()
d = pd.read_csv(a.trace, usecols=["scenario", "model_type", "client_tenant", "arrival_timestamp", "prompt_size", "token_size"])
hours = int(d.arrival_timestamp.max() // 3600) + 1
d["hour"] = (d.arrival_timestamp // 3600).astype(int)
d["weekday"] = (d.arrival_timestamp // 86400 + a.day0).astype(int) % 7
A, B = "bloom-176b", "llama2-70b"           # mô hình A, B của bài báo

print(f"{a.trace}: {len(d):,} request, {hours / 24:.1f} ngày")
share = d.scenario.value_counts(normalize=True) * 100
print(f"1. IW (IW-F+IW-N) = {share.get('IW-F', 0) + share.get('IW-N', 0):.1f}% số request (bài báo 72%); "
      f"IW-F {share.get('IW-F', 0):.1f}%, IW-N {share.get('IW-N', 0):.1f}%, NIW {share.get('NIW', 0):.1f}%")


def ps(tier, model):
    s = d[(d.scenario == tier) & (d.model_type == model)].groupby("hour").size().reindex(range(hours), fill_value=0)
    return acf(s, nlags=24)[24]


print(f"2. Chu kỳ ngày (ACF 24h): IW-F A {ps('IW-F', A):.2f} (0,7-0,95) | IW-N A {ps('IW-N', A):.2f} (0,6-0,8) | "
      f"IW-N B {ps('IW-N', B):.2f} (0,3-0,5) | NIW A {ps('NIW', A):.2f} (0-0,29)")
iwf = d[d.scenario == "IW-F"].groupby("weekday").size()
wk = iwf.reindex(range(5)).mean()
print(f"3. IW-F cuối tuần / ngày thường = {iwf.reindex([5, 6]).mean() / wk:.2f} (bài báo: rất thấp, 'weekends quiescing')")
reg = d.groupby("client_tenant").size()
a_iwf = d[(d.scenario == "IW-F") & (d.model_type == A)].groupby("client_tenant").size()
print(f"4. Vùng West/Central/East = {reg.get(0, 0):,}/{reg.get(1, 0):,}/{reg.get(2, 0):,} (bài báo East > Central > West); "
      f"mô hình A IW-F East/West = {a_iwf.get(2, 0) / max(a_iwf.get(0, 1), 1):.1f} (~4)")
iw = d[d.scenario != "NIW"]
print(f"5. Token IW: input trung vị {iw.prompt_size.median():.0f}, > 1k {100 * (iw.prompt_size > 1000).mean():.0f}% "
      f"(bài báo: phần lớn > 1k); output < 1k {100 * (iw.token_size < 1000).mean():.0f}% (phần lớn < 1k)")
print(f"6. IW:NIW = {(d.scenario != 'NIW').sum() / max((d.scenario == 'NIW').sum(), 1):.1f}:1 (Phụ lục A, T11/2024: 3:1)")
mod = d.model_type.value_counts(normalize=True) * 100
print(f"7. Tỉ trọng mô hình: " + ", ".join(f"{k} {v:.0f}%" for k, v in mod.items()) + " (bài báo: mô hình A đông nhất)")
