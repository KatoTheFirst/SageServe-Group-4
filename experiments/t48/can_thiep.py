"""Kiểm can thiệp (dòng 'Nguyên nhân độ trễ'): vi phạm SLA IW Llama-2 theo giờ của Reactive, LT-U ARIMA, LT-U oracle (trace chính),
cùng cách tính như experiments/analyze_hourly_miss.py; in tổng ở 5 giờ LT-U ARIMA vi phạm thêm nhiều nhất."""
import sys; sys.path.insert(0, ".")
from analyze_s4 import ROUTING_DELAY, concat, sla_of
R = sys.argv[1]                                  # T48: gốc dữ liệu là tham số (bản gốc: D:/SageServe_results/v21)
runs = {"reactive": f"{R}/lt/reactive", "lt_u": f"{R}/lt/lt_u", "lt_u_oracle": f"{R}/oracle/lt/lt_u"}
m = {}
for k, d in runs.items():
    g = concat(f"{d}/global_router/*.csv")
    g = g[(g.workload_type == "prod") & (g.model_type == "llama2-70b")]
    miss = (g.ttft - ROUTING_DELAY) > sla_of(g)
    hour = ((g.completion_time - g.response_time) // 3600).astype(int)
    m[k] = miss.groupby(hour).sum(); m[k] = m[k][m[k].index >= 1]
extra = (m["lt_u"] - m["reactive"]).dropna()
top = sorted(extra.nlargest(5).index.tolist())
print("5 giờ:", top, {k: int(v[top].sum()) for k, v in m.items()})
