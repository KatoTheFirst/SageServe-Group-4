"""
Unit tests cho Optimizer v0 – ILP (n+δ), ràng buộc cục bộ & toàn cục.

Mỗi test đi kèm bước tính tay để kiểm chứng đáp án.
Không cần simulator (không import simulator.py).
"""
import math
import pytest

from optimizer import Optimizer, OptimizerResult


# ═══════════════════════════════════════════════════════════════════
# 1. HELPERS tạo Optimizer nhanh
# ═══════════════════════════════════════════════════════════════════

def make_1model_2region_1gpu(eps=1.0, theta=100, alpha=10, sigma=1):
    """1 mô hình, 2 vùng, 1 loại GPU – ví dụ đơn giản nhất."""
    return Optimizer(
        models=1, regions=2, gpus=1,
        model_tps=[[theta]],
        gpu_cost=[alpha],
        startup_cost=[[sigma]],
        epsilon=eps,
    )


def make_2model_2region_1gpu(eps=1.0):
    """2 mô hình, 2 vùng, 1 GPU. θ₀=100, θ₁=200, α=10, σ=1."""
    return Optimizer(
        models=2, regions=2, gpus=1,
        model_tps=[[100], [200]],
        gpu_cost=[10],
        startup_cost=[[1], [1]],
        epsilon=eps,
    )


def make_1model_2region_2gpu(eps=1.0):
    """1 mô hình, 2 vùng, 2 loại GPU. θ₀=100, θ₁=300; α=[10,30]; σ=[1,3]."""
    return Optimizer(
        models=1, regions=2, gpus=2,
        model_tps=[[100, 300]],
        gpu_cost=[10, 30],
        startup_cost=[[1, 3]],
        epsilon=eps,
    )


# ═══════════════════════════════════════════════════════════════════
# 2. CÁC TEST CƠ BẢN – 1 mô hình, 2 vùng, 1 GPU
# ═══════════════════════════════════════════════════════════════════

