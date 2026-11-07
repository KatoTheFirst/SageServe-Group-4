"""v2.1 (D30): mỗi sửa lỗi có một test, FAIL trên code trước khi sửa và PASS sau khi sửa.
Theo patch T24 của Đoàn Việt Đức (cooldown, NIW 60%, chia 0, run.sh, requirements), viết lại trên code hiện tại."""
import logging
import os
import shutil
import subprocess
from types import SimpleNamespace as NS

import pytest

import arbiter
import long_term_allocation as lta
import model_endpoint_router as M
import simulator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------- Cooldown (D30): "scaling event" = lần gọi scale() làm số instance (gồm pending) đổi ----------
def reactive(monkeypatch, t, reclaim=0):
    """BasicArbiter thật; thao tác co giãn chỉ ghi lại và cộng pending như code thật."""
    monkeypatch.setattr(arbiter, "clock", lambda: t[0])
    a = object.__new__(arbiter.BasicArbiter)
    a.calls, a.results = [], {k: [] for k in ("timestamp", "model", "prod", "spot", "memory_util")}
    a.scaling_in_progress, a.next_scale_time = {}, {}
    a.overheads = NS(reclaim_spot=reclaim, spin_up=600, spin_down=0)
    a.cluster = NS(region=NS(model_endpoint_routers=[]), has_spot_instance=lambda m: True, has_spot_instance_any=lambda: False,
                   get_spot_instance_count=lambda m: 0)

    def up(ep):
        a.calls.append(("up", t[0])); ep.applications[0].pending_instances += 1
    a.scale_up_from_spot = up
    a.scale_down_to_spot = lambda ep: a.calls.append(("down", t[0]))
    return a


def router(monkeypatch, t, arb, mem):
    monkeypatch.setattr(M, "clock", lambda: t[0])
    r = object.__new__(M.RoundRobin)
    r.short_term_scaling, r.scaling_interval, r.last_scale_timestamp = True, 15, -1e9
    r.model_name, r.scaling_level = "m", 1
    r.region = NS(region_cluster=NS(arbiter=arb))
    r.applications = [NS(instances=[], pending_instances=0, get_max_memory=lambda: 0)]   # không deployment phục vụ: route dừng sau khối co giãn
    r.get_memory, r.get_max_memory = (lambda: mem[0]), (lambda: 1.0)
    return r


def arrive(r, t, now):
    t[0] = now
    with pytest.raises(ValueError):          # min() trên danh sách rỗng: dừng ngay sau khối co giãn
        r.route(NS(prompt_size=1))


def test_noop_call_does_not_restart_cooldown(monkeypatch):
    t, mem = [0.0], [0.5]
    a = reactive(monkeypatch, t)
    r = router(monkeypatch, t, a, mem)
    arrive(r, t, 10.0)                       # 50%: không co giãn -> không phải scaling event
    mem[0] = 0.8
    arrive(r, t, 12.0)                       # 80%: phải tăng ngay, không chờ tới > 25 s
    assert a.calls == [("up", 12.0)]


def test_blocked_call_does_not_restart_cooldown(monkeypatch):
    t, mem = [0.0], [0.8]
    a = reactive(monkeypatch, t, reclaim=60)
    r = router(monkeypatch, t, a, mem)
    for now in (10.0, 30.0, 46.0, 62.0, 70.0):   # tăng lúc 10; bị chặn (đang lấy lại spot) tới 70
        arrive(r, t, now)
    assert a.calls == [("up", 10.0), ("up", 70.0)]


def test_scaling_event_restarts_cooldown_at_decision_time(monkeypatch):
    t, mem = [0.0], [0.8]
    a = reactive(monkeypatch, t)
    r = router(monkeypatch, t, a, mem)
    arrive(r, t, 10.0)                       # quyết định tăng lúc 10 (instance còn pending)
    assert r.last_scale_timestamp == 10.0
    arrive(r, t, 24.0)                       # chưa đủ 15 s
    arrive(r, t, 25.5)
    assert [c for c, _ in a.calls] == ["up", "up"] and a.calls[1][1] == 25.5


