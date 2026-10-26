"""NV2 (§6.3): Load Predictor trong vòng lặp mô phỏng – quan sát TPM, huấn luyện ARIMA-60 mỗi giờ, log dự báo vs thực tế."""
from collections import defaultdict
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd

import global_arbiter as G
from generate_causal_arima_forecasts import fit_forecast


def make(mode, monkeypatch, now):
    a = object.__new__(G.MilpGlobalArbiter)
    a.forecast_mode, a.observed, a.forecast_log = mode, defaultdict(lambda: defaultdict(float)), []
    file_fc = pd.DataFrame({"Time": np.arange(0, 7200, 60), "Predicted": 7.0})
    a.forecast_df = {0: {"m": file_fc}}
    a.region_clusters = {0: NS(arbiter=NS())}
    monkeypatch.setattr(G, "clock", lambda: now[0])
    return a


def test_observe_bins_tokens_per_minute(monkeypatch):
    now = [125.0]
    a = make("online", monkeypatch, now)
    a.observe(0, "m", 100)
    a.observe(0, "m", 50)
    assert a.observed[(0, "m")][2] == 150


def test_online_fits_last_60_minutes(monkeypatch):
    now = [0.0]
    a = make("online", monkeypatch, now)
    rng = np.random.default_rng(0)
    tpm = 1e5 + 1e4 * np.sin(np.arange(60) / 9) + rng.normal(0, 1e3, 60)
    for m, v in enumerate(tpm):
        now[0] = 60.0 * m
        a.observe(0, "m", v)
    df = a.predict_hour(0, "m", 3600.0)
    assert len(df) == 60 and df.Time.iloc[0] == 3600.0
    assert np.allclose(df.Predicted.values, fit_forecast(tpm)[0])


def test_first_hour_and_offline_use_file(monkeypatch):
    now = [0.0]
    for mode, t in [("online", 0.0), ("offline", 3600.0)]:
        df = make(mode, monkeypatch, now).predict_hour(0, "m", t)
        assert (df.Predicted == 7.0).all() and len(df) == 60


def test_window_aligned_to_minute_grid(monkeypatch):
    # ILP chạy ở request đầu tiên sau mốc giờ (vd. 3600,3 s) – không được lấy nhầm phút đầu của giờ sau
    now = [0.0]
    a = make("offline", monkeypatch, now)
    fc = pd.DataFrame({"Time": np.arange(0, 3 * 3600, 60), "Predicted": np.r_[np.full(60, 1.0), np.full(60, 2.0), np.full(60, 9.0)]})
    a.forecast_df = {0: {"m": fc}}
    df = a.predict_hour(0, "m", 3600.3)
    assert len(df) == 60 and df.Predicted.max() == 2.0 and df.Time.iloc[0] == 3600