class TestBasic1Model2Region1GPU:
    """
    θ = 100 TPS/instance, α = 10, σ = 1.
    """

    def test_eps1_scale_up_and_down(self):
        """
        ε = 1.0, n = [[[1],[4]]], ρ_peak = [[250, 50]], global_peak = [300].

        Tính tay:
          Vùng 0: (n+δ)·100 ≥ 250  →  n+δ ≥ 3  →  δ ≥ 2  (n=1)
          Vùng 1: (n+δ)·100 ≥ 50   →  n+δ ≥ 1  →  δ ≥ −3 (n=4)
          Toàn cục: tổng(n+δ)·100 ≥ 300 →  tổng ≥ 3
          Hàm mục tiêu: min 10·δ + 1·max(δ,0)
            Vùng 0: δ=2 → 10·2 + 1·2 = 22
            Vùng 1: δ=-3 → 10·(-3) + 0 = -30  (bớt 3 máy tiết kiệm)
            Tổng = 22 - 30 = -8
          n* = [3, 1], δ = [+2, -3]
        """
        opt = make_1model_2region_1gpu(eps=1.0)
        result = opt.solve([[[1], [4]]], [[250, 50]], [300])
        assert result.is_optimal
        # δ theo [vùng][mô hình][gpu]: vùng 0 δ=+2, vùng 1 δ=-3
        assert result.delta == [[[2]], [[-3]]]
        # Hàm mục tiêu: -8
        assert abs(result.objective_value - (-8)) < 1e-6

    def test_eps05_allows_reroute(self):
        """
        ε = 0.5: vùng 0 chỉ cần 0.5·250 = 125 → ceil(125/100) = 2 instance.
        Toàn cục: tổng ≥ 300/100 = 3 → vùng 1 cần 1 instance.
        n = [[[1],[4]]]: δ = [+1, -3].

        Tính tay:
          Vùng 0: (1+1)·100 = 200 ≥ 125 ✓
          Vùng 1: (4-3)·100 = 100 ≥ 25  ✓
          Toàn cục: 200 + 100 = 300 ≥ 300 ✓
          Mục tiêu: 10·1 + 1·1 + 10·(-3) = 11 - 30 = -19
        """
        opt = make_1model_2region_1gpu(eps=0.5)
        result = opt.solve([[[1], [4]]], [[250, 50]], [300])
        assert result.is_optimal
        assert result.delta == [[[1]], [[-3]]]
        assert abs(result.objective_value - (-19)) < 1e-6

    def test_global_constraint_binds(self):
        """
        ε = 0.5, n = [[[0],[0]]], ρ_peak = [[100, 100]], global_peak = [450].

        Cục bộ ε = 0.5: vùng 0 ≥ 50/100 = 0.5 → 1, vùng 1 → 1. Tổng cục bộ ≥ 2.
        Toàn cục: tổng·100 ≥ 450 → tổng ≥ 5.
        Ràng buộc toàn cục chặt hơn → cần tổng 5 instance.
        """
        opt = make_1model_2region_1gpu(eps=0.5)
        result = opt.solve([[[0], [0]]], [[100, 100]], [450])
        assert result.is_optimal
        total = sum(result.delta[j][0][0] for j in range(2))
        assert total == 5

    def test_no_change_needed(self):
        """
        n đã đủ, δ = 0 tối ưu.
        n = [[[3],[2]]], ρ_peak = [[300, 200]], global_peak = [500], ε=1.
        Vùng 0: 3·100 = 300 ≥ 300 ✓
        Vùng 1: 2·100 = 200 ≥ 200 ✓
        Toàn cục: 500 ≥ 500 ✓
        Bớt 1 máy bất kỳ sẽ vi phạm → δ = [0, 0], mục tiêu = 0.
        """
        opt = make_1model_2region_1gpu(eps=1.0)
        result = opt.solve([[[3], [2]]], [[300, 200]], [500])
        assert result.is_optimal
        assert result.delta == [[[0]], [[0]]]
        assert abs(result.objective_value) < 1e-6

    def test_pure_scale_down(self):
        """
        n dư thừa, bớt máy tiết kiệm.
        n = [[[10],[10]]], ρ_peak = [[200, 100]], global_peak = [300], ε=1.
        Cần: vùng 0 ≥ 2, vùng 1 ≥ 1, toàn cục ≥ 3.
        Bớt: vùng 0 δ=-8, vùng 1 δ=-9.
        Mục tiêu: 10·(-8) + 10·(-9) = -170 (tiết kiệm).
        """
        opt = make_1model_2region_1gpu(eps=1.0)
        result = opt.solve([[[10], [10]]], [[200, 100]], [300])
        assert result.is_optimal
        assert result.delta == [[[-8]], [[-9]]]
        assert abs(result.objective_value - (-170)) < 1e-6

    def test_pure_scale_up(self):
        """
        n = 0 ở cả hai vùng, cần thêm tất cả.
        n = [[[0],[0]]], ρ_peak = [[300, 200]], global_peak = [500], ε=1.
        Cần: vùng 0 ≥ 3, vùng 1 ≥ 2, toàn cục ≥ 5 (trùng tổng cục bộ).
        δ = [3, 2], mục tiêu: 10·3 + 1·3 + 10·2 + 1·2 = 33 + 22 = 55.
        """
        opt = make_1model_2region_1gpu(eps=1.0)
        result = opt.solve([[[0], [0]]], [[300, 200]], [500])
        assert result.is_optimal
        assert result.delta == [[[3]], [[2]]]
        assert abs(result.objective_value - 55) < 1e-6

    def test_delta_lower_bound(self):
        """
        δ ≥ −n: không thể bớt nhiều hơn hiện có.
        n = [[[1],[0]]], ρ_peak = [[0, 0]], global_peak = [0], ε=1.
        Vùng 0: có 1, bớt tối đa 1 → δ=-1.
        Vùng 1: có 0, không thể bớt → δ=0.
        Mục tiêu: 10·(-1) = -10.
        """
        opt = make_1model_2region_1gpu(eps=1.0)
        result = opt.solve([[[1], [0]]], [[0, 0]], [0])
        assert result.is_optimal
        assert result.delta == [[[-1]], [[0]]]
        assert abs(result.objective_value - (-10)) < 1e-6


