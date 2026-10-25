"""F18: thời gian giải ILP §5 (bài báo: ~1,41 s cấu hình nhỏ, ~3 s cấu hình lớn). Dùng: python bench_ilp.py"""
import random
import time

from long_term_allocation import MilpLongTermAllocation

for models, regions, gpus in [(4, 3, 1), (4, 3, 2), (10, 5, 2)]:
    random.seed(0)
    a = MilpLongTermAllocation(models, regions, gpus,
                               model_tps=[[random.uniform(3e5, 2e6) for _ in range(gpus)] for _ in range(models)],
                               gpu_cost=[10 * (k + 1) for k in range(gpus)],
                               startup_cost=[[10 * (k + 1) / 6 for k in range(gpus)] for _ in range(models)], epsilon=0.9)
    times = []
    for _ in range(10):
        n = [[[random.randint(2, 20) for _ in range(gpus)] for _ in range(regions)] for _ in range(models)]
        peak = [[random.uniform(1e6, 2e7) for _ in range(regions)] for _ in range(models)]
        t = time.perf_counter()
        a.get_ilp_allocations(n, peak, [1.1 * sum(p) for p in peak])
        times.append(time.perf_counter() - t)
    print(f"{models} mô hình x {regions} vùng x {gpus} GPU: trung bình {sum(times) / len(times):.2f} s, lớn nhất {max(times):.2f} s")
