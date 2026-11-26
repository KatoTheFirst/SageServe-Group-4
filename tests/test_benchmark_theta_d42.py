"""D42: chỉ số bão hòa (b) và chọn θ(b) của benchmark_theta.py."""
import numpy as np
import pandas as pd

import benchmark_theta as B


def test_in_system_dem_request_chua_xong():
    df = pd.DataFrame({"arrival_timestamp": [0.0, 10.0, 20.0]})
    g = pd.DataFrame({"completion_time": [5.0, 30.0]})          # request thứ 3 chưa xong
    assert list(B.in_system(df, g, np.array([0.0, 6.0, 25.0, 40.0]))) == [1, 0, 2, 1]


def test_saturation_on_dinh_va_bung():
    arr = np.arange(0, B.ARRIVE, 1.0)
    df = pd.DataFrame({"arrival_timestamp": arr})
    on = B.saturation(df, pd.DataFrame({"completion_time": arr + 2}), 1.0)
    assert on["sat_ok"] and on["q_end"] <= on["q_start"] + 1
    bung = B.saturation(df, pd.DataFrame({"completion_time": arr[: len(arr) // 2] * 2 + 1}), 1.0)   # xử lý nửa tốc độ đến
    assert not bung["sat_ok"] and bung["q_slope_per_s"] > 0
    assert not B.saturation(df, pd.DataFrame({"completion_time": arr + 2}), 0.98)["sat_ok"]   # < 99% xong


def test_theta_b_lay_muc_truoc_muc_truot_dau():
    x = pd.DataFrame({"level_tps": [100, 125, 156, 195], "sat_ok": [True, True, False, True]})
    assert B.theta_b(x) == 125
    assert B.theta_b(pd.DataFrame({"level_tps": [100], "sat_ok": [False]})) is None
