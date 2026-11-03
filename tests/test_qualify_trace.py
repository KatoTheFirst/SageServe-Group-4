"""Cổng trace T1–T9: các phép đo không phụ thuộc mô phỏng."""
import pandas as pd

import qualify_trace as Q


def frame(minutes):
    return pd.DataFrame({"arrival_timestamp": [60.0 * m for m in minutes], "prompt_size": 100, "token_size": 0, "iw": True})


def test_minute_ratio_uses_peak_hour_and_counts_empty_minutes():
    d = frame([0] + [60 + i for i in range(60)] + [60])     # giờ 1 cao hơn, phút 60 gấp đôi
    r, cv = Q.per_minute_ratio(d, d.iw)
    assert r == 2.0 and cv > 0


def test_forecast_check_flags_misaligned_time(tmp_path):
    good = pd.DataFrame({"Time": [3600 + 60 * m for m in range(60)], "issue_time": 3600, "Predicted": 1.0})
    good.to_csv(tmp_path / "a_arima.csv", index=False)
    assert Q.check_forecasts(tmp_path)[1] == []
    bad = good.assign(Time=good.Time + 3)
    bad.to_csv(tmp_path / "b_arima.csv", index=False)
    assert Q.check_forecasts(tmp_path)[1] == ["b_arima.csv"]


def test_inside_is_inclusive():
    assert Q.inside(1.0, (1.0, 1.31)) and not Q.inside(1.32, (1.0, 1.31))
