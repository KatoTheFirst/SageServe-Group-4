import logging

from abc import ABC

from application import Application
from model import ModelParallelism
from model_endpoint_router import MAX_DEPLOYMENT_INSTANCES, MIN_DEPLOYMENT_INSTANCES
import application_repo
from simulator import clock
import start_state_repo
import utils

# Ngưỡng co giãn theo bộ nhớ hiệu dụng (bài báo §4, §7.1): > 70% thêm instance, < 30% trả về spot.
SCALE_UP_THRESHOLD = 0.7
SCALE_DOWN_THRESHOLD = 0.3

def size(app):
    """Số instance của deployment kể cả instance đang lấy lại spot / khởi động (lấy lại mất ~1–5 phút, khởi động 10 phút)."""
    return len(app.instances) + app.pending_instances


class Arbiter(ABC):
    """
    Arbiter allocates Processors to Application Allocators.
    It can be used to support application autoscaling.
    """
    def __init__(self,
                 cluster,
                 overheads):
        self.cluster = cluster
        self.overheads = overheads
        self.servers = cluster.servers
        self.applications = []
        self.allocators = {}
        self.results = {
            "timestamp":[],
            "model":[],
            "prod":[],
            "spot":[],
            "memory_util":[]
        }
        self.last_log_iter = -1
        self.next_scale_time = {}
        self.changes = {}

    def add_application(self, application):
        self.applications.append(application)
        self.allocators[application.application_id] = application.allocator
    
    def reset_changes(self):
        for model_endpoint in self.changes.keys():
            self.changes[model_endpoint] = 0


    def save_results_intermediate(self, write_itr): 
        utils.save_dict_as_csv(self.results, f"arbiters/{self.cluster.region.region_name}/{write_itr}.csv")
        self.last_log_iter = write_itr
        self.results = {
            "timestamp":[],
            "model":[],
            "prod":[],
            "spot":[],
            "memory_util": []
        }

    def save_results(self):
        utils.save_dict_as_csv(self.results, f"arbiters/{self.cluster.region.region_name}/{self.last_log_iter + 1}.csv")

    def run(self):
        pass

    def allocate(self, processors, application):
        """
        Allocates processors to the application.
        """
        pass

    def deallocate(self, processors, application):
        """
        Deallocates processors from the application.
        """
        pass

    def scale(self, model_endpoint):
        """
        Scales the application based on memory utilisation.
        """
        pass


class NoOpArbiter(Arbiter):
    """
    No-op Arbiter.
    """
    pass


