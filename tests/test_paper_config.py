"""Thông số vận hành của bài báo trong cấu hình (§2.3, §4, §6.1, §7.1) – lỗi overheads = 0 từng làm máy mới sẵn sàng tức thì."""
import glob

import yaml

import arbiter


def load(p):
    return yaml.safe_load(open(p, encoding="utf-8"))


def test_allocator_overheads():
    o = load("configs/orchestrator_repo/allocators/noop.yaml")["overheads"]
    assert o["spin_up"] == 600 and o["reclaim_spot"] == 60 and o["spin_down"] == 0


def test_arbiter_has_no_extra_wait():
    # bài báo chỉ có cooldown 15 s; khoảng chờ "đến khi instance sẵn sàng" của GitHub làm Reactive không tăng máy quá đà
    for p in glob.glob("configs/arbiter_repo/arbiters/*.yaml"):
        o = load(p).get("overheads")
        if o:
            assert o["spin_up"] == 0 and o["reclaim_spot"] == 0 and o["spin_down"] == 0, p


def test_thresholds_and_cooldown():
    assert (arbiter.SCALE_UP_THRESHOLD, arbiter.SCALE_DOWN_THRESHOLD) == (0.7, 0.3)
    assert load("configs/config.yaml")["scaling_interval"] == 15