# ═══════════════════════════════════════════════════════════════════
# 3. MULTI-MODEL TESTS
# ═══════════════════════════════════════════════════════════════════

class TestMultiModel:
    """2 mô hình, 2 vùng, 1 GPU. θ₀=100, θ₁=200."""

    def test_two_models_independent(self):
        """
        Mô hình 0: ρ_peak = [200, 100], global = [300], n = [[[2],[1]]]
          → đủ (2·100=200≥200, 1·100=100≥100, 300≥300), δ=0.
        Mô hình 1: ρ_peak = [400, 200], global = [600], n = [[[2],[1]]]
          → đủ (2·200=400≥400, 1·200=200≥200, 600≥600), δ=0.
        """
        opt = make_2model_2region_1gpu(eps=1.0)
        result = opt.solve(
            [[[2], [1]], [[2], [1]]],
            [[200, 100], [400, 200]],
            [300, 600],
        )
        assert result.is_optimal
        # δ[j][i][k]: vùng j, mô hình i
        assert result.delta == [[[0], [0]], [[0], [0]]]

    def test_two_models_one_needs_more(self):
        """
        Mô hình 0 (θ=100): ρ_peak=[300,100], global=[400], n=[[[2],[1]]].
          Cục bộ: vùng 0 cần 3, thiếu 1.
          Toàn cục: cần 4, có 3, cần +1 ở vùng 0 → δ₀=[+1, 0].
        Mô hình 1 (θ=200): ρ_peak=[400,200], global=[600], n=[[[2],[1]]].
          Đã đủ → δ₁=[0, 0].
        Mục tiêu: 10·1 + 1·1 = 11.
        """
        opt = make_2model_2region_1gpu(eps=1.0)
        result = opt.solve(
            [[[2], [1]], [[2], [1]]],
            [[300, 100], [400, 200]],
            [400, 600],
        )
        assert result.is_optimal
        # vùng 0: mô hình 0 +1, mô hình 1 0
        # vùng 1: mô hình 0 0, mô hình 1 0
        assert result.delta[0][0] == [1]   # vùng 0, mô hình 0
        assert result.delta[0][1] == [0]   # vùng 0, mô hình 1
        assert result.delta[1][0] == [0]   # vùng 1, mô hình 0
        assert result.delta[1][1] == [0]   # vùng 1, mô hình 1
        assert abs(result.objective_value - 11) < 1e-6


# ═══════════════════════════════════════════════════════════════════
# 4. MULTI-GPU TESTS
# ═══════════════════════════════════════════════════════════════════

class TestMultiGPU:
    """1 mô hình, 2 vùng, 2 GPU. θ=[100,300], α=[10,30], σ=[1,3]."""

    def test_prefer_cheap_gpu(self):
        """
        ρ_peak = [[100, 0]], global = [100], n = [[[0,0],[0,0]]], ε=1.
        Cần vùng 0 ≥ 100:
          - 1 GPU loại 0 (θ=100): chi phí 10+1 = 11
          - 1 GPU loại 1 (θ=300): chi phí 30+3 = 33
        Tối ưu: chọn GPU rẻ → δ vùng 0 = [1, 0].
        """
        opt = make_1model_2region_2gpu(eps=1.0)
        result = opt.solve([[[0, 0], [0, 0]]], [[100, 0]], [100])
        assert result.is_optimal
        assert result.delta[0][0] == [1, 0]  # vùng 0: 1 GPU loại 0
        assert result.delta[1][0] == [0, 0]  # vùng 1: không cần

    def test_need_big_gpu_when_demand_high(self):
        """
        ρ_peak = [[250, 0]], global = [250], n = [[[0,0],[0,0]]], ε=1.
        Cần vùng 0 ≥ 250:
          - 3 GPU loại 0 (3·100=300≥250): 3·(10+1) = 33
          - 1 GPU loại 1 (300≥250): 30+3 = 33
          - 2 GPU0 + hỗn hợp không đạt 250
        Chi phí bằng nhau → solver chọn một trong hai. Kiểm tổng năng lực ≥ 250.
        """
        opt = make_1model_2region_2gpu(eps=1.0)
        result = opt.solve([[[0, 0], [0, 0]]], [[250, 0]], [250])
        assert result.is_optimal
        d = result.delta[0][0]  # vùng 0, mô hình 0
        cap = d[0] * 100 + d[1] * 300
        assert cap >= 250
        assert abs(result.objective_value - 33) < 1e-6


