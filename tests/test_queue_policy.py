"""F9 (§6.5): thứ tự hàng đợi của FCFS / EDF / PF / DPA. Chạy: python -m pytest tests"""
from collections import deque
from types import SimpleNamespace as NS

import instance as I
from node import NodeState
from request import Request
import simulator


def R(*, workload_type, scenario, sla, arrival_timestamp, request_id=0, batch_id=-1):
    return Request(
        request_id=request_id, batch_id=batch_id, client_tenant=0, request_type=2,
        scenario=scenario, sla=sla, utility=1, regions="012", model_type="m",
        workload_type=workload_type, application_id=0, arrival_timestamp=arrival_timestamp,
    )

NOW = 100.0
REQS = {
    "F_new": R(workload_type="prod", scenario="IW-F", sla=1, arrival_timestamp=99.5),   # d = +0,5: khẩn
    "N_old": R(workload_type="prod", scenario="IW-N", sla=60, arrival_timestamp=30),    # d = -10: quá hạn nặng
    "N_mid": R(workload_type="prod", scenario="IW-N", sla=60, arrival_timestamp=50),    # d = +10: chưa khẩn
    "F_exp": R(workload_type="prod", scenario="IW-F", sla=1, arrival_timestamp=97),     # d = -2: vừa quá hạn
    "NIW": R(workload_type="dev", scenario="NIW", sla=86400, arrival_timestamp=0),      # NIW chưa chờ đủ 10 h
}


def order(policy, monkeypatch):
    monkeypatch.setattr(I, "QUEUE_POLICY", policy)
    return [k for k, r in sorted(REQS.items(), key=lambda kv: I.queue_key(kv[1], NOW))]


def test_fcfs(monkeypatch):
    assert order("fcfs", monkeypatch) == ["N_old", "N_mid", "F_exp", "F_new", "NIW"]


def test_edf(monkeypatch):
    assert order("edf", monkeypatch) == ["N_old", "F_exp", "F_new", "N_mid", "NIW"]


def test_pf(monkeypatch):
    assert order("pf", monkeypatch) == ["F_exp", "F_new", "N_old", "N_mid", "NIW"]


def test_dpa(monkeypatch):
    # quá hạn nặng > khẩn IW-F > (khẩn IW-N) > chưa khẩn IW-F > chưa khẩn IW-N > vừa quá hạn
    assert order("dpa", monkeypatch) == ["N_old", "F_new", "N_mid", "F_exp", "NIW"]


def test_fcfs_batch_respects_niw_priority_at_ten_hours(monkeypatch):
    monkeypatch.setattr(I, "QUEUE_POLICY", "fcfs")
    new_niw = R(workload_type="prod", scenario="NIW", sla=86400, arrival_timestamp=1,
                request_id=1, batch_id=8)
    aged_niw = REQS["NIW"]
    iw = R(workload_type="prod", scenario="IW-F", sla=1, arrival_timestamp=2, request_id=2)
    instance = object.__new__(I.ORCAInstance)
    instance.processors = []
    instance.batch, instance.max_batch_size = [], 3
    instance.memory, instance.max_memory = 0, 3
    instance.pending_requests = [aged_niw, new_niw, iw]
    instance.request_tasks = {
        request: [NS(request=request, memory=1, state=NodeState.QUEUED)]
        for request in instance.pending_requests
    }
    now = simulator.NIW_PRIORITY_AGE - 1
    monkeypatch.setattr(I, "clock", lambda: now)
    assert [task.request for task in instance.select_batch()[1]] == [iw, aged_niw, new_niw]
    now = simulator.NIW_PRIORITY_AGE
    assert [task.request for task in instance.select_batch()[1]] == [aged_niw, iw, new_niw]


def test_queue_manager_releases_aged_niw_to_signaling_region(monkeypatch):
    aged = REQS["NIW"]
    young = R(workload_type="prod", scenario="NIW", sla=86400, arrival_timestamp=1,
              request_id=1, batch_id=8)
    released = []
    queue_manager = NS(
        time=simulator.NIW_PRIORITY_AGE,
        batch_prod={"m": {0: deque([young])}},
        opp={"m": {0: deque([aged])}},
        global_router=NS(request_arrival=lambda request, *, region_id: released.append((request, region_id))),
    )
    monkeypatch.setattr(simulator, "sim", queue_manager)
    monkeypatch.setattr(simulator, "async_count", 0)

    simulator.feed_async_helper(NS(region_id=0), "m")
    assert released == [(aged, 0)]
    assert list(queue_manager.batch_prod["m"][0]) == [young]
