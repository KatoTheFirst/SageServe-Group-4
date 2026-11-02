"""LT-UA (§6.4): so input TPS của IW theo vùng gốc với dự báo ARIMA của chính vùng đó."""
from collections import deque
from types import SimpleNamespace as NS

import pandas as pd

import arbiter
import global_router as GR
import model_endpoint_router as M


def endpoint(monkeypatch, now):
    monkeypatch.setattr(M, "clock", lambda: now[0])
    ep = object.__new__(M.RoundRobin)
    ep.recent_tokens, ep.recent_token_sum = deque(), 0
    return ep


def ratio(monkeypatch, predicted, observed):
    monkeypatch.setattr(arbiter, "clock", lambda: 60.0)
    a = object.__new__(arbiter.GlobalArbiterARIMAChecking)
    a.arima_forecast = {"m": pd.Series({60: predicted})}
    return a.ratio_between_arima_and_actual(NS(model_name="m", tokens_last_minute=lambda: observed))


def test_iw_tokens_window_is_60_seconds(monkeypatch):
    now = [0.0]
    ep = endpoint(monkeypatch, now)
    ep.record_iw_tokens(100)
    now[0] = 30.0
    ep.record_iw_tokens(50)
    assert ep.tokens_last_minute() == 150
    now[0] = 61.0
    assert ep.tokens_last_minute() == 50


def test_ratio_zero_forecast(monkeypatch):
    assert ratio(monkeypatch, 0, 0) == 1.0                 # không tải, không dự báo: không được tăng máy
    assert ratio(monkeypatch, 0, 10) == float("inf")       # có tải mà dự báo 0: dự báo thiếu
    assert ratio(monkeypatch, 100, 50) == 0.5


def test_router_counts_only_iw_at_origin_region(monkeypatch):
    monkeypatch.setattr(GR, "clock", lambda: 0.0)
    monkeypatch.setattr(GR, "schedule_event", lambda delay, f: None)
    seen = {0: [], 1: []}
    def region(i):
        ep = NS(record_iw_tokens=seen[i].append)
        return NS(model_endpoint_routers={"m": ep}, request_arrival=lambda r: None)
    r = object.__new__(GR.ProbabilisticRouter)
    r.long_term_scaling, r.no_reroute = True, True
    r.region_routers = {0: region(0), 1: region(1)}
    r.global_arbiter = NS(scaling_interval_reached=lambda: False, observe=lambda *x: None)
    r.last_reported_allocation_time, r.allocation_interval = 0, 1e9
    r.overheads = NS(routing_delay=0)
    r._select_first_priority_region = lambda q: 0
    r.route(NS(workload_type="prod", region_priority="102", model_type="m", prompt_size=7))
    r.route(NS(workload_type="dev", region_priority="102", model_type="m", prompt_size=9))
    assert seen == {0: [], 1: [7]}                          # vùng gốc 1 dù được định tuyến về 0; NIW không tính
