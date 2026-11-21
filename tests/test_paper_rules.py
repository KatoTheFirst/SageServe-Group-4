"""Pha 2: mỗi quy tắc §4, §6.1, §6.2, §6.4, §7.1 chưa có test riêng được khóa bằng một test ở đây."""
import random
import statistics
from types import SimpleNamespace as NS

import pytest
import yaml

import allocator
import arbiter
import global_arbiter as GA
import global_router as GR
import model_endpoint_router as M
import region_router as RR
from request import GenerativeLLMRequest
from scheduler import TokenJSQScheduler
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
    a.next_scale_time = {"m": 0}
    a.overheads = NS(reclaim_spot=0, spin_up=0, spin_down=0)
    a.cluster = NS(region=NS(model_endpoint_routers=[]))
    a._scale_up = lambda ep, trigger: spot and (a.calls.append("up") or True)
    a._scale_down = lambda ep, trigger: a.calls.append("down") or True
    return a


# §4, §7.1 Reactive: > 70% tăng, < 30% giảm, không co giãn ở giữa
@pytest.mark.parametrize("mem,want", [(0.71, ["up"]), (0.70, []), (0.5, []), (0.30, []), (0.29, ["down"])])
def test_reactive_thresholds(monkeypatch, mem, want):
    a = stub(arbiter.BasicArbiter, monkeypatch)
    a.scale(endpoint(mem))
    assert a.calls == want


# §6.4 LT-U: chỉ tăng khi còn δ > 0 và bộ nhớ > 70%; chỉ giảm khi còn δ < 0 và bộ nhớ < 30%
@pytest.mark.parametrize("delta,mem,want,left", [
    (1, 0.71, ["up"], 0), (1, 0.70, [], 1), (0, 0.9, [], 0),
    (-1, 0.29, ["down"], 0), (-1, 0.30, [], -1), (0, 0.1, [], 0),
])
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


def test_lt_i_applies_hourly_plan_without_arrivals(monkeypatch):
    now = 0
    events = []
    monkeypatch.setattr(GA, "clock", lambda: now)
    monkeypatch.setattr(GR, "clock", lambda: now)
    monkeypatch.setattr(GR, "schedule_event", lambda delay, fn: events.append((now + delay, fn)))
    monkeypatch.setattr(GA, "schedule_event", lambda delay, fn: fn())
    local = stub(arbiter.GlobalArbiterAwareShortTermArbiter, monkeypatch)
    ep = endpoint(0.5)
    plan = object.__new__(GA.MilpGlobalArbiter)
    GA.GlobalArbiter.__init__(plan, long_term_scaling_interval=3600, max_time=7200)
    plan.regions, plan.models, plan.model_list = 1, 1, ["m"]
    plan.arima_traces = None
    plan.post_processing_strategy = "immediate"
    plan.current_allocations = lambda: [[[0]]]
    plan.get_ilp_forecast = lambda _: [[[2 if now == 0 else -1]]]
    plan.region_clusters = {2: NS(arbiter=local)}
    plan.region_routers = {2: NS(model_endpoint_routers={"m": ep})}
    router = object.__new__(GR.ProbabilisticRouter)
    router.long_term_scaling, router.global_arbiter = True, plan

    router.run()
    assert local.calls == ["up", "up"]
    now, tick = events.pop()
    assert now == 3600
    tick()
    assert local.calls == ["up", "up", "down"]
    assert not plan.scaling_interval_reached()


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
@pytest.mark.parametrize("mem,n", [(0.61, 0), (0.60, 0), (0.59, 1), (0.50, 1), (0.49, 2)])
def test_niw_feed_rate(monkeypatch, mem, n):
    sent = []
    monkeypatch.setattr(simulator, "feed_async_helper", lambda r, m: sent.append(m))
    region = NS(region_cluster=NS(get_memory=lambda m: mem, get_max_memory=lambda m: 1.0))
    simulator.feed_async(region, "m", 1)
    assert len(sent) == n


# §6.1 Global: vùng đầu tiên theo thứ tự có bộ nhớ < 70%; không vùng nào thì vùng bộ nhớ thấp nhất
@pytest.mark.parametrize("mems,want", [([0.5, 0.1, 0.1], 0), ([0.7, 0.6, 0.1], 1), ([0.9, 0.8, 0.75], 2)])
def test_global_routing(mems, want):
    r = object.__new__(GR.ProbabilisticRouter)
    r.region_routers = {i: NS(model_endpoint_routers={"m": 1}) for i in range(3)}
    r.region_clusters = {i: NS(get_memory=lambda m, i=i: mems[i], get_max_memory=lambda m: 1.0) for i in range(3)}
    assert r._select_region(NS(region_priority="012", model_type="m")) == want


