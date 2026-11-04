"""Pha 2: mỗi quy tắc §4, §6.1, §6.2, §6.4, §7.1 chưa có test riêng được khóa bằng một test ở đây."""
import random
import statistics
from types import SimpleNamespace as NS

import pytest
import yaml

import allocator
import arbiter
import global_router as GR
import model_endpoint_router as M
import simulator


def endpoint(mem, name="m"):
    return NS(model_name=name, get_memory=lambda: mem, get_max_memory=lambda: 1.0, scaling_level=2, tokens_last_minute=lambda: 0, applications=[])


def stub(cls, monkeypatch, now=0.0, changes=None, spot=True):
    """Arbiter thật, thay các thao tác co giãn bằng bộ đếm."""
    monkeypatch.setattr(arbiter, "clock", lambda: now)
    a = object.__new__(cls)
    a.calls = []
    a.results = {k: [] for k in ("timestamp", "model", "prod", "spot", "memory_util")}
    a.changes = {} if changes is None else dict(changes)
    a.scaling_in_progress, a.next_scale_time = {"m": False}, {"m": 0}
    a.overheads = NS(reclaim_spot=0, spin_up=0, spin_down=0)
    a.cluster = NS(region=NS(model_endpoint_routers=[]), has_spot_instance=lambda m: spot, has_spot_instance_any=lambda: False,
                   free_processors_and_kill_spot=lambda: [], get_spot_instance_count=lambda m: 0)
    a.scale_up_from_spot = lambda ep: a.calls.append("up")
    a.scale_down_to_spot = lambda ep: a.calls.append("down") or True
    return a


# §4, §7.1 Reactive: > 70% tăng, < 30% giảm, không co giãn ở giữa
@pytest.mark.parametrize("mem,want", [(0.71, ["up"]), (0.70, []), (0.5, []), (0.30, []), (0.29, ["down"])])
def test_reactive_thresholds(monkeypatch, mem, want):
    a = stub(arbiter.BasicArbiter, monkeypatch)
    a.scale(endpoint(mem))
    assert a.calls == want


# §6.4 LT-U: chỉ tăng khi còn δ > 0 và bộ nhớ > 70%; chỉ giảm khi còn δ < 0 và bộ nhớ < 30%
@pytest.mark.parametrize("delta,mem,want,left", [(1, 0.8, ["up"], 0), (1, 0.5, [], 1), (0, 0.9, [], 0), (-1, 0.2, ["down"], 0), (-1, 0.5, [], -1), (0, 0.1, [], 0)])
def test_lt_u_defers_until_memory_breach(monkeypatch, delta, mem, want, left):
    a = stub(arbiter.GlobalAribiterMemoryUtilizationScaling, monkeypatch, changes={"m": delta})
    a.scale(endpoint(mem))
    assert a.calls == want and a.changes["m"] == left


# §6.4 LT-I: không co giãn theo bộ nhớ giữa giờ
def test_lt_i_does_not_react_to_memory(monkeypatch):
    a = stub(arbiter.GlobalArbiterAwareShortTermArbiter, monkeypatch)
    a.scale(endpoint(0.99))
    a.scale(endpoint(0.01))
    assert a.calls == []


