"""
Phụ lục B (Fig. 17): so sánh 4 mô hình dự báo TPM – ARIMA, Moving Average, TVAR, HMM – theo MAPE và thời gian huấn luyện,
với các cửa sổ huấn luyện 60/90/120/180 phút, dự báo 60 phút tới, phát hành mỗi giờ (như global arbiter dùng).
Hướng của bài báo: MA nhanh nhưng kém chính xác; TVAR và HMM chính xác hơn ARIMA nhưng huấn luyện chậm hơn nhiều;
ARIMA cửa sổ 60 là điểm cân bằng nên được chọn.

Dùng: python compare_forecasters.py traces/composed_day_3regions.csv --out results/forecasters
"""
import argparse
import os
import time
import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression
from statsmodels.tsa.statespace.mlemodel import MLEModel

from generate_causal_arima_forecasts import fit_forecast

HORIZON = 60
WINDOWS = [60, 90, 120, 180]
SERIES = [("bloom-176b", 2), ("bloom-176b", 0), ("llama2-70b", 1), ("llama2-70b", 0)]   # như cổng G9


def moving_average(train):
    return np.full(HORIZON, train[-60:].mean())


class _TVAR(MLEModel):
    """TVAR dạng không gian trạng thái: y_t = [1, y_{t-1}, ..., y_{t-p}]·β_t + ε, β_t = β_{t-1} + η (bước ngẫu nhiên);
    phương sai ε, η ước lượng bằng hợp lý cực đại qua bộ lọc Kalman."""

    def __init__(self, y, p):
        X = np.column_stack([np.ones(len(y) - p)] + [y[p - i - 1:len(y) - i - 1] for i in range(p)])
        super().__init__(y[p:], k_states=p + 1, initialization="diffuse")
        self["design"] = X.T[np.newaxis, :, :]
        self["transition"] = np.eye(p + 1)
        self["selection"] = np.eye(p + 1)
        self.k = p + 1

    @property
    def start_params(self):
        return np.r_[1.0, np.full(self.k, 0.01)]

    def transform_params(self, u):
        return u ** 2

    def untransform_params(self, c):
        return c ** 0.5

    def update(self, params, **kwargs):
        params = super().update(params, **kwargs)
        self["obs_cov", 0, 0] = params[0]
        self["state_cov"] = np.diag(params[1:])


def tvar(train, p=2):
    """TVAR (Phụ lục B): "single-value predictions at each time step" – mỗi bước huấn luyện lại trên cửa sổ trượt
    (gồm cả giá trị vừa dự báo) rồi dự báo 1 giá trị; 60 bước = 60 lần huấn luyện."""
    warnings.filterwarnings("ignore")
    mu, sd = train.mean(), train.std() + 1e-9
    x = list((train - mu) / sd)
    n, out = len(x), []
    for _ in range(HORIZON):
        win = np.array(x[-n:])
        try:
            w = _TVAR(win, p).fit(disp=False, maxiter=200).filtered_state[:, -1]
        except Exception:
            return moving_average(train)
        y = w @ np.r_[1.0, win[::-1][:p]]
        out.append(y)
        x.append(y)
    return np.clip(np.array(out) * sd + mu, 0, None)


def hmm(train, k=3):
    """HMM phát xạ Gaussian trên TPM của cửa sổ (chế độ tải = trạng thái ẩn).
    Dự báo h bước: P(trạng thái cuối) · A^h · trung bình chế độ.
    shortcut: bài báo đưa cả ngày/giờ vào trạng thái; ở đây chỉ dùng token vì trace chính chỉ có 1 ngày."""
    warnings.filterwarnings("ignore")
    mu, sd = train.mean(), train.std() + 1e-9
    try:
        res = MarkovRegression((train - mu) / sd, k_regimes=k, switching_variance=True).fit(disp=False, maxiter=50)
    except Exception:
        return moving_average(train)
    A = res.regime_transition[:, :, -1] if res.regime_transition.ndim == 3 else res.regime_transition
    names = list(res.model.param_names)
    means = np.array([res.params[names.index(f"const[{i}]")] for i in range(k)])
    prob = res.smoothed_marginal_probabilities[-1]
    out = []
    for _ in range(HORIZON):
        prob = A @ prob            # cột = trạng thái hiện tại (quy ước statsmodels)
        out.append(prob @ means)
    return np.clip(np.array(out) * sd + mu, 0, None)


MODELS = {"ARIMA": lambda tr: fit_forecast(tr)[0], "MovingAvg": moving_average, "TVAR": tvar, "HMM": hmm}


def evaluate(tpm, model, window):
    errs, secs = [], []
    for start in range(max(window, 60 * 6), len(tpm) - HORIZON, 60):
        train, actual = tpm[start - window:start], tpm[start:start + HORIZON]
        t0 = time.perf_counter()
        pred = MODELS[model](train)
        secs.append(time.perf_counter() - t0)
        if actual.max() > 0:
            errs.append(abs(pred.max() - actual.max()) / actual.max())      # sai số đỉnh giờ – đại lượng ILP dùng
    return 100 * np.mean(errs), np.mean(secs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--out", default="results/forecasters")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    d = pd.read_csv(a.trace, usecols=["model_type", "workload_type", "arrival_timestamp", "prompt_size", "regions"],
                    dtype={"regions": str})
    d = d[d.workload_type == "prod"]
    d["region"] = d.regions.str.zfill(3).str[0].astype(int)
    minutes = int(d.arrival_timestamp.max() // 60) + 1
    rows = []
    for model_name, r in SERIES:
        x = d[(d.model_type == model_name) & (d.region == r)]
        tpm = x.groupby((x.arrival_timestamp // 60).astype(int)).prompt_size.sum().reindex(range(minutes), fill_value=0)
        for m in MODELS:
            for w in WINDOWS:
                mape, sec = evaluate(tpm.values.astype(float), m, w)
                rows.append({"series": f"{model_name}@{r}", "model": m, "window": w, "mape_%": mape, "train_s": sec})
                print(rows[-1], flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(f"{a.out}/forecasters.csv", index=False)
    print(res.groupby(["model", "window"])[["mape_%", "train_s"]].mean().round(3).unstack("window").to_string())


if __name__ == "__main__":
    main()
