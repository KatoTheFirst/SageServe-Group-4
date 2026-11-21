import logging
import pandas as pd
from os import getcwd

from abc import ABC, abstractmethod
import random
from typing import List, Tuple

from simulator import clock, schedule_event, cancel_event, reschedule_event
from request import Request
from region_cluster import RegionCluster
from controller import Controller
from global_arbiter import GlobalArbiter

import utils

REGION_MEMORY_THRESHOLD = 0.7

class GlobalRouter(ABC):
    """
    Router routes Requests to Regions.
    """
    def __init__(self,
                 controller: Controller,
                 overheads, 
                 long_term_scaling,
                 no_reroute):
        self.controller = controller
        self.overheads = overheads
        self.region_clusters = {}
        self.region_routers = {}

        # long term planner
        self.long_term_scaling = long_term_scaling
        self.global_arbiter = None
        self.last_reported_allocation_time = 0
        self.allocation_interval = 600
        self.no_reroute = no_reroute
        
        self.results = {}
        self.reset_results()

        self.last_log_iter = -1
        
    def reset_results(self):
        self.results = {
            'request_id': [],
            'completion_time': [],
            'response_time': [],
            'ttft': [],
            'workload_type': [],
            'utility': [],
            'sla': [],
            'model_type': []
        }

    def add_region(self, region: RegionCluster):
        self.region_clusters[region.region_id] = region.region_cluster
        self.region_routers[region.region_id] = region.region_router

    def add_global_arbiter(self, global_arbiter: GlobalArbiter):
        self.global_arbiter = global_arbiter
        if self.long_term_scaling:
            self.global_arbiter.add_region_routers(self.region_routers)
            self.global_arbiter.add_region_clusters(self.region_clusters)
            self.global_arbiter.load_predicted_traces()
            self.global_arbiter.start_with_8_each()

    def run(self):
        if not self.long_term_scaling:
            return
        arbiter = self.global_arbiter
        if arbiter.scaling_interval_reached():
            arbiter.scale()
        interval = arbiter.long_term_scaling_interval
        if clock() + interval < arbiter.max_time:
            schedule_event(interval, self.run)

    @abstractmethod
    def route(self, *args):
        """
        Main routing logic
        """
        raise NotImplementedError

    def request_arrival(self, request: Request, *, region_id=None):
        request.arrive_at_global_router()
        self.route_request(request, region_id=region_id)

    def request_completion(self, request: Request):
        request.complete_at_global_router()
        self.results['request_id'].append(request.request_id)
        self.results['completion_time'].append(request.metrics.global_router_completion_timestamp)
        self.results['response_time'].append(request.metrics.global_router_response_time)
        self.results['ttft'].append(request.metrics.TTFT)
        self.results['workload_type'].append(request.workload_type)
        self.results['utility'].append(request.utility)
        self.results['sla'].append(request.sla)
        self.results['model_type'].append(request.model_type)


    def route_request(self, request: Request, *, region_id=None):
        self.route(request, region_id=region_id)

    def save_results(self):
        utils.save_dict_as_csv(self.results, f"global_router/{self.last_log_iter + 1}.csv")
        if self.long_term_scaling:
            self.global_arbiter.save_results()
    
    def save_results_intermediate(self, write_itr):
        utils.save_dict_as_csv(self.results, f"global_router/{write_itr}.csv")
        self.last_log_iter = write_itr
        if self.long_term_scaling:      # simulator không gọi save_results() cuối bài -> ghi log global arbiter mỗi đợt
            self.global_arbiter.save_results()
        self.reset_results()

def inter_region_delay():
    """§7.1: chuyển request sang vùng khác – 90% trễ ≤ 500 ms, dưới 2% tới 2,5 s (dạng phân phối là giả định)."""
    u = random.random()
    if u < 0.90:
        return random.uniform(0.0, 0.5)
    if u < 0.98:
        return random.uniform(0.5, 1.0)
    return random.uniform(1.0, 2.5)


class ProbabilisticRouter(GlobalRouter):
    """
    Forwards request to the appropriate scheduler without any overheads.
    """
    def _candidate_regions(self, request: Request):
        for choice in request.region_priority:
            region_id = int(choice)
            router = self.region_routers.get(region_id)
            if router is not None and request.model_type in router.model_endpoint_routers:
                yield region_id

    def _select_region(self, request: Request) -> int:
        utilizations = {}
        for region_id in self._candidate_regions(request):
            cluster = self.region_clusters[region_id]
            capacity = cluster.get_max_memory(request.model_type)
            if capacity <= 0:
                continue
            utilization = cluster.get_memory(request.model_type) / capacity
            if utilization < REGION_MEMORY_THRESHOLD:
                return region_id
            utilizations[region_id] = utilization
        if utilizations:
            return min(utilizations, key=utilizations.get)
        raise ValueError(f"No preferred region can serve {request.model_type}")

    def _select_first_priority_region(self, request: Request) -> int:
        for region_id in self._candidate_regions(request):
            if self.region_clusters[region_id].get_max_memory(request.model_type) > 0:
                return region_id
        raise ValueError(f"No preferred region can serve {request.model_type}")

    def route(self, request: Request, *, region_id=None):
        if self.long_term_scaling and self.global_arbiter.scaling_interval_reached():
            self.global_arbiter.scale()
        if self.long_term_scaling and request.is_interactive:
            origin = int(request.region_priority[0])
            origin_router = self.region_routers.get(origin)
            if origin_router is not None and request.model_type in origin_router.model_endpoint_routers:
                self.global_arbiter.observe(origin, request.model_type, request.prompt_size)
                origin_router.model_endpoint_routers[request.model_type].record_iw_tokens(request.prompt_size)
        if clock() > self.last_reported_allocation_time + self.allocation_interval:
            self.last_reported_allocation_time = clock()
        if region_id is None:
            if self.long_term_scaling and self.no_reroute:
                region_id = self._select_first_priority_region(request)
            else:
                region_id = self._select_region(request)
        router = self.region_routers[region_id]
        f = lambda router=router,request=request: \
            router.request_arrival(request)
        schedule_event(self.overheads.routing_delay, f)
