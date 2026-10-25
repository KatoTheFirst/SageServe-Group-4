"""F9 (§6.5): thứ tự hàng đợi của FCFS / EDF / PF / DPA. Chạy: python -m pytest tests"""
from types import SimpleNamespace as R

import instance as I

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


def test_niw_promoted_after_10h(monkeypatch):
    monkeypatch.setattr(I, "QUEUE_POLICY", "fcfs")
    old_niw = R(workload_type="dev", scenario="NIW", sla=86400, arrival_timestamp=0)
    assert I.queue_key(old_niw, I.NIW_QUEUE_DELAY + 1)[0] == 0
