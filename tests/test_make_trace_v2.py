"""make_trace_v2: giữ số request mỗi giờ, chỉ đổi đúng thuộc tính được yêu cầu."""
import numpy as np
import pandas as pd

import make_trace_v2 as V


def frame(n=6000):
    rng = np.random.default_rng(0)
    return pd.DataFrame({"arrival_timestamp": np.sort(rng.uniform(0, 7200, n)), "scenario": rng.choice(["IW-F", "NIW"], n),
                         "client_tenant": 2, "regions": "201", "prompt_size": 1000, "model_type": "m"})


def test_reshape_keeps_hourly_counts_and_other_tier():
    d = frame()
    before = d.groupby(d.arrival_timestamp // 3600).size()
    iw_times = d[d.scenario == "IW-F"].arrival_timestamp.values.copy()
    out = V.reshape_minutes(d, d.scenario == "NIW", V.spike_weights([5.0]), np.random.default_rng(1))
    assert out.groupby(out.arrival_timestamp // 3600).size().equals(before)
    assert np.array_equal(out[out.scenario == "IW-F"].arrival_timestamp.values, iw_times.round(3))


def test_spike_reaches_requested_multiple():
    d = frame(60000).assign(scenario="NIW")
    out = V.reshape_minutes(d, d.scenario == "NIW", V.spike_weights([4.0]), np.random.default_rng(1))
    c = out[out.arrival_timestamp < 3600].groupby(out.arrival_timestamp // 60).size()
    assert 3.5 < c.max() / c.median() < 4.5


def test_fill_week_copies_thursday_and_sunday():
    d = pd.DataFrame({"arrival_timestamp": [2.5 * 86400, 6.5 * 86400, 0.5 * 86400], "scenario": ["IW-N", "IW-N", "IW-F"]})
    out = V.fill_week_iwn(d)
    iwn = sorted(out[out.scenario == "IW-N"].arrival_timestamp / 86400)
    assert iwn == [0.5, 1.5, 2.5, 6.5]


def test_redraw_regions_first_digit_matches_tenant():
    d = frame()
    out = V.redraw_regions(d, [1, 1, 1], np.random.default_rng(1))
    iw = out[out.scenario != "NIW"]
    assert (iw.regions.str[0].astype(int) == iw.client_tenant).all() and iw.client_tenant.nunique() == 3
    assert (out[out.scenario == "NIW"].regions == "201").all()


def test_reduce_clip_hits_target():
    d = frame().assign(scenario="IW-F")
    d.loc[d.index[:1200], "prompt_size"] = V.MAX_PROMPT      # 20%
    out = V.reduce_clip(d, 9, np.random.default_rng(1))
    assert abs(100 * (out.prompt_size >= V.MAX_PROMPT).mean() - 9) < 0.1