class BasicArbiter(Arbiter):
    """Reactive scaling and the allocation operations shared by SageServe and Chiron."""

    @staticmethod
    def memory_utilization(model_endpoint):
        capacity = model_endpoint.get_max_memory()
        return model_endpoint.get_memory() / capacity if capacity > 0 else None

    def log_state(self, model_endpoint, utilization):
        # Giữ schema log trạng thái để đọc được bằng các script phân tích cũ.
        for endpoint in self.cluster.region.model_endpoint_routers:
            self.results["timestamp"].append(clock())
            self.results["model"].append(endpoint.model_name)
            self.results["prod"].append(str(sum(len(app.instances) for app in endpoint.applications)))
            self.results["spot"].append(str(self.cluster.get_spot_instance_count(endpoint.model_name)))
            memory = utilization if endpoint is model_endpoint else self.memory_utilization(endpoint)
            self.results["memory_util"].append(memory)

    def _record_scale(self, model_endpoint, before, trigger, action, wait):
        after = model_endpoint.instance_counts()
        if sum(after) == sum(before):
            return False
        now = clock()
        if trigger == "request":
            self.next_scale_time[model_endpoint.model_name] = now + wait
        logging.info(
            "SCALE_EVENT,%s,%s,%s,%s,%s,%s,%s,%s,%s",
            now, self.cluster.region.region_name, model_endpoint.model_name, trigger, action,
            *before, *after,
        )
        return True

    def _scale_up(self, model_endpoint, trigger):
        apps = model_endpoint.applications
        before = model_endpoint.instance_counts()
        if not apps or model_endpoint.scaling_level < 1:
            return False
        if model_endpoint.max_instances is not None and sum(before) >= model_endpoint.max_instances:
            return False

        last = apps[-1]
        split = size(last) == MAX_DEPLOYMENT_INSTANCES
        if split:
            # Phải giữ lại ít nhất một instance phục vụ trong deployment hiện tại khi tách.
            if len(last.instances) < 2:
                return False
            destination = last
        elif size(last) == MIN_DEPLOYMENT_INSTANCES:
            destination = apps[-2] if len(apps) > 1 and size(apps[-2]) == MIN_DEPLOYMENT_INSTANCES else last
        else:
            return False

        reclaim = self.cluster.has_spot_instance(model_endpoint.model_name)
        if not reclaim:
            if model_endpoint.scaling_level < 2:
                return False
            processors = self.cluster.free_processors_and_kill_spot()
            if processors is None:
                return False

        if split:
            destination = Application.from_config(
                application_repo.get_application_cfg(model_endpoint.model_name),
                application_id=last.application_id + 1,
                cluster=self.cluster, region=model_endpoint.region, router=model_endpoint, arbiter=None,
                feed_async=last.feed_async, feed_async_granularity=last.feed_async_granularity,
            )
        if reclaim:
            destination.allocator.start_reclaim_spot_instance(model_endpoint.model_name)
            wait = self.overheads.reclaim_spot
        else:
            self.spin_up_new_instance(model_endpoint, destination, processors)
            wait = self.overheads.spin_up
        if split:
            self._move_instance(last.instances[-1], last, destination)
            model_endpoint.add_application(destination)
        return self._record_scale(model_endpoint, before, trigger, "up", wait)

    def spin_up_new_instance(self, model_endpoint, application, processors):
        instance_cfg = start_state_repo.get_start_state_cfg(model_endpoint.start_state).instance
        parallelism = ModelParallelism(
            pipeline_parallelism=instance_cfg.pipeline_parallelism,
            tensor_parallelism=instance_cfg.tensor_parallelism,
        )
        application.allocator.start_spin_up_instance(
            instance_cfg=instance_cfg, processors=processors, parallelism=parallelism, pre_start=False,
        )

    @staticmethod
    def _move_instance(instance, source, destination):
        source.remove_instance(instance)
        destination.add_instance(instance)
        instance.application = destination

    def scale_down_to_spot(self, model_endpoint):
        apps = model_endpoint.applications
        if not apps or any(app.pending_instances for app in apps[-2:]):
            return False

        last = apps[-1]
        if size(last) == MAX_DEPLOYMENT_INSTANCES:
            last.allocator.start_spin_down_instance(last.instances[-1])
        elif len(apps) > 1 and size(last) == MIN_DEPLOYMENT_INSTANCES:
            previous = apps[-2]
            if size(previous) == MAX_DEPLOYMENT_INSTANCES:
                previous.allocator.start_spin_down_instance(previous.instances[-1])
            elif size(previous) == MIN_DEPLOYMENT_INSTANCES:
                last.allocator.start_spin_down_instance(last.instances[-1])
                self._move_instance(last.instances[-1], last, previous)
                model_endpoint.remove_application(last)
            else:
                return False
        else:
            return False
        return True

    def _scale_down(self, model_endpoint, trigger):
        before = model_endpoint.instance_counts()
        if model_endpoint.scaling_level < 1 or sum(before) <= model_endpoint.min_instances:
            return False
        if not self.scale_down_to_spot(model_endpoint):
            return False
        return self._record_scale(model_endpoint, before, trigger, "down", self.overheads.spin_down)

    def force_scale_up(self, model_endpoint):
        self._scale_up(model_endpoint, "hourly")

    def force_scale_down(self, model_endpoint):
        self._scale_down(model_endpoint, "hourly")
        self.log_state(model_endpoint, self.memory_utilization(model_endpoint))

    def _can_scale(self, model_endpoint):
        return clock() >= self.next_scale_time.get(model_endpoint.model_name, 0)

    def scale(self, model_endpoint):
        if not self._can_scale(model_endpoint):
            return
        utilization = self.memory_utilization(model_endpoint)
        if utilization is not None:
            if utilization > SCALE_UP_THRESHOLD:
                self._scale_up(model_endpoint, "request")
            elif utilization < SCALE_DOWN_THRESHOLD:
                self._scale_down(model_endpoint, "request")
        self.log_state(model_endpoint, utilization)


class GlobalArbiterAwareShortTermArbiter(BasicArbiter):
    """LT-I applies the hourly plan immediately."""

    def scale(self, model_endpoint):
        self.log_state(model_endpoint, self.memory_utilization(model_endpoint))