# ═══════════════════════════════════════════════════════════════════
# 5. EPSILON TESTS
# ═══════════════════════════════════════════════════════════════════

class TestEpsilon:
    """Kiểm tra ε ảnh hưởng đến ràng buộc cục bộ."""

    def test_eps_reduces_local_requirement(self):
        """
        ε = 0.5, ρ_peak = [[500, 100]], global = [600], n=[[[0],[0]]].
        Cục bộ: vùng 0 ≥ 0.5·500/100 = 2.5 → 3; vùng 1 ≥ 0.5·100/100 = 0.5 → 1.
        Toàn cục: tổng ≥ 600/100 = 6.
        Cục bộ yêu cầu 3+1=4, toàn cục 6 → cần thêm 2 nữa.
        Tối ưu: phân bổ thêm vào vùng rẻ nhất (chi phí đồng nhất → bất kỳ).
        Tổng δ = 6.
        """
        opt = make_1model_2region_1gpu(eps=0.5)
        result = opt.solve([[[0], [0]]], [[500, 100]], [600])
        assert result.is_optimal
        total = result.delta[0][0][0] + result.delta[1][0][0]
        assert total == 6

    def test_eps1_vs_eps05_less_instances_locally(self):
        """
        ε=1.0: vùng 0 cần ≥ 5 (500/100), vùng 1 cần ≥ 1 → tổng ≥ 6.
        ε=0.5: vùng 0 cần ≥ 3 (250/100), vùng 1 cần ≥ 1 → tổng ≥ 6 (toàn cục binds).
        Với ε=1.0, vùng 0 phải có ≥ 5; với ε=0.5, vùng 0 chỉ cần ≥ 3.
        """
        opt1 = make_1model_2region_1gpu(eps=1.0)
        r1 = opt1.solve([[[0], [0]]], [[500, 100]], [600])

        opt05 = make_1model_2region_1gpu(eps=0.5)
        r05 = opt05.solve([[[0], [0]]], [[500, 100]], [600])

        # ε=1: vùng 0 ≥ 5
        assert r1.delta[0][0][0] >= 5
        # ε=0.5: vùng 0 có thể ≤ 5 (tối thiểu 3)
        assert r05.delta[0][0][0] >= 3


# ═══════════════════════════════════════════════════════════════════
# 6. STARTUP COST TESTS
# ═══════════════════════════════════════════════════════════════════