def test_noop_lt_u_call_does_not_restart_cooldown(monkeypatch):
    """Áp cho mọi chiến lược: LT-U không đổi số instance thì cũng không đặt lại mốc."""
    t = [0.0]
    arb = NS(scale=lambda ep: None)          # arbiter bất kỳ không co giãn
    r = router(monkeypatch, t, arb, [0.9])
    arrive(r, t, 10.0)
    assert r.last_scale_timestamp == -1e9


# ---------- Queue Manager NIW: chỉ cấp khi < 60% (§6.1, §6.2) ----------
def test_niw_not_fed_at_exactly_60pct(monkeypatch):
    sent = []
    monkeypatch.setattr(simulator, "feed_async_helper", lambda r, m: sent.append(m))
    region = NS(region_cluster=NS(get_memory=lambda m: 0.6, get_max_memory=lambda m: 1.0))
    simulator.feed_async(region, "m", 1)
    assert sent == []


# ---------- Chặn chia 0 khi endpoint chưa có máy sẵn sàng ----------
def test_feed_async_zero_capacity(monkeypatch):
    sent = []
    monkeypatch.setattr(simulator, "feed_async_helper", lambda r, m: sent.append(m))
    region = NS(region_cluster=NS(get_memory=lambda m: 0, get_max_memory=lambda m: 0))
    simulator.feed_async(region, "m", 1)
    assert sent == []


# ---------- run.sh trả mã lỗi khi bài con lỗi ----------
@pytest.mark.skipif(shutil.which("bash") is None, reason="cần bash")
def test_run_sh_propagates_failure(tmp_path):
    p = subprocess.run(["bash", "experiments/run.sh", "s4", "1"], cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "PY": "false", "RESULTS_ROOT": str(tmp_path)})
    assert p.returncode != 0 and "Xong" not in p.stdout


# ---------- requirements.txt ----------
def test_requirements_parse():
    from packaging.requirements import Requirement
    lines = [l.strip() for l in open(os.path.join(ROOT, "requirements.txt")) if l.strip() and not l.startswith("#")]
    reqs = {r.name.lower(): r for r in (Requirement(l) for l in lines)}   # dòng hỏng -> InvalidRequirement
    assert {"tqdm", "statsmodels", "psutil", "hmmlearn"} <= set(reqs)
    assert str(reqs["hmmlearn"].specifier) == "==0.3.3"                    # D26


# ---------- ILP: kiểm trạng thái nghiệm ----------
def test_ilp_not_optimal_keeps_allocation(monkeypatch, caplog):
    monkeypatch.setattr(lta.LpProblem, "solve", lambda self, *a, **k: -1)   # -1 = Infeasible trong PuLP
    a = lta.MilpLongTermAllocation(1, 2, 1, model_tps=[[100]], gpu_cost=[10], startup_cost=[[1]], epsilon=1.0)
    with caplog.at_level(logging.WARNING):
        delta = a.get_ilp_allocations([[[3], [4]]], [[500, 50]], [550])
    assert delta == [[[0]], [[0]]]                                          # giữ cấu hình hiện tại
    assert any("ILP" in r.getMessage() for r in caplog.records)


# ---------- run.py ghi commit + hash git diff vào sage_env.txt ----------
def test_code_identity_written():
    import run
    ident = run.code_identity()
    assert set(ident) == {"CODE_COMMIT", "CODE_DIFF_SHA256"}
    assert all(isinstance(v, str) and v for v in ident.values())


def test_compare_runs_sees_code_difference(tmp_path):
    import sys
    sys.path.insert(0, os.path.join(ROOT, "experiments"))
    import compare_runs
    runs = {}
    for name, h in (("a", "x1"), ("b", "x2")):
        d = tmp_path / name
        (d / ".hydra").mkdir(parents=True)
        (d / ".hydra" / "overrides.yaml").write_text("- end_time=10\n", encoding="utf-8")
        (d / "sage_env.txt").write_text(f"CODE_COMMIT=abc\nCODE_DIFF_SHA256={h}\n", encoding="utf-8")
        runs[name] = str(d)
    assert compare_runs.config_diff(runs["a"], runs["b"]) == ["CODE_DIFF_SHA256"]