def lt_ua(monkeypatch, second_of_hour, predicted, observed, delta=0, mem=0.5):
    a = stub(arbiter.GlobalArbiterARIMAChecking, monkeypatch, now=3600.0 + second_of_hour, changes={"m": delta})
    t = 60 * ((3600 + second_of_hour) // 60)
    import pandas as pd
    a.arima_forecast = {"m": pd.Series({t: predicted})}
    ep = endpoint(mem)
    ep.tokens_last_minute = lambda: observed
    a.scale(ep)
    return a.calls


# §6.4 LT-UA: 20 phút cuối giờ, đã đạt số instance đích: ≥ 5x tăng, ≤ 0,5x giảm, không cần ngưỡng bộ nhớ
def test_lt_ua_rules(monkeypatch):
    assert lt_ua(monkeypatch, 2400, 100, 500) == ["up"]
    assert lt_ua(monkeypatch, 2400, 100, 499) == []
    assert lt_ua(monkeypatch, 3599, 100, 50) == ["down"]
    assert lt_ua(monkeypatch, 2400, 100, 51) == []


def test_lt_ua_outside_window_behaves_like_lt_u(monkeypatch):
    assert lt_ua(monkeypatch, 2399, 100, 500) == []
    assert lt_ua(monkeypatch, 2399, 100, 10) == []


def test_lt_ua_needs_target_reached(monkeypatch):
    assert lt_ua(monkeypatch, 3000, 100, 500, delta=1, mem=0.5) == []       # còn δ: theo luật LT-U, bộ nhớ chưa vượt
    assert lt_ua(monkeypatch, 3000, 100, 10, delta=-1, mem=0.5) == []


# §6.2 Queue Manager: < 60% đưa 1, < 50% đưa 2, ≥ 60% không đưa
@pytest.mark.parametrize("mem,n", [(0.61, 0), (0.60, 1), (0.50, 1), (0.49, 2)])
def test_niw_feed_rate(monkeypatch, mem, n):
    sent = []
    monkeypatch.setattr(simulator, "feed_async_helper", lambda r, m: sent.append(m))
    region = NS(region_cluster=NS(get_memory=lambda m: mem, get_max_memory=lambda m: 1.0))
    simulator.feed_async(region, "m", 1)
    assert len(sent) == (0 if mem > 0.6 else n)


# §6.1 Global: vùng đầu tiên theo thứ tự có bộ nhớ < 70%; không vùng nào thì vùng bộ nhớ thấp nhất
@pytest.mark.parametrize("mems,want", [([0.5, 0.1, 0.1], "0"), ([0.7, 0.6, 0.1], "1"), ([0.9, 0.8, 0.75], "2")])
def test_global_routing(mems, want):
    r = object.__new__(GR.ProbabilisticRouter)
    r.region_routers = {i: NS(model_endpoint_routers={"m": 1}) for i in range(3)}
    r.region_clusters = {i: NS(get_memory=lambda m, i=i: mems[i], get_max_memory=lambda m: 1.0) for i in range(3)}
    assert r._select_region(NS(region_priority="012", model_type="m")) == want


# §6.1 Vùng: deployment có bộ nhớ hiệu dụng thấp nhất, bỏ deployment chưa phục vụ
def test_endpoint_routes_to_least_loaded_serving_deployment(monkeypatch):
    monkeypatch.setattr(M, "clock", lambda: 0.0)
    seen = []
    monkeypatch.setattr(M, "schedule_event", lambda d, f: f())
    ep = object.__new__(M.RoundRobin)
    ep.short_term_scaling = False
    ep.overheads = NS(routing_delay=0)
    app = lambda i, mem, cap: NS(application_id=i, get_memory=lambda: mem, get_max_memory=lambda: cap)
    ep.applications = [app(0, 0.8, 1.0), app(1, 0.2, 1.0), app(2, 0.0, 0.0)]
    ep.schedulers = {i: NS(request_arrival=lambda q, i=i: seen.append(i)) for i in range(3)}
    ep.route(NS())
    assert seen == [1]


# §7.1 Spot: trung vị 1 phút, tối đa 5 phút
def test_spot_reclaim_delay_distribution():
    random.seed(0)
    x = [allocator.reclaim_spot_delay(60) for _ in range(20000)]
    assert 55 <= statistics.median(x) <= 65 and max(x) <= 300


# §7.1 Chiron: 10 interactive, 5 mixed, 5 batch mỗi mô hình mỗi vùng; Θ = 0,6
def test_chiron_config_and_threshold():
    cfg = yaml.safe_load(open("configs/controller/us3-4models-chiron.yaml", encoding="utf-8"))
    for region in cfg["regions"]:
        counts = {m["model_name"]: m["instance_count"] for m in region["model_endpoints"]}
        for name in ("bloom-176b", "llama2-70b", "llama3.1-8b", "llama3.2-3b"):
            assert (counts[f"{name}-p"], counts[name], counts[f"{name}-d"]) == (10, 5, 5)
    assert "if ibp > 0.6:" in open("arbiter.py", encoding="utf-8").read()
