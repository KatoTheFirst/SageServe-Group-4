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
        pass

    @abstractmethod
    def route(self, *args):
        """
        Main routing logic
        """
        raise NotImplementedError

    def request_arrival(self, request: Request):
        request.arrive_at_global_router()
        self.route_request(request)

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


    def route_request(self, request: Request):
        self.route(request)

    def save_results(self):
        utils.save_dict_as_csv(self.results, f"global_router/{self.last_log_iter + 1}.csv")
        if self.long_term_scaling:
            self.global_arbiter.save_results()
    
    def save_results_intermediate(self, write_itr):
        utils.save_dict_as_csv(self.results, f"global_router/{write_itr}.csv")
        self.last_log_iter = write_itr
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
    def _select_region(self, request: Request) -> int:
        # TODO: revisit global routing logic
        region_priority = request.region_priority
        assert len(region_priority) == 3, "Request has invalid region priority"
        region_priority = [c for c in region_priority if int(c) in self.region_routers]  # bỏ vùng không có trong cấu hình (vd. 1 vùng)
        for choice in region_priority:
            if request.model_type in self.region_routers[int(choice)].model_endpoint_routers and \
                self.region_clusters[int(choice)].get_memory(request.model_type) / self.region_clusters[int(choice)].get_max_memory(request.model_type) < 0.7:
                return choice
        return min(region_priority, key=lambda x: self.region_clusters[int(x)].get_memory(request.model_type) / self.region_clusters[int(x)].get_max_memory(request.model_type))
        raise ValueError("Request model type not found in any region")

    def _select_first_priority_region(self, request) -> int:
        region_priority = request.region_priority
        assert len(region_priority) == 3, "Request has invalid region priority"
        region_priority = [c for c in region_priority if int(c) in self.region_routers]  # bỏ vùng không có trong cấu hình (vd. 1 vùng)
        for choice in region_priority:
            if request.model_type in self.region_routers[int(choice)].model_endpoint_routers:
                return choice
        return min(region_priority, key=lambda x: self.region_clusters[int(x)].get_memory(request.model_type) / self.region_clusters[int(x)].get_max_memory(request.model_type))
        
    def route(self, request: Request):
        if self.long_term_scaling and self.global_arbiter.scaling_interval_reached():
            self.global_arbiter.scale()
        if clock() > self.last_reported_allocation_time + self.allocation_interval:
            self.last_reported_allocation_time = clock()
        if self.long_term_scaling and self.no_reroute:
            router = self.region_routers[int(self._select_first_priority_region(request))]
        else:
            router = self.region_routers[int(self._select_region(request))]
        f = lambda router=router,request=request: \
            router.request_arrival(request)
        schedule_event(self.overheads.routing_delay, f)
