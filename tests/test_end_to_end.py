"""
Kiểm thử toàn bộ simulator (end-to-end) trên trace nhỏ tự sinh: 3 vùng x 4 mô hình, request đến trong 1,5 giờ,
mô phỏng 3 giờ (bội số 3600 s: lần ghi kết quả cuối rơi đúng end_time) – ILP chạy ở giờ 0 và ở thời điểm lẻ sau
mốc giờ 1 (ILP chỉ chạy khi có request đi qua global router, như mô phỏng thật).
Bloom ở eastus chỉ khởi đầu 4 instance để có thêm co giãn; nhánh khởi động máy mới từ GPU spot của mô hình khác được
thử ở lt_i (ILP giờ 0 tăng Llama-2 ở eastus khi vùng này chưa có spot Llama-2).
Bất biến: không lỗi; mọi request hoàn thành; cooldown >= 15 s giữa hai quyết định co giãn; deployment <= 3 instance;
mọi instance được thêm đều qua lấy lại spot / khởi động có độ trễ (có log SCALEUP_WASTE); Load Predictor online trùng offline.  Chạy riêng: python -m pytest tests/test_end_to_end.py  (vài phút)
"""
import glob
import os
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from compose_trace import COLS

NAME = "_test_e2e"
ARRIVE, END = 5400, 10800       # giây: request đến trong [0, ARRIVE), mô phỏng tới END
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = ["bloom-176b", "llama2-70b", "llama3.1-8b", "llama3.2-3b"]
RUNS = {
    "reactive": ["long_term_scaling=False"],
    "lt_i": ["long_term_scaling=True", "arb=global_arbiter_short_term_scaling"],
    "lt_u": ["long_term_scaling=True", "arb=global_arbiter_memory_utilization"],
    "lt_ua_offline": ["long_term_scaling=True", "arb=global_arbiter_ARIMA_checking", "global_arbiter.forecast_mode=offline"],
    "lt_ua_online": ["long_term_scaling=True", "arb=global_arbiter_ARIMA_checking", "global_arbiter.forecast_mode=online"],
}


def make_trace():
    rng = np.random.default_rng(0)
    rows = []
    for r in range(3):
        for m, rate in zip(MODELS, [1.5, 1.0, 0.4, 0.2]):            # request/giây, đủ để Bloom phải co giãn
            for wt, frac in [("prod", 0.75), ("dev", 0.25)]:
                n = rng.poisson(rate * frac * ARRIVE)
                t = np.sort(rng.uniform(0, ARRIVE, n))
                rows.append(pd.DataFrame({"arrival_timestamp": t.round(3), "model_type": m, "workload_type": wt,
                                          "client_tenant": r, "regions": [f"{r}{(r + 1) % 3}{(r + 2) % 3}"] * n,
                                          "scenario": "IW-F" if wt == "prod" else "NIW", "sla": 1 if wt == "prod" else 86400,
                                          "utility": 5.0 if wt == "prod" else 1.0,
                                          "prompt_size": rng.integers(200, 4000, n), "token_size": rng.integers(50, 800, n)}))
    df = pd.concat(rows).sort_values("arrival_timestamp", kind="stable").reset_index(drop=True)
    df["request_id"] = df.index
    df["batch_id"], df["request_type"], df["application_id"], df["batch_size"] = -1, 2, 0, 1
    df[COLS].to_csv(f"{ROOT}/traces/{NAME}.csv", index=False)
    return df


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    trace = make_trace()
    out = tmp_path_factory.mktemp("e2e")
    subprocess.run([sys.executable, "generate_causal_arima_forecasts.py", "--trace", f"traces/{NAME}.csv",
                    "--output_dir", f"traces/forecasts/{NAME}", "--workers", "2"], cwd=ROOT, check=True, capture_output=True)
    procs = {}
    for name, extra in RUNS.items():
        args = []
        for e in extra:
            if e.startswith("arb="):
                args += [f"controller.regions.{i}.arbiter={e[4:]}" for i in range(3)]
            else:
                args.append(e)
        cmd = [sys.executable, "run.py", "performance_model.db_path=data/perf_model_4models.csv", f"end_time={END}",
               "trace=random_trace", f"trace.filename={NAME}", "controller=us3-4models",
               f"global_arbiter.arima_traces=traces/forecasts/{NAME}", f"output_dir={(out / name).as_posix()}",
               "controller.regions.2.model_endpoints.1.instance_count=4"] + args
        procs[name] = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                       encoding="utf-8", errors="ignore")
    logs = {name: p.communicate()[0] for name, p in procs.items()}
    yield trace, out, logs
    os.remove(f"{ROOT}/traces/{NAME}.csv")
    shutil.rmtree(f"{ROOT}/traces/forecasts/{NAME}")


