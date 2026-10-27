import logging

from abc import ABC
from typing import List, Tuple
import numpy as np
import pandas as pd
from collections import defaultdict
from hydra.utils import to_absolute_path

from application import Application
from model import ModelParallelism
import application_repo
from simulator import clock, schedule_event, cancel_event, reschedule_event
import start_state_repo
import utils
from long_term_allocation import MilpLongTermAllocation
from generate_causal_arima_forecasts import WINDOW, HORIZON, fit_forecast


class GlobalArbiter(ABC):
    """
    Global Arbiter allocates Models to Regions from the global router.
    """
    def __init__(self,
                 long_term_scaling_interval,
                 max_time):
        self.regions = 3
        self.models = 2
        self.model_to_idx_mapping = {"A": 0, "B": 1, "C": 2, "D": 3}
        self.model_list = ["A", "B", "C", "D"]

        self.long_term_scaling_interval = long_term_scaling_interval
        self.last_updated_time = -1e9
        self.last_reported_allocation_time = 0
        self.allocation_interval = 600

        self.max_time = max_time

    def scaling_interval_reached(self) -> bool:
        return (clock() >= self.last_updated_time + self.long_term_scaling_interval)
    
NIW_BUFFER = 0.1    # β (§6.3): 10% tải NIW của giờ trước