class TestStartupCost:
    """Chi phí khởi động σ chỉ áp dụng khi δ > 0 (thêm máy)."""

    def test_startup_cost_only_on_positive_delta(self):
        """
        α=10, σ=5. n=[[[5],[5]]], ρ_peak=[[200,300]], global=[500], ε=1.
        Vùng 0: cần 2 (bớt 3, δ=-3, chi phí = 10·(-3) = -30, startup = 0)
        Vùng 1: cần 3 (bớt 2, δ=-2, chi phí = 10·(-2) = -20, startup = 0)
        Mục tiêu: -50.
        """
        opt = Optimizer(1, 2, 1, [[100]], [10], [[5]], epsilon=1.0)
        result = opt.solve([[[5], [5]]], [[200, 300]], [500])
        assert result.is_optimal
        assert result.delta == [[[-3]], [[-2]]]
        assert abs(result.objective_value - (-50)) < 1e-6

    def test_high_startup_cost_discourages_adding(self):
        """
        σ rất lớn → optimizer cố gắng dùng instance có sẵn thay vì thêm mới.
        n=[[[0],[3]]], ρ_peak=[[100,100]], global=[200], ε=0.5 (reroute OK).
        Cục bộ: vùng 0 ≥ 0.5, vùng 1 ≥ 0.5 → mỗi vùng ≥ 1 instance.
        Toàn cục: cần 2 instance.
        Vùng 1 có 3: bớt 2 (δ=-2, chi phí = 10·(-2) = -20).
        Vùng 0 cần 1: thêm 1 (δ=+1, chi phí = 10·1 + σ·1).
        Nếu σ=1: mục tiêu = 11-20 = -9.
        Nếu σ=1000: mục tiêu = 1010-20 = 990 (vẫn phải thêm vì ràng buộc cục bộ).
        """
        opt_low = Optimizer(1, 2, 1, [[100]], [10], [[1]], epsilon=0.5)
        r_low = opt_low.solve([[[0], [3]]], [[100, 100]], [200])
        assert r_low.is_optimal

        opt_high = Optimizer(1, 2, 1, [[100]], [10], [[1000]], epsilon=0.5)
        r_high = opt_high.solve([[[0], [3]]], [[100, 100]], [200])
        assert r_high.is_optimal

        # Với σ cao, mục tiêu cao hơn nhưng vẫn phải thêm ít nhất 1 ở vùng 0
        assert r_high.objective_value > r_low.objective_value
        assert r_high.delta[0][0][0] >= 1


# ═══════════════════════════════════════════════════════════════════
# 7. EDGE CASES & ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_single_model_single_region_single_gpu(self):
        """Bài toán nhỏ nhất: 1×1×1."""
        opt = Optimizer(1, 1, 1, [[100]], [10], [[1]], epsilon=1.0)
        result = opt.solve([[[0]]], [[300]], [300])
        assert result.is_optimal
        assert result.delta == [[[3]]]
        # 10·3 + 1·3 = 33
        assert abs(result.objective_value - 33) < 1e-6

    def test_zero_demand(self):
        """Nhu cầu = 0: tối ưu là bớt hết máy."""
        opt = make_1model_2region_1gpu(eps=1.0)
        result = opt.solve([[[5], [3]]], [[0, 0]], [0])
        assert result.is_optimal
        assert result.delta == [[[-5]], [[-3]]]
        # 10·(-5) + 10·(-3) = -80
        assert abs(result.objective_value - (-80)) < 1e-6

    def test_already_at_zero_zero_demand(self):
        """n=0, demand=0: không có gì để làm."""
        opt = make_1model_2region_1gpu(eps=1.0)
        result = opt.solve([[[0], [0]]], [[0, 0]], [0])
        assert result.is_optimal
        assert result.delta == [[[0]], [[0]]]
        assert abs(result.objective_value) < 1e-6

    def test_invalid_epsilon_zero(self):
        with pytest.raises(ValueError, match="ε"):
            Optimizer(1, 1, 1, [[100]], [10], [[1]], epsilon=0)

    def test_invalid_epsilon_negative(self):
        with pytest.raises(ValueError, match="ε"):
            Optimizer(1, 1, 1, [[100]], [10], [[1]], epsilon=-0.5)

    def test_invalid_epsilon_above_one(self):
        with pytest.raises(ValueError, match="ε"):
            Optimizer(1, 1, 1, [[100]], [10], [[1]], epsilon=1.5)

    def test_invalid_model_tps_shape(self):
        with pytest.raises(ValueError, match="model_tps"):
            Optimizer(2, 1, 1, [[100]], [10], [[1], [1]], epsilon=1.0)

    def test_invalid_gpu_cost_shape(self):
        with pytest.raises(ValueError, match="gpu_cost"):
            Optimizer(1, 1, 1, [[100]], [10, 20], [[1]], epsilon=1.0)

    def test_invalid_startup_cost_shape(self):
        with pytest.raises(ValueError, match="startup_cost"):
            Optimizer(1, 1, 1, [[100]], [10], [[1, 2]], epsilon=1.0)

    def test_invalid_current_allocation_models(self):
        """current_allocation có sai số mô hình."""
        opt = make_1model_2region_1gpu()
        with pytest.raises(ValueError, match="mô hình"):
            opt.solve([[[1], [2]], [[3], [4]]], [[100, 100]], [200])

    def test_invalid_region_peak_shape(self):
        opt = make_1model_2region_1gpu()
        with pytest.raises(ValueError, match="mô hình"):
            opt.solve([[[1], [2]]], [[100, 100], [100, 100]], [200])


