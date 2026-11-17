"""T38: tối ưu 1–2 (instance.py) kiểm/xóa task trong batch theo danh tính (`is`) thay vì `==` của @dataclass.
Hai cách chỉ khác nhau khi batch chứa hai object Task khác nhau mà bằng nhau theo dataclass. Test này chạy một đoạn mô phỏng thật
(LT-UA, trace cắt 12–15h, 900 s) với một hàm bọc start_iteration chỉ có trong test, và khẳng định điều đó không bao giờ xảy ra.
Điều kiện cần để hai Task bằng nhau: cùng lớp, cùng node_id và cùng request_id (tuple so sánh của dataclass chứa các trường này)."""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACE = "composed_day_3regions_12to15_v2"

HOOK = r'''
import atexit, json, os, runpy, sys
sys.path.insert(0, os.getcwd())
import instance

stats = {"lan_kiem": 0, "cap_ung_vien": 0, "bang_nhau_khac_object": 0, "batch_lon_nhat": 0}
goc = instance.ORCAInstance.start_iteration


def kiem(self):
    goc(self)
    b = self.batch
    stats["lan_kiem"] += 1
    stats["batch_lon_nhat"] = max(stats["batch_lon_nhat"], len(b))
    nhom = {}
    for t in b:
        nhom.setdefault((type(t), t.node_id, getattr(t.request, "request_id", None)), []).append(t)
    for ts in nhom.values():
        for i in range(len(ts)):
            for j in range(i + 1, len(ts)):
                stats["cap_ung_vien"] += 1
                if ts[i] is not ts[j] and ts[i] == ts[j]:
                    stats["bang_nhau_khac_object"] += 1


instance.ORCAInstance.start_iteration = kiem
atexit.register(lambda: json.dump(stats, open(os.environ["T38_STATS"], "w")))
sys.argv = ["run.py"] + sys.argv[1:]
runpy.run_path("run.py", run_name="__main__")
'''


@pytest.mark.skipif(not os.path.exists(f"{ROOT}/traces/{TRACE}.csv"), reason="cần trace v2 (python fetch_traces.py --v2)")
def test_batch_khong_co_hai_task_khac_object_ma_bang_nhau(tmp_path):
    hook, stats = tmp_path / "hook.py", tmp_path / "stats.json"
    hook.write_text(HOOK, encoding="utf-8")
    arb = "global_arbiter_ARIMA_checking"
    cmd = [sys.executable, str(hook), "performance_model.db_path=data/perf_model_4models.csv", "end_time=900", f"output_dir={tmp_path / 'kq'}",
           "trace=random_trace", f"trace.filename={TRACE}", "controller=us3-4models", f"global_arbiter.arima_traces=traces/forecasts/{TRACE}",
           "global_arbiter.theta_file=data/theta_tps_v2.csv", "long_term_scaling=True"] + [f"controller.regions.{r}.arbiter={arb}" for r in range(3)]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env={**os.environ, "T38_STATS": str(stats), "PYTHONIOENCODING": "utf-8"})
    assert p.returncode == 0, p.stderr[-2000:]
    s = json.loads(stats.read_text())
    assert s["lan_kiem"] > 1000 and s["batch_lon_nhat"] > 1, s       # hàm bọc thật sự chạy, batch có nhiều task
    assert s["bang_nhau_khac_object"] == 0, s