class MilpGlobalArbiter(GlobalArbiter):
    """MILP based global router"""
    def __init__(self,
                 arima_traces,
                 long_term_scaling_interval,
                 post_processing_strategy,
                 max_time,
                 epsilon=1.0,
                 gpu_cost=10,
                 startup_time=600,
                 theta_file="data/theta_tps.csv",
                 forecast_mode="offline"):
        super().__init__(long_term_scaling_interval, max_time)
        # Load Predictor (§6.3): "offline" = dự báo nhân quả đọc từ file; "online" = mỗi giờ huấn luyện ARIMA-60 trên
        # TPM quan sát được trong simulator (giờ đầu chưa có lịch sử -> dùng file)
        assert forecast_mode in ("offline", "online"), forecast_mode
        self.forecast_mode = forecast_mode
        self.observed = defaultdict(lambda: defaultdict(float))     # (vùng, mô hình) -> phút -> token IW
        self.forecast_log = []
        self.epsilon = epsilon
        self.gpu_cost = gpu_cost
        self.startup_time = startup_time
        self.theta_file = to_absolute_path(theta_file)
        self.arima_traces = to_absolute_path(arima_traces)   # hydra đổi cwd sang thư mục kết quả
        self.forecast_df = {}
        self.dev_df = {}
        self.region_clusters = None
        self.region_routers = None
        self.milp_allocator = None
        self.post_processing_strategy = post_processing_strategy
        self.num_instances_log = None
    
    def add_region_routers(self, region_routers) -> None:
        self.region_routers = region_routers
    
    def add_region_clusters(self, region_clusters) -> None:
        self.region_clusters = region_clusters

    def save_results(self):
        utils.save_dict_as_csv(self.num_instances_log, "global_ariber_logs.csv")
        # log dự báo vs thực tế theo giờ (thực tế lấy từ token IW quan sát được trong giờ đó)
        rows = []
        for r in self.forecast_log:
            obs = self.observed[(r["region"], r["model"])]
            actual = np.array([obs.get(m, 0.0) for m in range(r["hour"] * 60, (r["hour"] + 1) * 60)])
            rows.append({**r, "actual_peak_tpm": actual.max(), "actual_mean_tpm": actual.mean()})
        if rows:
            utils.save_dict_as_csv({k: [x[k] for x in rows] for k in rows[0]}, "forecast_log.csv")

    def observe(self, region_id, model_name, tokens):
        """Load Predictor: cộng token đầu vào của request IW theo phút (gọi từ global router)."""
        self.observed[(region_id, model_name)][int(clock() // 60)] += tokens

    def predict_hour(self, region_id, model_name, cur_time):
        """Dự báo TPM 60 phút tới (DataFrame Time, Predicted)."""
        # canh theo phút tròn: ILP chạy ở request đầu tiên sau mốc giờ (vd. 3600,3 s); lọc theo cur_time sẽ bỏ phút đầu
        # của giờ này và lấy nhầm phút đầu giờ sau (dự báo theo phút, mỗi giờ một lần huấn luyện)
        start = int(cur_time // 60)
        df = self.forecast_df[region_id][model_name]
        df = df[(df["Time"] >= 60 * start) & (df["Time"] < 60 * start + 3600)]
        if self.forecast_mode == "online" and cur_time >= WINDOW * 60:
            obs = self.observed[(region_id, model_name)]
            train = np.array([obs.get(m, 0.0) for m in range(start - WINDOW, start)])
            pred = fit_forecast(train)[0]
            df = pd.DataFrame({"Time": [60 * (start + m) for m in range(HORIZON)], "Predicted": pred})
            arbiter = self.region_clusters[region_id].arbiter
            if hasattr(arbiter, "set_arima_forecast"):      # LT-UA so tải thực với dự báo vừa cập nhật
                arbiter.set_arima_forecast(model_name, df)
        return df
    
    def load_predicted_traces(self) -> None:
        self.regions = len(self.region_clusters)
        unique_models = []
        for region_id in self.region_clusters.keys():
            for model_name in self.region_routers[region_id].model_endpoint_routers:
                unique_models.append(model_name)
                filepath = f"{self.arima_traces}/final_{model_name}_prod_1minute_region{region_id}_arima.csv"
                dev_file = f"{self.arima_traces}/final_{model_name}_dev_region{region_id}_exact.csv"
                print(filepath)
                print(dev_file)
                if region_id not in self.forecast_df:
                    self.forecast_df[region_id] = {}
                if region_id not in self.dev_df:
                    self.dev_df[region_id] = {}
                self.forecast_df[region_id][model_name] = pd.read_csv(filepath)
                self.dev_df[region_id][model_name] = pd.read_csv(dev_file)
                print(region_id, model_name, len(self.forecast_df[region_id][model_name]))
                print(region_id, model_name, len(self.dev_df[region_id][model_name]))
                arbiter = self.region_clusters[region_id].arbiter
                if hasattr(arbiter, "set_arima_forecast"):      # LT-UA
                    arbiter.set_arima_forecast(model_name, self.forecast_df[region_id][model_name])

        unique_models = sorted(list(set(unique_models)))
        # unique_models = ["A", "B", "C", "D"]
        self.models = len(unique_models)
        self.model_list = unique_models
        for i in range(self.models):
            self.model_to_idx_mapping[unique_models[i]] = i
        # θ (§5): TPS 1 instance gánh ở ngưỡng bộ nhớ 70%, đo bằng analyze_capacity.py; dự báo tính theo TPM nên ×60
        theta = pd.read_csv(self.theta_file).set_index("model").theta_tps
        self.milp_allocator = MilpLongTermAllocation(
            models=self.models,
            regions=self.regions,
            gpus=1,
            model_tps=[[60 * theta[m.removesuffix("-p").removesuffix("-d")]] for m in unique_models],
            gpu_cost=[self.gpu_cost],
            # σ: chi phí khởi động = α x thời gian khởi động (§5), α tính theo giờ
            startup_cost=[[self.gpu_cost * self.startup_time / 3600] for _ in range(self.models)],
            epsilon=self.epsilon,
        )
        self.num_instances_log = {f"region_{i}_model_{j}": [] for i in range(self.regions) for j in range(self.models)}
        self.num_instances_log["time"] = []
    def current_allocations(self) -> List[List[List[int]]]:
        ca = {}
        for region_id, region_router in self.region_routers.items():
            cur_region = [[0] for _ in range(self.models)]
            for model_name in region_router.model_endpoint_routers.keys():
                # tính cả instance đang lấy lại spot / khởi động (như arbiter.size), nếu không ILP giao thêm máy trùng
                val = sum(len(app.instances) + app.pending_instances
                          for app in region_router.model_endpoint_routers[model_name].applications)
                cur_region[self.model_to_idx_mapping[model_name]][0] += val
            for model_name in region_router.model_endpoint_routers.keys(): 
                self.num_instances_log[f"region_{region_id}_model_{self.model_to_idx_mapping[model_name]}"].append(cur_region[self.model_to_idx_mapping[model_name]][0])
            ca[region_id] = cur_region
            if ca[region_id] == None:
                ca[region_id] = 0
        self.num_instances_log["time"].append(clock())
        return [ca[k] for k in sorted(ca.keys())]
    
    def start_with_8_each(self) -> None:
        ca = self.current_allocations()
        actions = []
        for i in range(self.regions):
            for j in range(self.models):
                for k in range(1):
                    if ca[i][j][k] <= 8:
                        continue
                    while ca[i][j][k] > 8:
                        actions.append((False, 0, i, j, k))
                        ca[i][j][k] -= 1
        self.schedul_scaling_events(actions)
        logging.info(f"Start state: {self.current_allocations()}")

    def get_ilp_forecast(self, path) -> List[List[List[int]]]:
        cur_time = clock()
        # get current allocation
        current_allocation: List[List[List[int]]] = self.current_allocations()
        current_allocation_transposed = [[[0] for _ in range(self.regions)] for __ in range(self.models)]
        for i in range(self.models):
            for j in range(self.regions):
                for k in range(1):
                    current_allocation_transposed[i][j][k] = current_allocation[j][i][k]
        current_allocation = current_allocation_transposed
        
        # §6.3: đỉnh dự báo ARIMA (TPM) trong cả giờ tới + β = 10% tải NIW nhận được trong giờ trước
        region_peak = [[0.0] * self.regions for _ in range(self.models)]
        series = [[] for _ in range(self.models)]
        for region_id, region_router in self.region_routers.items():
            for model_name in region_router.model_endpoint_routers.keys():
                i = self.model_to_idx_mapping[model_name]
                df = self.predict_hour(region_id, model_name, cur_time)
                self.forecast_log.append({"hour": int(cur_time // 3600), "region": region_id, "model": model_name,
                                          "mode": self.forecast_mode, "pred_peak_tpm": df["Predicted"].max() if len(df) else 0,
                                          "pred_mean_tpm": df["Predicted"].mean() if len(df) else 0})
                dev = self.dev_df[region_id][model_name]
                dev = dev[(dev["arrival_timestamp"] >= cur_time - 3600) & (dev["arrival_timestamp"] < cur_time)]
                beta = NIW_BUFFER * dev["prompt_size"].sum() / 60
                region_peak[i][region_id] = (df["Predicted"].max() if len(df) else 0) + beta
                series[i].append(df.set_index("Time")["Predicted"] + beta)
        global_peak = [pd.concat(s_, axis=1).fillna(0).sum(axis=1).max() if s_ else 0 for s_ in series]
        logging.info(f"ILP region peak (TPM): {region_peak}, global peak: {global_peak}")
        return self.milp_allocator.get_ilp_allocations(current_allocation, region_peak, [float(g) for g in global_peak])

    def post_process_ilp(self, ilp_forecast: List[List[List[int]]]) -> List[Tuple[bool, int, int, int, int]]: 
        # (start action?, action time, region, model, gpu)
        actions = []
        indices = [(i, j, k) for i in range(self.regions) for j in range(self.models) for k in range(1)]
        if self.post_processing_strategy == "immediate":
            for idx in indices:
                if ilp_forecast[idx[0]][idx[1]][idx[2]] < 0:
                    for _ in range(-ilp_forecast[idx[0]][idx[1]][idx[2]]):
                        actions.append((False, 0, idx[0], idx[1], idx[2]))
            for idx in indices:
                if ilp_forecast[idx[0]][idx[1]][idx[2]] > 0:
                    for _ in range(ilp_forecast[idx[0]][idx[1]][idx[2]]):
                        actions.append((True, 0, idx[0], idx[1], idx[2]))
        elif self.post_processing_strategy == "evenly_distributed":
            """we should do the actions spread out even in the time period"""
            raise NotImplementedError(f"ILP post processing strategy {self.post_processing_strategy} not implemented")
        else:
            raise NotImplementedError(f"ILP post processing strategy {self.post_processing_strategy} not implemented")
        return actions

    def schedul_scaling_events(self, changes: List[Tuple[bool, int, int, int, int]]) -> None:
        for e in changes:
            action, delay, region, model, gpu = e
            if clock() + delay >= self.max_time:
                continue
            if action:
                f = lambda self=self, region=region, model=model: self.region_clusters[region].arbiter.force_scale_up(self.region_routers[region].model_endpoint_routers[self.model_list[model]])
                schedule_event(delay, f)
            else:
                f = lambda self=self, region=region, model=model: self.region_clusters[region].arbiter.force_scale_down(self.region_routers[region].model_endpoint_routers[self.model_list[model]])
                schedule_event(delay, f)

    def scale(self) -> None:
        ilp_forecast: List[List[List[int]]] = self.get_ilp_forecast(self.arima_traces)
        ilp_changes = self.post_process_ilp(ilp_forecast)
        logging.info(f"Current allocation at time {clock()}: {self.current_allocations()}")
        logging.info(f"ILP forecast at time {clock()}: {ilp_forecast}")
        for region_cluster in self.region_clusters.values():
            region_cluster.arbiter.reset_changes()
        self.schedul_scaling_events(ilp_changes)
        self.last_updated_time = clock()
