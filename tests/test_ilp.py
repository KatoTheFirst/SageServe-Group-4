"""F4 (§5): ILP với ràng buộc từng vùng (ε) và toàn cục, tính tay."""
from long_term_allocation import MilpLongTermAllocation


def make(eps):
    return MilpLongTermAllocation(1, 2, 1, model_tps=[[100]], gpu_cost=[10], startup_cost=[[1]], epsilon=eps)


def test_per_region_eps1():
    assert make(1.0).get_ilp_allocations([[[1], [4]]], [[250, 50]], [300]) == [[[2]], [[-3]]]


def test_eps_allows_reroute():
    assert make(0.5).get_ilp_allocations([[[1], [4]]], [[250, 50]], [300]) == [[[1]], [[-3]]]


def test_global_constraint_binds():
    assert sum(r[0][0] for r in make(0.5).get_ilp_allocations([[[0], [0]]], [[100, 100]], [450])) == 5