# ═══════════════════════════════════════════════════════════════════
# 8. OPTIMIZER RESULT DATACLASS
# ═══════════════════════════════════════════════════════════════════

class TestOptimizerResult:

    def test_total_delta(self):
        r = OptimizerResult(delta=[[[2]], [[-3]]], status="Optimal", objective_value=-8)
        assert r.total_delta() == -1

    def test_delta_for_model_region(self):
        r = OptimizerResult(delta=[[[2]], [[-3]]], status="Optimal")
        assert r.delta_for_model_region(0, 0) == [2]
        assert r.delta_for_model_region(0, 1) == [-3]

    def test_is_optimal(self):
        r1 = OptimizerResult(delta=[[[0]]], status="Optimal")
        assert r1.is_optimal
        r2 = OptimizerResult(delta=[[[0]]], status="Infeasible")
        assert not r2.is_optimal


# ═══════════════════════════════════════════════════════════════════
# 9. COMPATIBILITY với MilpLongTermAllocation (long_term_allocation.py)
# ═══════════════════════════════════════════════════════════════════

class TestCompatibility:
    """Kiểm tra rằng Optimizer.get_ilp_allocations cho kết quả
    giống MilpLongTermAllocation.get_ilp_allocations trên cùng đầu vào."""

    def test_matches_legacy_eps1(self):
        """So sánh với kết quả đã biết từ test_ilp.py."""
        opt = Optimizer(1, 2, 1, [[100]], [10], [[1]], epsilon=1.0)
        assert opt.get_ilp_allocations([[[1], [4]]], [[250, 50]], [300]) == [[[2]], [[-3]]]

    def test_matches_legacy_eps05(self):
        opt = Optimizer(1, 2, 1, [[100]], [10], [[1]], epsilon=0.5)
        assert opt.get_ilp_allocations([[[1], [4]]], [[250, 50]], [300]) == [[[1]], [[-3]]]

    def test_matches_legacy_global_bind(self):
        opt = Optimizer(1, 2, 1, [[100]], [10], [[1]], epsilon=0.5)
        result = opt.get_ilp_allocations([[[0], [0]]], [[100, 100]], [450])
        total = sum(r[0][0] for r in result)
        assert total == 5


# ═══════════════════════════════════════════════════════════════════
# 10. STRESS TEST – kích thước lớn hơn
# ═══════════════════════════════════════════════════════════════════

