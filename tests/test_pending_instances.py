"""Lấy lại spot / khởi động có độ trễ (§6.1, §7.1) – deployment phải tính cả instance đang chờ, nếu không arbiter
xếp trùng vào cùng deployment (từng sinh deployment 4 instance và kẹt không tăng máy được nữa)."""
from types import SimpleNamespace as NS

import pytest

import arbiter
from model_endpoint_router import RoundRobin
from region_cluster import RegionCluster


def app(n, pending=0):
    application = NS(instances=[NS(identity=object()) for _ in range(n)], pending_instances=pending, application_id=0,
                     feed_async=True, feed_async_granularity=1, scheduler=object())
    application.add_instance = application.instances.append
    application.remove_instance = application.instances.remove

    def reserve(_):
        application.pending_instances += 1

    application.allocator = NS(start_reclaim_spot_instance=reserve,
                               start_spin_down_instance=application.remove_instance)
    return application


def endpoint_with_arbiter(monkeypatch, strategy, *apps, max_instances=None):
    region = NS(region_name="westus", model_endpoint_routers=[])
    cluster = NS(region=region, servers={}, has_spot_instance=lambda model: True,
                 get_spot_instance_count=lambda model: 0)
    scaling = strategy(cluster, NS(reclaim_spot=0, spin_up=0, spin_down=0))
    endpoint = RoundRobin(region=region, model_name="m", start_state="orca", scaling_interval=15,
                          scaling_level=2, short_term_scaling=True, overheads=NS(routing_delay=0),
                          max_instances=max_instances)
    endpoint.get_memory = lambda: 0.8
    endpoint.get_max_memory = lambda: 1.0
    for application in apps:
        endpoint.add_application(application)
    monkeypatch.setattr(arbiter, "clock", lambda: 30.0)
    return endpoint, scaling


def test_size_counts_pending():
    assert arbiter.size(app(2, 1)) == 3


def test_scale_down_waits_for_pending():
    ep = NS(applications=[app(3), app(2, 1)])
    assert arbiter.BasicArbiter.scale_down_to_spot(None, ep) is False
    assert arbiter.GlobalAribiterMemoryUtilizationScaling.scale_down_to_spot(None, ep) is False


def test_lt_u_keeps_target_when_split_has_only_one_ready_instance(monkeypatch, caplog):
    current = app(1, 2)
    ep, scaling = endpoint_with_arbiter(monkeypatch, arbiter.GlobalAribiterMemoryUtilizationScaling, current)
    scaling.force_scale_up(ep)
    scaling.scale(ep)
    assert scaling.changes["m"] == 1
    assert ep.instance_counts() == (1, 2)
    assert scaling.next_scale_time == {}

    current.pending_instances -= 1
    current.instances.append(NS(identity=object()))
    new = app(0)
    new.application_id = 1
    monkeypatch.setattr(arbiter.application_repo, "get_application_cfg", lambda name: None)
    monkeypatch.setattr(arbiter.Application, "from_config", lambda *args, **kwargs: new)
    with caplog.at_level("INFO"):
        scaling.scale(ep)
    assert scaling.changes["m"] == 0
    assert [arbiter.size(a) for a in ep.applications] == [2, 2]
    assert [len(a.instances) for a in ep.applications] == [1, 1]
    assert [r.message for r in caplog.records if r.message.startswith("SCALE_EVENT,")] == [
        "SCALE_EVENT,30.0,westus,m,request,up,2,1,2,2"
    ]


def test_lt_i_respects_max_with_pending_and_logs_both_directions(monkeypatch, caplog):
    current = app(2)
    ep, scaling = endpoint_with_arbiter(monkeypatch, arbiter.GlobalArbiterAwareShortTermArbiter,
                                       current, max_instances=3)
    with caplog.at_level("INFO"):
        scaling.force_scale_up(ep)
        scaling.force_scale_up(ep)      # 2 ready + 1 pending đã chạm trần
        scaling.force_scale_down(ep)    # không gộp/bớt deployment đang chờ
        assert ep.instance_counts() == (2, 1)
        current.pending_instances -= 1
        current.instances.append(NS(identity=object()))
        scaling.force_scale_down(ep)
        scaling.force_scale_down(ep)    # đã chạm sàn
    assert ep.instance_counts() == (2, 0)
    assert [r.message for r in caplog.records if r.message.startswith("SCALE_EVENT,")] == [
        "SCALE_EVENT,30.0,westus,m,hourly,up,2,0,2,1",
        "SCALE_EVENT,30.0,westus,m,hourly,down,3,0,2,0",
    ]