class GlobalAribiterMemoryUtilizationScaling(BasicArbiter):
    """LT-U approaches the hourly target when memory crosses the scaling thresholds."""

    def scale(self, model_endpoint):
        name = model_endpoint.model_name
        delta = self.changes.get(name, 0)
        utilization = self.memory_utilization(model_endpoint)
        if self._can_scale(model_endpoint) and utilization is not None:
            if delta > 0 and utilization > SCALE_UP_THRESHOLD and self._scale_up(model_endpoint, "request"):
                self.changes[name] -= 1
            elif delta < 0 and utilization < SCALE_DOWN_THRESHOLD and self._scale_down(model_endpoint, "request"):
                self.changes[name] += 1
        self.log_state(model_endpoint, utilization)

    def force_scale_up(self, model_endpoint):
        name = model_endpoint.model_name
        self.changes[name] = self.changes.get(name, 0) + 1

    def force_scale_down(self, model_endpoint):
        name = model_endpoint.model_name
        self.changes[name] = self.changes.get(name, 0) - 1


# LT-UA (§6.4): trong 20 phút cuối giờ, khi đã đạt số instance ILP, so TPS thực với dự báo ARIMA
LTUA_WINDOW = 20 * 60
LTUA_UP_RATIO = 5.0      # tải thực ≥ 5x dự báo -> tiếp tục tăng
LTUA_DOWN_RATIO = 0.5    # tải thực ≤ 0,5x dự báo -> tiếp tục giảm


class GlobalArbiterARIMAChecking(GlobalAribiterMemoryUtilizationScaling):
    def __init__(self, cluster, overheads):
        super().__init__(cluster, overheads)
        self.arima_forecast = {}

    def set_arima_forecast(self, model_name, forecast):
        self.arima_forecast[model_name] = forecast.set_index("Time")["Predicted"]

    def ratio_between_arima_and_actual(self, model_endpoint):
        predicted = self.arima_forecast[model_endpoint.model_name].get(60 * (clock() // 60), 0)
        observed = model_endpoint.tokens_last_minute()
        if predicted > 0:
            return observed / predicted
        return float("inf") if observed > 0 else 1.0

    def scale(self, model_endpoint):
        name = model_endpoint.model_name
        target_reached = self.changes.get(name, 0) == 0
        in_window = clock() % 3600 >= 3600 - LTUA_WINDOW
        if not (target_reached and in_window and name in self.arima_forecast):
            return super().scale(model_endpoint)
        if self._can_scale(model_endpoint):
            ratio = self.ratio_between_arima_and_actual(model_endpoint)
            if ratio >= LTUA_UP_RATIO:
                self._scale_up(model_endpoint, "request")
            elif ratio <= LTUA_DOWN_RATIO:
                self._scale_down(model_endpoint, "request")
        self.log_state(model_endpoint, self.memory_utilization(model_endpoint))


class ChironArbiter(BasicArbiter):
    """Use Chiron's workload signals with the shared allocation limits."""

    def scale(self, model_endpoint):
        if not self._can_scale(model_endpoint):
            return
        if model_endpoint.model_name.endswith("-d"):
            ready, _ = model_endpoint.instance_counts()
            if model_endpoint.pending_requests == 0:
                self._scale_down(model_endpoint, "request")
            elif ready:
                pending_time = (
                    model_endpoint.pending_requests * model_endpoint.prompt_time
                    + model_endpoint.pending_tokens / (model_endpoint.decode_throughput * ready)
                )
                if pending_time > 24 * 60 * 60:
                    self._scale_up(model_endpoint, "request")
        else:
            model_name = model_endpoint.model_name.removesuffix("-p")
            endpoints = (
                self.cluster.region.get_model_endpoint(model_name + "-p"),
                self.cluster.region.get_model_endpoint(model_name),
            )
            instances = [instance for ep in endpoints if ep for app in ep.applications for instance in app.instances]
            if instances:
                ibp = sum(instance.cnt_iw_requests > 0 for instance in instances) / len(instances)
                if ibp > 0.6:
                    self._scale_up(model_endpoint, "request")
                else:
                    self._scale_down(model_endpoint, "request")
        self.log_state(model_endpoint, self.memory_utilization(model_endpoint))
