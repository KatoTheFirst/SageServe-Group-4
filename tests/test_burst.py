"""F11: burst x8 chỉ nhân IW trong cửa sổ, NIW và phần còn lại giữ nguyên."""
import numpy as np
import pandas as pd

from inject_burst import inject


def test_burst_multiplies_iw_in_window_only():
    n = 86400
    df = pd.DataFrame({"arrival_timestamp": np.arange(n, dtype=float), "workload_type": ["prod", "dev"] * (n // 2),
                       "request_id": range(n)})
    out, slots = inject(df, mult=8, window=600, per_day=3, rng=np.random.default_rng(0))
    assert len(slots) == 3
    inside = lambda d: sum(((d.arrival_timestamp >= s) & (d.arrival_timestamp < s + 600)).sum() for s in slots)
    iw_in = inside(df[df.workload_type == "prod"])
    assert len(out) == n + 7 * iw_in
    assert (out.workload_type == "dev").sum() == (df.workload_type == "dev").sum()
    assert out.arrival_timestamp.is_monotonic_increasing and out.request_id.is_unique
