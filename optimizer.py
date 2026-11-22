"""
Optimizer v0 – ILP tối ưu phân bổ dài hạn của SageServe (§5).

Bài toán (n + δ) với ràng buộc cục bộ (từng vùng) và toàn cục:

  Biến:
    n[i][j][k]  – số instance hiện tại mô hình i ở vùng j trên GPU loại k (cho trước)
    δ[i][j][k]  – số instance thay đổi (nguyên, có thể âm; δ ≥ −n)

  Ràng buộc cục bộ (từng vùng):
    ∀ i,j:  Σ_k (n + δ)[i][j][k] · θ[i][k]  ≥  ε · ρ_peak[i][j]

  Ràng buộc toàn cục:
    ∀ i:    Σ_j Σ_k (n + δ)[i][j][k] · θ[i][k]  ≥  peak_global[i]

  Hàm mục tiêu:
    min  γ + μ
    γ = Σ α[k] · δ[i][j][k]                   (chi phí VM)
    μ = Σ σ[i][k] · max(δ[i][j][k], 0)        (chi phí khởi động mô hình)

Module này gói lại MilpLongTermAllocation với:
  - validate đầu vào rõ ràng
  - trả kết quả dạng OptimizerResult (dataclass)
  - sẵn sàng cho unit test tính tay
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional

from pulp import LpMinimize, LpProblem, LpSolutionOptimal, LpStatus, LpVariable, PULP_CBC_CMD, lpSum

# D37: dừng khi khoảng cách tương đối ≤ 0,01%. D37b: lưới an toàn 300 s; hết giờ thì dùng nghiệm tốt nhất và ghi gap vào log.
ILP_GAP_REL = 1e-4
ILP_TIME_LIMIT = 300


@dataclass
class OptimizerResult:
    """Kết quả của ILP optimizer."""

    # δ[j][i][k] – vùng trước, mô hình sau, GPU cuối (format simulator dùng)
    delta: List[List[List[int]]]

    # Trạng thái solver (string)
    status: str

    # Giá trị hàm mục tiêu (None nếu không có nghiệm)
    objective_value: Optional[float] = None

    @property
    def is_optimal(self) -> bool:
        return self.status == "Optimal"

    def total_delta(self) -> int:
        """Tổng δ trên tất cả (mô hình, vùng, GPU)."""
        return sum(
            self.delta[j][i][k]
            for j in range(len(self.delta))
            for i in range(len(self.delta[0]))
            for k in range(len(self.delta[0][0]))
        )

    def delta_for_model_region(self, model_idx: int, region_idx: int) -> List[int]:
        """δ của 1 cặp (mô hình, vùng) trên mỗi loại GPU."""
        return self.delta[region_idx][model_idx]


class Optimizer:
    """
    ILP optimizer v0 cho bài toán phân bổ dài hạn SageServe §5.

    Parameters
    ----------
    models : int
        Số mô hình.
    regions : int
        Số vùng (region).
    gpus : int
        Số loại GPU.
    model_tps : list[list[float]]
        θ[i][k] – năng lực (tokens per minute) 1 instance mô hình i trên GPU k.
    gpu_cost : list[float]
        α[k] – chi phí VM mỗi đơn vị thời gian cho GPU loại k.
    startup_cost : list[list[float]]
        σ[i][k] – chi phí khởi động mô hình i trên GPU k.
    epsilon : float
        0 < ε ≤ 1, phần dung lượng tối thiểu mỗi vùng phải đáp ứng (phần còn lại
        có thể chuyển sang vùng khác).
    instance_bounds : dict, optional
        (chỉ số mô hình, chỉ số vùng) → (sàn, trần) trên tổng instance qua mọi GPU.
    """

    def __init__(
        self,
        models: int,
        regions: int,
        gpus: int,
        model_tps: List[List[float]],
        gpu_cost: List[float],
        startup_cost: List[List[float]],
        epsilon: float = 1.0,
        instance_bounds: dict[tuple[int, int], tuple[int, int | None]] | None = None,
    ) -> None:
        # ── Validate ──────────────────────────────────────────────
        if not (0 < epsilon <= 1):
            raise ValueError(f"§5: 0 < ε ≤ 1, nhận được ε = {epsilon}")
        if models <= 0 or regions <= 0 or gpus <= 0:
            raise ValueError("models, regions, gpus phải > 0")
        if len(model_tps) != models or any(len(r) != gpus for r in model_tps):
            raise ValueError(f"model_tps phải có kích thước [{models}][{gpus}]")
        if len(gpu_cost) != gpus:
            raise ValueError(f"gpu_cost phải có kích thước [{gpus}]")
        if len(startup_cost) != models or any(len(r) != gpus for r in startup_cost):
            raise ValueError(f"startup_cost phải có kích thước [{models}][{gpus}]")

        self.models = models
        self.regions = regions
        self.gpus = gpus
        self.model_tps = model_tps
        self.gpu_cost = gpu_cost
        self.startup_cost = startup_cost
        self.epsilon = epsilon
        self.instance_bounds = instance_bounds or {}

    # ── public API ────────────────────────────────────────────────

    def solve(
        self,
        current_allocation: List[List[List[int]]],
        region_peak: List[List[float]],
        global_peak: List[float],
    ) -> OptimizerResult:
        """
        Giải ILP.

        Parameters
        ----------
        current_allocation : n[i][j][k]
            Mô hình × Vùng × GPU.
        region_peak : ρ_peak[i][j]
            Đỉnh dự báo mô hình i tại vùng j (TPM).
        global_peak : peak_global[i]
            Đỉnh dự báo toàn cục mô hình i (TPM).

        Returns
        -------
        OptimizerResult
            delta[j][i][k] – vùng trước, mô hình sau (format simulator).
        """
        self._validate_inputs(current_allocation, region_peak, global_peak)

        prob = LpProblem("sageserve_ilp_v0", LpMinimize)

        idx = [
            (i, j, k)
            for i in range(self.models)
            for j in range(self.regions)
            for k in range(self.gpus)
        ]

        n = {(i, j, k): current_allocation[i][j][k] for i, j, k in idx}
        delta = LpVariable.dicts("d", idx, cat="Integer")
        # pos[x] = max(δ[x], 0) — biến phụ tuyến tính hoá chi phí khởi động
        pos = LpVariable.dicts("d_pos", idx, lowBound=0, cat="Integer")

        # ── Ràng buộc ────────────────────────────────────────────
        for x in idx:
            # δ ≥ −n  (không thể bớt nhiều hơn hiện có)
            prob += delta[x] >= -n[x], f"lb_{x}"
            # pos ≥ δ  (cùng với lowBound=0, khi tối ưu pos = max(δ, 0))
            prob += pos[x] >= delta[x], f"pos_{x}"

        def capacity(i: int, j: int):
            """Dung lượng mô hình i tại vùng j sau khi áp δ."""
            return lpSum(
                (n[(i, j, k)] + delta[(i, j, k)]) * self.model_tps[i][k]
                for k in range(self.gpus)
            )

        # Ràng buộc cục bộ (từng vùng)
        for i in range(self.models):
            for j in range(self.regions):
                prob += (
                    capacity(i, j) >= self.epsilon * region_peak[i][j]
                ), f"local_{i}_{j}"

        for (i, j), (minimum, maximum) in self.instance_bounds.items():
            total = lpSum(n[(i, j, k)] + delta[(i, j, k)] for k in range(self.gpus))
            prob += total >= minimum, f"min_instances_{i}_{j}"
            if maximum is not None:
                prob += total <= maximum, f"max_instances_{i}_{j}"

        # Ràng buộc toàn cục
        for i in range(self.models):
            prob += (
                lpSum(capacity(i, j) for j in range(self.regions))
                >= global_peak[i]
            ), f"global_{i}"

        # ── Hàm mục tiêu ─────────────────────────────────────────
        # γ = Σ α[k] · δ  (chi phí VM ròng: thêm tốn, bớt tiết kiệm)
        # μ = Σ σ[i][k] · max(δ, 0)  (chi phí khởi động, chỉ khi thêm)
        prob += lpSum(
            self.gpu_cost[k] * delta[(i, j, k)]
            + self.startup_cost[i][k] * pos[(i, j, k)]
            for i, j, k in idx
        )

        # ── Giải ──────────────────────────────────────────────────
        fd, log_path = tempfile.mkstemp(suffix=".cbc.log")
        os.close(fd)
        try:
            status = prob.solve(PULP_CBC_CMD(msg=0, gapRel=ILP_GAP_REL, timeLimit=ILP_TIME_LIMIT, logPath=log_path))
            if LpStatus.get(status) == "Optimal" and prob.sol_status != LpSolutionOptimal:
                self._log_time_limit(prob, log_path)
        finally:
            os.remove(log_path)
        status_str = LpStatus.get(status, str(status))

        if status_str != "Optimal":
            logging.warning(
                "ILP không có nghiệm tối ưu (trạng thái %s): giữ cấu hình hiện tại",
                status_str,
            )
            zero_delta = [
                [[0] * self.gpus for _ in range(self.models)]
                for _ in range(self.regions)
            ]
            return OptimizerResult(delta=zero_delta, status=status_str)

        result_delta = [
            [
                [round(delta[(i, j, k)].value()) for k in range(self.gpus)]
                for i in range(self.models)
            ]
            for j in range(self.regions)
        ]

        return OptimizerResult(
            delta=result_delta,
            status="Optimal",
            objective_value=prob.objective.value(),
        )

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def _log_time_limit(prob, log_path):
        """D37b: CBC dừng trước khi chứng minh gapRel (thường do hết ILP_TIME_LIMIT): ghi mục tiêu, cận dưới, gap."""
        with open(log_path, encoding="utf-8", errors="replace") as f:      # đóng ngay để os.remove trong solve() không bị khóa trên Windows
            text = f.read()
        result = re.search(r"Result - (.*)", text)
        bound = re.search(r"Lower bound:\s*(\S+)", text)
        obj = prob.objective.value()
        gap = None
        if bound and obj is not None:
            lb = float(bound.group(1))
            gap = abs(obj - lb) / max(abs(lb), 1e-9)
        logging.warning(
            "ILP dừng trước khi đạt gapRel (%s; giới hạn %s s): dùng nghiệm tốt nhất, mục tiêu %s, cận dưới %s, gap %s",
            result.group(1).strip() if result else "?", ILP_TIME_LIMIT, obj,
            bound.group(1) if bound else "?", f"{gap:.4%}" if gap is not None else "?",
        )

    def _validate_inputs(self, ca, rp, gp):
        if len(ca) != self.models:
            raise ValueError(f"current_allocation cần {self.models} mô hình, nhận {len(ca)}")
        for i, row in enumerate(ca):
            if len(row) != self.regions:
                raise ValueError(f"current_allocation[{i}] cần {self.regions} vùng, nhận {len(row)}")
            for j, cell in enumerate(row):
                if len(cell) != self.gpus:
                    raise ValueError(
                        f"current_allocation[{i}][{j}] cần {self.gpus} GPU, nhận {len(cell)}"
                    )
        if len(rp) != self.models:
            raise ValueError(f"region_peak cần {self.models} mô hình")
        for i, row in enumerate(rp):
            if len(row) != self.regions:
                raise ValueError(f"region_peak[{i}] cần {self.regions} vùng")
        if len(gp) != self.models:
            raise ValueError(f"global_peak cần {self.models} mô hình")

    # ── Tiện ích cho global_arbiter ───────────────────────────────

    def get_ilp_allocations(
        self,
        current_allocation: List[List[List[int]]],
        region_peak: List[List[float]],
        global_peak: List[float],
    ) -> List[List[List[int]]]:
        """API tương thích với MilpLongTermAllocation.get_ilp_allocations."""
        result = self.solve(current_allocation, region_peak, global_peak)
        return result.delta