def test_global_fallback_skips_missing_model_and_empty_endpoint():
    router = object.__new__(GR.ProbabilisticRouter)
    router.region_routers = {
        0: NS(model_endpoint_routers={}),
        1: NS(model_endpoint_routers={"m": 1}),
        2: NS(model_endpoint_routers={"m": 1}),
    }
    router.region_clusters = {
        1: NS(get_max_memory=lambda m: 0),
        2: NS(get_max_memory=lambda m: 1.0, get_memory=lambda m: 0.8),
    }
    assert router._select_region(NS(region_priority="012", model_type="m")) == 2


# §6.1 Vùng: deployment có bộ nhớ hiệu dụng thấp nhất, bỏ deployment chưa phục vụ
def test_endpoint_routes_to_least_loaded_serving_deployment(monkeypatch):
    monkeypatch.setattr(M, "clock", lambda: 0.0)
    seen = []
    monkeypatch.setattr(M, "schedule_event", lambda d, f: f())
    ep = object.__new__(M.RoundRobin)
    ep.short_term_scaling = False
    ep.overheads = NS(routing_delay=0)
    app = lambda i, mem, cap: NS(application_id=i, get_memory=lambda: mem, get_max_memory=lambda: cap)
    ep.applications = [app(0, 0.8, 1.0), app(4, 0.2, 1.0), app(5, 0.0, 0.0)]
    ep.schedulers = {i: NS(request_arrival=lambda q, i=i: seen.append(i)) for i in (0, 4, 5)}
    ep.route(NS())
    assert seen == [4]


def test_dispatch_reselects_if_deployment_was_removed(monkeypatch):
    events, seen = [], []
    monkeypatch.setattr(M, "schedule_event", lambda delay, callback: events.append(callback))
    ep = M.RoundRobin(region=None, model_name="m", start_state="orca", scaling_interval=15,
                      scaling_level=0, short_term_scaling=False, overheads=NS(routing_delay=1))
    for key, memory in [(3, 0.1), (7, 0.4)]:
        ep.add_application(NS(application_id=key, get_memory=lambda memory=memory: memory,
                              get_max_memory=lambda: 1,
                              scheduler=NS(request_arrival=lambda request, key=key: seen.append(key))))
    ep.route(NS())
    ep.remove_application(ep.applications[0])
    events.pop()()
    assert seen == [7]


def test_chiron_routes_to_mixed_when_dedicated_has_no_ready_capacity(monkeypatch):
    monkeypatch.setattr(RR, "schedule_event", lambda delay, callback: callback())
    seen = []
    router = RR.ChironRegionRouter(overheads=NS(routing_delay=0))
    router.add_model_endpoint(NS(model_name="m-p", get_max_memory=lambda: 0))
    router.add_model_endpoint(NS(model_name="m", get_max_memory=lambda: 1, request_arrival=seen.append))
    request = NS(model_type="m-p")
    router.route(request)
    assert seen == [request]


def test_token_jsq_counts_decode_work_until_it_is_processed():
    def request(request_id, prompt, output):
        return GenerativeLLMRequest(
            request_id=request_id, batch_id=-1, client_tenant=0, request_type=2,
            scenario="IW-F", sla=1, utility=1, regions="012", model_type="m",
            workload_type="prod", application_id=0, prompt_size=prompt, token_size=output,
        )

    jsq = object.__new__(TokenJSQScheduler)
    first, second = NS(sched_pending_tokens=0), NS(sched_pending_tokens=50)
    jsq.instances = [first, second]
    long_request = request(1, prompt=5, output=101)
    jsq.schedule(long_request)
    token_task = next(long_request.successors(long_request.root_node))
    assert first.sched_pending_tokens == 105

    short_request = request(2, prompt=5, output=1)
    jsq.schedule(short_request)
    assert short_request.root_node.instance is second

    token_task.processing_tokens = 60
    token_task.complete_iteration()
    assert first.sched_pending_tokens == 45
    next_request = request(3, prompt=5, output=1)
    jsq.schedule(next_request)
    assert next_request.root_node.instance is first


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