@pytest.mark.parametrize("use_arima_ratio", [False, True])
def test_scale_down_respects_disabled_scaling(monkeypatch, use_arima_ratio):
    ep, scaling = endpoint_with_arbiter(monkeypatch, arbiter.GlobalArbiterARIMAChecking, app(3))
    ep.scaling_level = 0
    ep.get_memory = lambda: 0.1
    if use_arima_ratio:
        scaling.arima_forecast["m"] = {}
        monkeypatch.setattr(scaling, "ratio_between_arima_and_actual", lambda ep: 0.1)
        monkeypatch.setattr(arbiter, "clock", lambda: 3000.0)
    else:
        scaling.force_scale_down(ep)
    scaling.scale(ep)
    assert ep.instance_counts() == (3, 0)
    assert scaling.next_scale_time == {}


def test_foreign_spot_can_only_be_reused_after_it_drains():
    cluster = object.__new__(RegionCluster)
    processor = NS(instances=[])
    busy = NS(batch=[object()], pending_queue=[], blocked_queue=[], sched_pending_tokens=1, processors=[processor])
    cluster.spot_instances = {"other": [busy]}
    processor.instances.append(busy)
    assert cluster.free_processors_and_kill_spot() is None
    assert cluster.spot_instances["other"] == [busy] and processor.instances == [busy]
    busy.batch.clear()
    busy.sched_pending_tokens = 0
    assert cluster.free_processors_and_kill_spot() == [processor]
    assert cluster.spot_instances["other"] == [] and processor.instances == []


def test_ilp_current_allocation_counts_pending(monkeypatch):
    # ILP chạy khi một instance còn đang lấy lại spot: phải thấy nó, nếu không giao thêm 1 máy trùng (lt_ua, 26/10)
    import global_arbiter as G
    monkeypatch.setattr(G, "clock", lambda: 0.0)
    a = object.__new__(G.MilpGlobalArbiter)
    a.models, a.model_to_idx_mapping = 1, {"m": 0}
    a.num_instances_log = {"region_0_model_0": [], "time": []}
    a.region_routers = {0: NS(model_endpoint_routers={"m": NS(applications=[app(3), app(2, 1)])})}
    assert a.current_allocations() == [[[6]]]


@pytest.mark.parametrize("start", [[3] * 7, [3, 3, 2], [2]])
def test_lt_i_applies_full_ilp_delta_at_the_hour(monkeypatch, caplog, start):
    # D40 (T48 bậc 2): ở cùng mốc giờ không instance nào kịp ready; trước đây sau ~3 lần tăng thì việc tách deployment
    # bị chặn (cần 2 ready) và phần δ còn lại của ILP bị bỏ (eastus Bloom t = 54000 s: δ = +24, áp 3).
    ep, scaling = endpoint_with_arbiter(monkeypatch, arbiter.GlobalArbiterAwareShortTermArbiter, *[app(n) for n in start])
    ids = iter(range(1, 1000))

    def new_deployment(*args, **kwargs):
        d = app(0)
        d.application_id = next(ids)
        return d

    monkeypatch.setattr(arbiter.application_repo, "get_application_cfg", lambda name: None)
    monkeypatch.setattr(arbiter.Application, "from_config", new_deployment)
    with caplog.at_level("INFO"):
        for _ in range(24):
            scaling.force_scale_up(ep)
    assert sum(ep.instance_counts()) == sum(start) + 24
    assert all(arbiter.size(a) in (2, 3) for a in ep.applications)
    assert sum(len(a.instances) for a in ep.applications) == sum(start)      # instance ready không mất, chỉ chuyển deployment
    assert sum(r.message.startswith("SCALE_EVENT,") for r in caplog.records) == 24
