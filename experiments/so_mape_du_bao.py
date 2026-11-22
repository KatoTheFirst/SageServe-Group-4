"""So sai số dự báo đỉnh giờ tới (T42 Tuần 9, bản đối chiếu): KHÔNG fit lại ARIMA, dùng file dự báo nhân quả có sẵn.
Thực tế: TPM của IW theo phút cho từng (mô hình, vùng gốc), cách tính như generate_causal_arima_forecasts.py; đỉnh thực của giờ h = max TPM trong giờ h.
Các cách dự báo đỉnh giờ h (h >= 1, bỏ giờ 0 warm-up):
  arima_v1      : max dự báo ARIMA-60 trong giờ h (file final_*_arima.csv) – forecast v1 của nhóm
  giu_gio_truoc : đỉnh thực giờ h-1 (persistence, baseline T41)
  max_hai       : max(arima_v1, giu_gio_truoc) – ứng viên v2 "sàn bằng đỉnh giờ trước" (giả định, chủ task chọn)
Chỉ số: MAPE trên ô có đỉnh thực > 0, WAPE, bias (tổng sai/tổng thực), % ô dự báo thiếu. Với trace tuần: tách thêm theo ngày.
Dùng (qua chay_phan_tich.py): python experiments/so_mape_du_bao.py <trace.csv> <thư mục dự báo> <file ra .csv> [--ngay]"""
import glob
import os
import re
import sys

import numpy as np
import pandas as pd

trace, fdir, out = sys.argv[1:4]
theo_ngay = "--ngay" in sys.argv
d = pd.read_csv(trace, usecols=["model_type", "workload_type", "arrival_timestamp", "prompt_size", "regions"], dtype={"regions": str})
d = d[d.workload_type == "prod"]
d["region"] = d.regions.str.zfill(3).str[0].astype(int)
d["phut"] = (d.arrival_timestamp // 60).astype(int)
rows = []
for f in sorted(glob.glob(f"{fdir}/final_*_prod_1minute_region*_arima.csv")):
    m = re.search(r"final_(.+)_prod_1minute_region(\d+)_arima.csv", os.path.basename(f))
    model, r = m.group(1), int(m.group(2))
    x = d[(d.model_type == model) & (d.region == r)]
    fc = pd.read_csv(f)
    n = max(int(fc.Time.max() // 60) + 1, int(x.phut.max()) + 1 if len(x) else 0)
    tpm = x.groupby("phut").prompt_size.sum().reindex(range(n), fill_value=0)
    thuc = tpm.groupby(np.arange(n) // 60).max()
    arima = fc.groupby(fc.Time // 3600).Predicted.max().reindex(thuc.index, fill_value=0)
    df = pd.DataFrame({"gio": thuc.index, "thuc": thuc.values, "arima_v1": arima.values, "giu_gio_truoc": thuc.shift(1).values})
    df["max_hai"] = df[["arima_v1", "giu_gio_truoc"]].max(axis=1)
    rows.append(df.assign(model=model, region=r))
a = pd.concat(rows)
hmax = int((d.arrival_timestamp.max() + 1) // 3600) - 1     # giờ trọn vẹn cuối cùng (DEV-1D: 23 -> giờ 1..23 như T41)
a = a[(a.gio >= 1) & (a.gio <= hmax) & a.giu_gio_truoc.notna()]
a["ngay"] = a.gio // 24


def chi_so(g, cach):
    e = g[cach] - g.thuc
    pos = g.thuc > 0
    return {"cách": cach, "số ô": len(g), "MAPE (%)": 100 * (e[pos].abs() / g.thuc[pos]).mean(), "WAPE (%)": 100 * e.abs().sum() / g.thuc.sum(),
            "bias (%)": 100 * e.sum() / g.thuc.sum(), "dự báo thiếu (%)": 100 * (e < 0).mean()}


kq = []
for cach in ("arima_v1", "giu_gio_truoc", "max_hai"):
    kq.append({"nhóm": "tất cả", **chi_so(a, cach)})
    if theo_ngay:
        for ng, g in a.groupby("ngay"):
            kq.append({"nhóm": f"ngày {ng}", **chi_so(g, cach)})
t = pd.DataFrame(kq)
t.to_csv(out, index=False)
print(f"{trace}\n{t.round(2).to_string(index=False)}")
