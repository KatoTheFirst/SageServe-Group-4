"""Pha 3 (độ nhạy): chạy run.py với một tham số đổi qua biến môi trường, không sửa code chính.
SAGE_SPIN_UP (giây khởi động), SAGE_WAIT=1 (Reactive chờ tới khi instance sẵn sàng), SAGE_BETA (β của ILP), SAGE_NO_DOWN=1 (tắt luật giảm LT-UA),
SAGE_LITERAL=1 (Pha 6, D21a: Reactive đúng chữ §4/§7.1, tắt luật 6, 7, 8b)."""
import os
import runpy
import sys

ROOT = os.getcwd()
sys.path.insert(0, ROOT)
import allocator
import arbiter
import global_arbiter

SPIN_UP, WAIT, BETA = os.environ.get("SAGE_SPIN_UP"), os.environ.get("SAGE_WAIT"), os.environ.get("SAGE_BETA")
if BETA:
    global_arbiter.NIW_BUFFER = float(BETA)
if os.environ.get("SAGE_NO_DOWN"):
    arbiter.LTUA_DOWN_RATIO = -1.0
if os.environ.get("SAGE_LITERAL"):
    import model_endpoint_router as mer
    from simulator import clock, schedule_event

    arbiter.size = lambda app: len(app.instances)            # luật 6 tắt: không đếm instance đang chờ
    scale_down = arbiter.BasicArbiter.scale_down_to_spot

    def scale_down_literal(self, model_endpoint):               # luật 7 tắt: bớt/gộp cả khi còn instance chờ
        apps = model_endpoint.applications[-2:]
        saved = [a.pending_instances for a in apps]
        for a in apps:
            a.pending_instances = 0                             # chỉ để vượt câu kiểm tra của luật 7, trả lại ngay sau
        try:
            return scale_down(self, model_endpoint)
        finally:
            for a, p in zip(apps, saved):
                a.pending_instances = p
    arbiter.BasicArbiter.scale_down_to_spot = scale_down_literal

    def route_literal(self, request):                           # luật 8b tắt: round robin; giữ 8a (chỉ deployment đang phục vụ)
        if self.short_term_scaling and clock() > self.last_scale_timestamp + self.scaling_interval:
            self.current_request = request
            self.region.region_cluster.arbiter.scale(self)
            self.last_scale_timestamp = clock()
        serving = [a for a in self.applications if a.get_max_memory() > 0]
        self.idx = (self.idx + 1) % len(serving)
        scheduler = self.schedulers[list(self.schedulers.keys())[serving[self.idx].application_id]]
        schedule_event(self.overheads.routing_delay, lambda s=scheduler, r=request: s.request_arrival(r))
    mer.RoundRobin.route = route_literal
if SPIN_UP:
    init = allocator.Allocator.__init__

    def allocator_init(self, *a, **k):
        init(self, *a, **k)
        _set(self.overheads, spin_up=float(SPIN_UP))
    allocator.Allocator.__init__ = allocator_init
if WAIT:
    arb_init = arbiter.Arbiter.__init__

    def arbiter_init(self, *a, **k):
        arb_init(self, *a, **k)
        _set(self.overheads, spin_up=float(SPIN_UP or 600), reclaim_spot=60.0)
    arbiter.Arbiter.__init__ = arbiter_init


def _set(cfg, **values):
    from omegaconf import OmegaConf
    OmegaConf.set_struct(cfg, False)
    OmegaConf.set_readonly(cfg, False)
    for k, v in values.items():
        cfg[k] = v
    return cfg


sys.argv[0] = os.path.join(ROOT, "run.py")
runpy.run_path(sys.argv[0], run_name="__main__")
