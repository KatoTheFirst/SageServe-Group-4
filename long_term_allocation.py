"""
Bài toán tối ưu dài hạn của SageServe (§5), giải mỗi giờ.

Biến:   δ[i][j][k] nguyên – số instance mô hình i ở vùng j trên GPU k thêm (> 0) hoặc bớt (< 0).
Ràng buộc:
  (1) từng vùng:  Σ_k (n + δ)[i][j][k] · θ[i][k] ≥ ε · ρ_peak[i][j]      (0 < ε ≤ 1, phần dư chuyển vùng khác)
  (2) toàn cục:   Σ_j Σ_k (n + δ)[i][j][k] · θ[i][k] ≥ peak_t(Σ_j ρ[i][j](t))
  (3) δ ≥ −n
Mục tiêu: min γ + μ,  γ = Σ α[k] · δ (chi phí VM),  μ = Σ σ[i][k] · max(δ, 0) (chi phí khởi động mô hình).
"""
import datetime
from typing import List

from pulp import LpMinimize, LpProblem, LpVariable, PULP_CBC_CMD, lpSum

from simulator import clock


class MilpLongTermAllocation:
    def __init__(self,
                 models: int,
                 regions: int,
                 gpus: int,
                 model_tps: List[List[float]],
                 gpu_cost: List[float],
                 startup_cost: List[List[float]],
                 epsilon: float = 1.0) -> None:
        assert 0 < epsilon <= 1, "§5: 0 < ε ≤ 1"
        assert len(model_tps) == models and all(len(r) == gpus for r in model_tps)
        assert len(startup_cost) == models and all(len(r) == gpus for r in startup_cost)
        assert len(gpu_cost) == gpus
        self.models, self.regions, self.gpus = models, regions, gpus
        self.model_tps = model_tps          # θ[i][k], cùng đơn vị với dự báo (TPM)
        self.gpu_cost = gpu_cost            # α[k]
        self.startup_cost = startup_cost    # σ[i][k]
        self.epsilon = epsilon

    def get_ilp_allocations(self,
                            current_allocation: List[List[List[int]]],
                            region_peak: List[List[float]],
                            global_peak: List[float],
                            path: str = None) -> List[List[List[int]]]:
        """current_allocation[i][j][k], region_peak[i][j], global_peak[i] -> δ[j][i][k] (vùng trước, như simulator dùng)."""
        prob = LpProblem(f"solver_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}", LpMinimize)
        idx = [(i, j, k) for i in range(self.models) for j in range(self.regions) for k in range(self.gpus)]
        n = {(i, j, k): current_allocation[i][j][k] for i, j, k in idx}
        delta = LpVariable.dicts("delta", idx, cat="Integer")
        pos = LpVariable.dicts("delta_pos", idx, lowBound=0, cat="Integer")   # = max(δ, 0) khi tối ưu (σ > 0)
        for x in idx:
            prob += delta[x] >= -n[x]
            prob += pos[x] >= delta[x]
        cap = lambda i, j: lpSum((n[(i, j, k)] + delta[(i, j, k)]) * self.model_tps[i][k] for k in range(self.gpus))
        for i in range(self.models):
            for j in range(self.regions):
                prob += cap(i, j) >= self.epsilon * region_peak[i][j]
            prob += lpSum(cap(i, j) for j in range(self.regions)) >= global_peak[i]
        prob += lpSum(self.gpu_cost[k] * delta[(i, j, k)] + self.startup_cost[i][k] * pos[(i, j, k)] for i, j, k in idx)
        if path:
            prob.writeLP(f"{path}/../../ilp_outputs/my_output_at_{clock()}.lp")
        prob.solve(PULP_CBC_CMD(msg=0))
        return [[[round(delta[(i, j, k)].value()) for k in range(self.gpus)] for i in range(self.models)]
                for j in range(self.regions)]


if __name__ == "__main__":
    # Kiểm tra tính tay: 1 mô hình, 2 vùng, θ = 100, α = 10, σ = 1.
    a = MilpLongTermAllocation(1, 2, 1, model_tps=[[100]], gpu_cost=[10], startup_cost=[[1]], epsilon=1.0)
    # ε = 1: vùng 0 cần ceil(250/100) = 3 (đang 1 -> +2), vùng 1 cần 1 (đang 4 -> -3)
    assert a.get_ilp_allocations([[[1], [4]]], [[250, 50]], [300]) == [[[2]], [[-3]]]
    # ε = 0,5: vùng 0 chỉ cần 125 -> 2 instance; toàn cục 300 -> tổng 3 -> vùng 1 giữ 1
    a.epsilon = 0.5
    assert a.get_ilp_allocations([[[1], [4]]], [[250, 50]], [300]) == [[[1]], [[-3]]]
    # ràng buộc toàn cục chặt hơn tổng từng vùng: cần 5 instance tổng
    assert sum(r[0][0] for r in a.get_ilp_allocations([[[0], [0]]], [[100, 100]], [450])) == 5
    print("ILP OK")