@pytest.mark.parametrize("name", list(RUNS))
def test_run_completes_without_error(runs, name):
    _, _, logs = runs
    assert "Traceback" not in logs[name] and "TraceSimulator completed" in logs[name], logs[name][-2000:]


@pytest.mark.parametrize("name", list(RUNS))
def test_all_requests_finish(runs, name):
    trace, out, _ = runs
    g = pd.concat(pd.read_csv(f) for f in glob.glob(f"{out}/{name}/global_router/*.csv"))
    assert set(g.request_id) == set(trace.request_id)


@pytest.mark.parametrize("name", list(RUNS))
def test_cooldown_and_deployment_size(runs, name):
    _, out, _ = runs
    mem = pd.concat(pd.read_csv(f) for f in glob.glob(f"{out}/{name}/memory/*.csv"))
    parts = mem.instance.str.rsplit("_", n=2)          # <vùng>_<mô hình>_<deployment>_<instance>
    mem["app"] = parts.str[0] + "_" + parts.str[1]
    assert mem.groupby(["app", "time"]).instance.nunique().max() <= 3      # deployment 2–3 instance (§6.1)
    ups = [l.split("SCALEUP_WASTE,")[1].split(",") for l in open(f"{out}/{name}/run.log", encoding="utf-8")
           if "SCALEUP_WASTE," in l]
    for (model, region), t in pd.DataFrame([(float(u[0]), u[1], u[4]) for u in ups],
                                           columns=["t", "model", "region"]).groupby(["model", "region"]).t:
        gaps = np.diff(np.unique(t.values))
        assert (gaps >= 15 - 1e-6).all(), (model, region, gaps.min())   # cooldown 15 s (§4)


def scaleups(path):
    return [l.split("SCALEUP_WASTE,")[1].strip().split(",") for l in open(path, encoding="utf-8") if "SCALEUP_WASTE," in l]


@pytest.mark.parametrize("name", list(RUNS))
def test_every_added_instance_has_startup_delay(runs, name):
    # instance chỉ được vào phục vụ sau khi lấy lại spot (~1–5 phút) hoặc khởi động (10 phút, §7.1) – cả hai đều ghi log
    _, out, _ = runs
    mem = pd.concat(pd.read_csv(f, usecols=["time", "instance"]) for f in glob.glob(f"{out}/{name}/memory/*.csv"))
    p = mem.instance.str.split("_")
    mem["key"] = p.str[0] + "_" + p.str[1]
    c = mem.groupby(["key", "time"]).instance.nunique().reset_index().sort_values(["key", "time"])
    added = c.groupby("key").instance.diff().clip(lower=0).groupby(c.key).sum()
    logged = pd.Series([f"{u[4]}_{u[1]}" for u in scaleups(f"{out}/{name}/run.log")]).value_counts()
    assert (added <= logged.reindex(added.index, fill_value=0)).all(), pd.DataFrame({"added": added, "logged": logged})
    assert all(float(u[3]) == 600 for u in scaleups(f"{out}/{name}/run.log") if u[2] == "spin_up")


def test_spin_up_path_exercised(runs):
    _, out, _ = runs
    assert any(u[2] == "spin_up" for u in scaleups(f"{out}/lt_i/run.log"))


def test_online_forecast_equals_offline(runs):
    _, out, _ = runs
    on = pd.read_csv(f"{out}/lt_ua_online/forecast_log.csv")
    off = pd.read_csv(f"{out}/lt_ua_offline/forecast_log.csv")
    m = on.merge(off, on=["hour", "region", "model"], suffixes=("_on", "_off"))
    assert {0, 1} <= set(m.hour) and len(m[m.hour == 1]) == 12      # giờ 1 phải có đủ 3 vùng x 4 mô hình
    assert np.allclose(m.pred_peak_tpm_on, m.pred_peak_tpm_off, rtol=1e-4)
