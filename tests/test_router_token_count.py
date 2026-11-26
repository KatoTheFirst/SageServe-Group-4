"""D41: ba cách TokenJSQ đếm "token còn lại" (router.token_count)."""
from types import SimpleNamespace as NS

import pytest
import yaml

import scheduler
import task
from request import GenerativeLLMRequest
from scheduler import TokenJSQScheduler


def req(i, prompt, output):
    return GenerativeLLMRequest(request_id=i, batch_id=-1, client_tenant=0, request_type=2, scenario="IW-F", sla=1, utility=1,
                                regions="012", model_type="m", workload_type="prod", application_id=0,
                                prompt_size=prompt, token_size=output)


def inst(pending=0, pool=0, avail=2000):
    # 1 token KV = 2·hidden·layers·dtype = 2 byte -> sức chứa avail / 2 token
    model = NS(architecture=NS(hidden_size=1, num_layers=1), size=NS(dtype_size=1))
    return NS(sched_pending_tokens=pending, sched_pool_tokens=pool, max_available_memory=avail, model=model)


def jsq(*instances):
    j = object.__new__(TokenJSQScheduler)
    j.instances = list(instances)
    return j


def test_mac_dinh_la_oracle():
    cfg = yaml.safe_load(open("configs/config.yaml", encoding="utf-8"))
    assert cfg["router"]["token_count"] == "oracle" and scheduler.TOKEN_COUNT == "oracle"


def test_prompt1_so_sach_nhu_v21(monkeypatch):
    monkeypatch.setattr(scheduler, "TOKEN_COUNT", "prompt1")
    a, b = inst(0), inst(50)
    r = req(1, prompt=5, output=101)
    jsq(a, b).schedule(r)
    tok = next(r.successors(r.root_node))
    assert a.sched_pending_tokens == 6 and not tok.track_remaining_tokens   # prompt + 1, không biết độ dài đầu ra
    r2 = req(2, prompt=5, output=1)
    jsq(a, b).schedule(r2)
    assert r2.root_node.instance is a                                         # oracle sẽ chọn b (105 > 50)
    assert getattr(r, "pool_instance", None) is None and a.sched_pool_tokens == 0


def test_pool_chon_instance_con_trong_nhieu_nhat(monkeypatch):
    monkeypatch.setattr(scheduler, "TOKEN_COUNT", "pool")
    a, b = inst(pool=100, avail=2000), inst(pool=0, avail=1000)               # trống 900 và 500 token
    r = req(1, prompt=300, output=50)
    jsq(a, b).schedule(r)
    assert r.root_node.instance is a and a.sched_pool_tokens == 400 and a.sched_pending_tokens == 301
    assert scheduler.pool_free_tokens(a) == 600 and scheduler.pool_free_tokens(b) == 500
    r2 = req(2, prompt=10, output=5)
    jsq(a, b).schedule(r2)
    assert r2.root_node.instance is a                                         # 600 > 500: chưa tính đầu ra chưa sinh của r
    task.pool_add(r, 150)                                                     # r sinh thêm 150 token
    assert scheduler.pool_free_tokens(a) == 440
    r3 = req(3, prompt=10, output=5)
    jsq(a, b).schedule(r3)
    assert r3.root_node.instance is b                                         # 440 < 500
    task.pool_release(r)
    assert a.sched_pool_tokens == 110 and r.pool_instance is None             # còn 100 sẵn có + prompt r2 (r3 sang b)
    task.pool_release(r)                                                      # gọi lại không trừ thêm
    assert a.sched_pool_tokens == 110


def test_pool_hoa_lay_instance_dau(monkeypatch):
    monkeypatch.setattr(scheduler, "TOKEN_COUNT", "pool")
    a, b = inst(), inst()
    r = req(1, prompt=1, output=1)
    jsq(a, b).schedule(r)
    assert r.root_node.instance is a


def test_gia_tri_la_bi_tu_choi():
    import initialize
    cfg = NS(feed_async_granularity=1, queue_policy="fcfs", router=NS(token_count="sai"), controller=NS(regions=[]))
    with pytest.raises(ValueError):
        initialize.init_regions(cfg, None)
