"""Smoke test: experiments/analyze_oracle.py, analyze_week.py, reactive_behavior.py trên dữ liệu nhỏ cố định, kết quả tính tay."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments"))
import analyze_oracle
import compare_runs
import analyze_week
import reactive_behavior


def fake_run(d, instances, ttfts, times=(3600, 4500, 5400, 6300), arrival0=0.0):
    """instances: {model: số instance}, mỗi mốc thời gian; ttfts: TTFT (gồm 1 s định tuyến) của request IW-F Llama-2."""
    os.makedirs(f"{d}/memory")
    os.makedirs(f"{d}/global_router")
    mem = [{"time": t, "instance": f"westus_{m}_{i}", "memory": 1, "max_memory": 2}
           for t in times for m, n in instances.items() for i in range(n)]
    pd.DataFrame(mem).to_csv(f"{d}/memory/0.csv", index=False)
    g = pd.DataFrame({"request_id": range(len(ttfts)), "ttft": ttfts, "response_time": [x + 1 for x in ttfts],
                      "workload_type": "prod", "utility": 5.0, "sla": 1, "model_type": "llama2-70b"})
    g["completion_time"] = arrival0 + g.response_time
    g.to_csv(f"{d}/global_router/0.csv", index=False)


def test_analyze_oracle_table(tmp_path):
    R = str(tmp_path)
    fake_run(f"{R}/lt/reactive", {"llama2-70b": 2, "bloom-176b": 1}, [1.5, 1.5, 1.5, 3.0])
    fake_run(f"{R}/lt/lt_u", {"llama2-70b": 1, "bloom-176b": 1}, [1.5, 3.0, 3.0, 3.0])
    fake_run(f"{R}/oracle/lt/lt_u", {"llama2-70b": 2, "bloom-176b": 1}, [1.5, 1.5, 1.5, 1.5])
    t = analyze_oracle.table(R, traces=("lt",), strategies=("lt_u",)).set_index(["strategy", "forecast"])
    assert list(t.index) == [("reactive", "-"), ("lt_u", "ARIMA"), ("lt_u", "oracle")]   # thiếu oracle_smooth: bỏ qua
    assert t.loc[("reactive", "-"), "ih_l2"] == 2.0                    # 2 instance × 4 khoảng 15 phút / 4
    assert t.loc[("lt_u", "ARIMA"), "ih_l2_vs_R_%"] == pytest.approx(-50.0)
    assert t.loc[("lt_u", "ARIMA"), "ih_total_vs_R_%"] == pytest.approx(-100 / 3)
    assert t.loc[("reactive", "-"), "miss_l2_%"] == 25.0               # chỉ TTFT 3,0 s (2,0 s sau định tuyến) trượt 1 s
    assert t.loc[("lt_u", "ARIMA"), "miss_l2_%"] == 75.0
    assert t.loc[("lt_u", "oracle"), "miss_l2_%"] == 0.0
    assert t.loc[("reactive", "-"), "ttft_q3_l2"] == pytest.approx(1.875)
    assert t.loc[("lt_u", "oracle"), "ih_l2_vs_R_%"] == 0.0


def test_analyze_week_per_day(tmp_path):
    d = str(tmp_path / "run")
    fake_run(d, {"llama2-70b": 1}, [3.0], times=(3600,))                               # ngày 0: 1 instance, 1 request trượt
    day1 = tmp_path / "day1"
    fake_run(str(day1), {"llama2-70b": 2}, [1.5], times=(86400 + 3600,), arrival0=86400.0)   # ngày 1: 2 instance, không trượt
    for sub in ("memory", "global_router"):
        a = pd.read_csv(f"{d}/{sub}/0.csv")
        b = pd.read_csv(f"{day1}/{sub}/0.csv")
        pd.concat([a, b]).to_csv(f"{d}/{sub}/0.csv", index=False)
    out = analyze_week.per_day(d, day0=4)
    assert list(out.index) == ["T6", "T7"]                              # day0 = 4: thứ Sáu
    assert out.ih.tolist() == [0.25, 0.5]                               # 1 và 2 instance trong một khoảng 15 phút
    assert out["iw_miss_%"].tolist() == [100.0, 0.0]


def test_reactive_behavior_table(tmp_path):
    d = tmp_path / "run"
    os.makedirs(d / "arbiters" / "westus")
    log = ["x SCALEUP_WASTE,100,llama2-70b,reclaim_spot,60,westus",       # giờ đầu: bỏ
           "x SCALEUP_WASTE,4000,llama2-70b,reclaim_spot,60,westus",
           "x SCALEUP_WASTE,5000,llama2-70b,spin_up,600,westus",
           "x SCALEUP_WASTE,6000,bloom-176b,reclaim_spot,60,westus"]       # mô hình khác: bỏ
    (d / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    pd.DataFrame({"timestamp": [0, 3000, 4000, 4500, 5000, 9000, 12000], "model": "llama2-70b",
                  "prod": [5, 4, 3, 4, 5, 4, 5], "spot": 0, "memory_util": 0.5}).to_csv(d / "arbiters/westus/0.csv", index=False)
    t = reactive_behavior.table(str(d)).set_index("vùng")
    w = t.loc["westus"]
    assert w["CHÍNH: lấy lại spot + khởi động"] == 2
    assert (w["lấy lại spot"], w["khởi động mới"]) == (1, 1)
    assert w["scale-in"] == 2                                           # 4000 và 9000; lần giảm lúc 3000 nằm trong giờ đầu
    assert w["flap 1–1 ≤30 phút"] == 1                                  # 4500 khớp 4000; 5000 hết scale-in để ghép; 12000 quá 30 phút
    assert w["lãng phí (instance-giờ)"] == pytest.approx(660 / 3600)
    assert t.loc["tổng", "lãng phí (GPU-giờ, x8)"] == pytest.approx(8 * 660 / 3600)
    assert reactive_behavior.flaps([10], [20, 30]) == 1                 # 1–1: một scale-in không ghép hai lần


def test_compare_runs_config_includes_sage_env(tmp_path):
    def run(name, env):
        d = tmp_path / name
        os.makedirs(d / ".hydra")
        (d / ".hydra/overrides.yaml").write_text(f"- end_time=10\n- output_dir={d}\n", encoding="utf-8")
        if env is not None:
            (d / "sage_env.txt").write_text(env, encoding="utf-8")
        return str(d)
    base, same, lit, old = run("a", ""), run("b", ""), run("c", "SAGE_LITERAL=1\n"), run("d", None)
    assert compare_runs.config_diff(base, same) == []                  # output_dir khác nhưng bị bỏ
    assert compare_runs.config_diff(base, lit) == ["SAGE_LITERAL"]
    assert compare_runs.config_diff(base, old) is None                 # bài cũ không có sage_env.txt: không đối chiếu được
