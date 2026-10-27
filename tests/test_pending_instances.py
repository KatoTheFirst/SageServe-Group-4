"""Lấy lại spot / khởi động có độ trễ (§6.1, §7.1) – deployment phải tính cả instance đang chờ, nếu không arbiter
xếp trùng vào cùng deployment (từng sinh deployment 4 instance và kẹt không tăng máy được nữa)."""
from types import SimpleNamespace as NS

import arbiter


def app(n, pending=0):
    return NS(instances=[object()] * n, pending_instances=pending)


def test_size_counts_pending():
    assert arbiter.size(app(2, 1)) == 3


def test_scale_down_waits_for_pending():
    ep = NS(applications=[app(3), app(2, 1)])
    assert arbiter.BasicArbiter.scale_down_to_spot(None, ep) is False
    assert arbiter.GlobalAribiterMemoryUtilizationScaling.scale_down_to_spot(None, ep) is False


def test_scale_up_counts_pending():
    # (2 + 1 đang chờ) = 3 -> phải đi nhánh "deployment đủ 3" (tách deployment mới), không lấy thêm vào deployment cũ
    calls = []
    ep = NS(applications=[app(2, 1)], model_name="m")
    ep.applications[-1].allocator = NS(start_reclaim_spot_instance=lambda m: calls.append("reclaim_into_old"))
    try:
        arbiter.BasicArbiter.scale_up_from_spot(None, ep)
    except Exception:
        pass      # nhánh tách deployment cần cấu hình thật; điều cần kiểm là KHÔNG lấy thêm vào deployment cũ
    assert calls == []


def test_ilp_current_allocation_counts_pending(monkeypatch):
    # ILP chạy khi một instance còn đang lấy lại spot: phải thấy nó, nếu không giao thêm 1 máy trùng (lt_ua, 26/10)
    import global_arbiter as G
    monkeypatch.setattr(G, "clock", lambda: 0.0)
    a = object.__new__(G.MilpGlobalArbiter)
    a.models, a.model_to_idx_mapping = 1, {"m": 0}
    a.num_instances_log = {"region_0_model_0": [], "time": []}
    a.region_routers = {0: NS(model_endpoint_routers={"m": NS(applications=[app(3), app(2, 1)])})}
    assert a.current_allocations() == [[[6]]]
