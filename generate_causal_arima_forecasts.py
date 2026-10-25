"""
Sinh dự báo ARIMA cho global arbiter theo bài báo (§6.3, Phụ lục B):
- chuỗi Tokens Per Minute (TPM, tổng prompt_size theo phút) của IW, theo từng (mô hình, vùng);
- mỗi đầu giờ h: huấn luyện ARIMA trên 60 phút vừa qua (bậc chọn theo AIC), dự báo 60 phút của giờ h;
  -> mỗi dòng (Time, Predicted) chỉ dùng dữ liệu trước giờ đó (nhân quả).
- giờ 0 chưa có lịch sử: dùng TPM trung bình của giờ 0 (ngoại lệ duy nhất, ghi trong metadata).
- NIW: global arbiter chỉ cần tải NIW đã NHẬN (β = 10% giờ trước) -> ghi nguyên các request NIW.

Đầu ra (tên file global_arbiter.py đọc):
  <out>/final_{model}_prod_1minute_region{r}_arima.csv   (Time, Predicted, issue_time, order)
  <out>/final_{model}_dev_region{r}_exact.csv             (arrival_timestamp, prompt_size)
  <out>/metadata.csv

Dùng: python generate_causal_arima_forecasts.py --trace traces/<trace>.csv --output_dir traces/forecasts/<trace>
"""
import argparse
import hashlib
import os
import warnings
from multiprocessing import Pool

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA

WINDOW = 60      # phút huấn luyện (Phụ lục B: "training window of 60")
HORIZON = 60     # phút dự báo = chu kỳ giải ILP 1 giờ
ORDERS = [(1, 0, 0), (2, 0, 0), (1, 1, 1), (2, 1, 1), (0, 1, 1)]


def fit_forecast(train):
    """Chọn bậc theo AIC trên cửa sổ, trả (dự báo HORIZON bước, bậc). Không hội tụ -> giữ mức trung bình cửa sổ."""
    warnings.filterwarnings("ignore")
    best = None
    for o in ORDERS:
        try:
            fit = ARIMA(train, order=o).fit()
            if np.isfinite(fit.aic) and (best is None or fit.aic < best[0].aic):
                best = (fit, o)
        except Exception:
            pass
    if best is None:
        return np.full(HORIZON, train.mean()), None
    return np.clip(best[0].forecast(HORIZON), 0, None), best[1]


def forecast_series(tpm):
    """tpm: mảng TPM theo phút -> DataFrame dự báo theo giờ, nhân quả."""
    rows = []
    for h in range(int(np.ceil(len(tpm) / HORIZON))):
        start = h * HORIZON
        if h == 0:
            pred, order = np.full(HORIZON, tpm[:HORIZON].mean()), "warmup"
        else:
            pred, order = fit_forecast(tpm[start - WINDOW:start])
        for m, p in enumerate(pred):
            rows.append((60 * (start + m), round(float(p), 2), 60 * start, str(order)))
    return pd.DataFrame(rows, columns=["Time", "Predicted", "issue_time", "order"])


def mape_hourly_peak(tpm, fc):
    """Sai số đỉnh giờ (đại lượng ILP dùng), bỏ giờ 0."""
    act = pd.Series(tpm).groupby(np.arange(len(tpm)) // HORIZON).max()
    pre = fc.groupby(fc.Time // 3600).Predicted.max()
    ok = (act.index > 0) & (act > 0)
    return float(100 * (abs(pre.reindex(act.index) - act) / act)[ok].mean())


def main():
    ap = argparse.ArgumentParser(description="Dự báo ARIMA-60 nhân quả theo giờ (SageServe §6.3)")
    ap.add_argument("--trace", required=True)
    ap.add_argument("--output_dir", required=True)
    ap.add_argument("--workers", type=int, default=max(1, os.cpu_count() - 1))
    a = ap.parse_args()
    os.makedirs(a.output_dir, exist_ok=True)
    d = pd.read_csv(a.trace, usecols=["model_type", "workload_type", "arrival_timestamp", "prompt_size", "regions"],
                    dtype={"regions": str})
    d["region"] = d.regions.str.zfill(3).str[0].astype(int)     # vùng ưu tiên đầu = vùng request được gửi tới
    minutes = int(d.arrival_timestamp.max() // 60) + 1
    keys = sorted(d.groupby(["model_type", "region"]).groups)
    iw = d[d.workload_type == "prod"]
    series = []
    for model, r in keys:
        x = iw[(iw.model_type == model) & (iw.region == r)]
        series.append(x.groupby((x.arrival_timestamp // 60).astype(int)).prompt_size.sum()
                      .reindex(range(minutes), fill_value=0).values.astype(float))
    with Pool(a.workers) as pool:
        forecasts = pool.map(forecast_series, series)

    digest = hashlib.sha256(open(a.trace, "rb").read()).hexdigest()[:16]
    meta = []
    for (model, r), tpm, fc in zip(keys, series, forecasts):
        fc.to_csv(f"{a.output_dir}/final_{model}_prod_1minute_region{r}_arima.csv", index=False)
        dev = d[(d.workload_type == "dev") & (d.model_type == model) & (d.region == r)]
        dev[["arrival_timestamp", "prompt_size"]].to_csv(f"{a.output_dir}/final_{model}_dev_region{r}_exact.csv",
                                                         index=False)
        meta.append({"model": model, "region": r, "minutes": minutes, "iw_tokens": tpm.sum(), "niw_requests": len(dev),
                     "mape_hourly_peak_%": round(mape_hourly_peak(tpm, fc), 1), "window": WINDOW,
                     "horizon": HORIZON, "unit": "TPM", "hour0": "warmup = mean of hour 0", "trace_sha256": digest})
    meta = pd.DataFrame(meta)
    meta.to_csv(f"{a.output_dir}/metadata.csv", index=False)
    print(meta[["model", "region", "niw_requests", "mape_hourly_peak_%"]].to_string(index=False))


if __name__ == "__main__":
    main()