class TestLargerProblem:

    def test_4models_3regions_1gpu(self):
        """
        Tái tạo cấu trúc của SageServe: 4 mô hình, 3 vùng, 1 GPU.
        n hiện tại tất cả = 5, ρ_peak mỗi mô hình mỗi vùng = 400, ε=1, θ=100.
        Cần 4 instance mỗi ô (400/100), tổng cần = 4×3 = 12 < 15 hiện tại.
        Toàn cục cần 1200 = tổng cục bộ.
        Bớt 1 instance mỗi ô → δ = -1 mỗi ô, tổng δ = -12.
        """
        opt = Optimizer(
            models=4, regions=3, gpus=1,
            model_tps=[[100], [100], [100], [100]],
            gpu_cost=[10],
            startup_cost=[[1], [1], [1], [1]],
            epsilon=1.0,
        )
        n = [[[5] for _ in range(3)] for _ in range(4)]
        rp = [[400 for _ in range(3)] for _ in range(4)]
        gp = [1200 for _ in range(4)]
        result = opt.solve(n, rp, gp)
        assert result.is_optimal
        # Mỗi ô bớt 1: δ[j][i] = [-1] cho tất cả
        for j in range(3):
            for i in range(4):
                assert result.delta[j][i] == [-1]

    def test_infeasible_returns_zero_delta(self):
        """
        Nếu bài toán không khả thi (demand > capacity cho phép), trả δ=0.
        Tuy nhiên, ILP luôn khả thi nếu ta cho phép thêm vô hạn (δ không có cận trên).
        Vậy ILP luôn khả thi → test rằng kết quả luôn Optimal.
        """
        opt = make_1model_2region_1gpu(eps=1.0)
        # Demand rất lớn nhưng không giới hạn δ trên → luôn khả thi
        result = opt.solve([[[0], [0]]], [[1e9, 1e9]], [2e9])
        assert result.is_optimal
        # Cần rất nhiều máy
        total = result.delta[0][0][0] + result.delta[1][0][0]
        assert total >= 2e7  # ít nhất 20 triệu instance


# ═══════════════════════════════════════════════════════════════════
# 11. RÀNG BUỘC CỤC BỘ VÀ TOÀN CỤC – kiểm tra riêng biệt
# ═══════════════════════════════════════════════════════════════════

class TestConstraintInteraction:

    def test_local_sufficient_global_insufficient(self):
        """
        ε=0.5: cục bộ rẻ hơn nhưng toàn cục cần nhiều hơn.
        n=[[[1],[1]]], ρ_peak=[[100,100]], global=[500], ε=0.5.
        Cục bộ: mỗi vùng ≥ 0.5·100/100 = 0.5 → 1 (đã có).
        Toàn cục: tổng ≥ 500/100 = 5 (có 2, thiếu 3).
        """
        opt = make_1model_2region_1gpu(eps=0.5)
        result = opt.solve([[[1], [1]]], [[100, 100]], [500])
        assert result.is_optimal
        total = 1 + result.delta[0][0][0] + 1 + result.delta[1][0][0]
        assert total >= 5

    def test_local_insufficient_global_sufficient(self):
        """
        ε=1.0: cục bộ chặt hơn toàn cục.
        n=[[[0],[10]]], ρ_peak=[[300,100]], global=[300], ε=1.0.
        Toàn cục: (0+10)·100=1000≥300 ✓, nhưng cục bộ vùng 0 cần 3.
        → phải thêm 3 ở vùng 0, có thể bớt ở vùng 1.
        """
        opt = make_1model_2region_1gpu(eps=1.0)
        result = opt.solve([[[0], [10]]], [[300, 100]], [300])
        assert result.is_optimal
        # Vùng 0 phải có ≥ 3
        assert result.delta[0][0][0] >= 3
        # Vùng 1 có thể bớt (10 xuống 1)
        assert result.delta[1][0][0] <= 0

    def test_feasibility_check(self):
        """
        Kiểm tra rằng nghiệm thỏa mãn cả hai ràng buộc cục bộ và toàn cục.
        """
        opt = make_1model_2region_1gpu(eps=0.7)
        n_init = [[[2], [3]]]
        rp = [[350, 250]]
        gp = [650]
        result = opt.solve(n_init, rp, gp)
        assert result.is_optimal

        theta = 100
        # Kiểm ràng buộc cục bộ
        for j in range(2):
            cap = (n_init[0][j][0] + result.delta[j][0][0]) * theta
            assert cap >= 0.7 * rp[0][j], f"Vi phạm cục bộ vùng {j}: {cap} < {0.7 * rp[0][j]}"

        # Kiểm ràng buộc toàn cục
        total_cap = sum(
            (n_init[0][j][0] + result.delta[j][0][0]) * theta
            for j in range(2)
        )
        assert total_cap >= gp[0], f"Vi phạm toàn cục: {total_cap} < {gp[0]}"

