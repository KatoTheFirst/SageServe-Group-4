import logging

from abc import ABC

from application import Application
from model import ModelParallelism
import application_repo
from simulator import clock, schedule_event, cancel_event, reschedule_event
import start_state_repo
import utils

from queue import Queue

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
        self.scaling_in_progress = {}
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
    """
    Basic Arbiter.
    """
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

    def scale_up_from_spot(self, model_endpoint):
        if size(model_endpoint.applications[-1]) == 3:
            recent_application = model_endpoint.applications[-1]
            old_instance = recent_application.instances[-1]
            recent_application.remove_instance(old_instance)
            # start new application with old instance and reclaim spot instance
            new_application = Application.from_config(application_repo.get_application_cfg(model_endpoint.model_name),
                                    application_id=recent_application.application_id + 1,
                                    cluster=model_endpoint.region.region_cluster,
                                    region=model_endpoint.region,
                                    router=model_endpoint,
                                    arbiter=None,
                                    feed_async=recent_application.feed_async,
                                    feed_async_granularity=recent_application.feed_async_granularity)
            new_application.add_instance(old_instance) # add old instance
            old_instance.application = new_application
            new_application.allocator.start_reclaim_spot_instance(model_endpoint.model_name) # reclaim spot instance
            model_endpoint.add_application(new_application)
        elif len(model_endpoint.applications) > 1 \
                and size(model_endpoint.applications[-1]) == 2 \
                and size(model_endpoint.applications[-2]) == 2:
            recent_application = model_endpoint.applications[-2]
            assert size(recent_application) == 2
            recent_application.allocator.start_reclaim_spot_instance(model_endpoint.model_name)
        elif (len(model_endpoint.applications) > 1 \
                and size(model_endpoint.applications[-1]) == 2 \
                and size(model_endpoint.applications[-2]) == 3) \
                or (len(model_endpoint.applications) == 1 \
                    and size(model_endpoint.applications[-1]) == 2):
            recent_application = model_endpoint.applications[-1]
            assert size(recent_application) == 2
            recent_application.allocator.start_reclaim_spot_instance(model_endpoint.model_name)
    
    def spin_up_new_instance(self, model_endpoint, application, processors):
        start_state_cfg = start_state_repo.get_start_state_cfg(model_endpoint.start_state)
        instance_cfg = start_state_cfg.instance
        parallelism = ModelParallelism(pipeline_parallelism=instance_cfg.pipeline_parallelism,
                                tensor_parallelism=instance_cfg.tensor_parallelism)
        application.allocator.start_spin_up_instance(instance_cfg=instance_cfg,
                                    processors=processors,
                                    parallelism=parallelism,
                                    pre_start=True)

    def scale_up_from_spot_other(self, model_endpoint, processors):
        if size(model_endpoint.applications[-1]) == 3:
            recent_application = model_endpoint.applications[-1]
            old_instance = recent_application.instances[-1]
            recent_application.remove_instance(old_instance)
            # start new application with old instance and reclaim spot instance
            # new_application = Application.new_application(recent_application.application_id + 1, model_endpoint.model_name)
            new_application = Application.from_config(application_repo.get_application_cfg(model_endpoint.model_name),
                                    application_id=recent_application.application_id + 1,
                                    cluster=model_endpoint.region.region_cluster,
                                    region=model_endpoint.region,
                                    router=model_endpoint,
                                    arbiter=None,
                                    feed_async=recent_application.feed_async,
                                    feed_async_granularity=recent_application.feed_async_granularity)
            new_application.add_instance(old_instance) # add old instance
            old_instance.application = new_application
            self.spin_up_new_instance(model_endpoint, new_application, processors)
            model_endpoint.add_application(new_application)
        elif len(model_endpoint.applications) > 1 \
                and size(model_endpoint.applications[-1]) == 2 \
                and size(model_endpoint.applications[-2]) == 2:
            recent_application = model_endpoint.applications[-2]
            assert size(recent_application) == 2
            self.spin_up_new_instance(model_endpoint, recent_application, processors)
        elif (len(model_endpoint.applications) > 1 \
                and size(model_endpoint.applications[-1]) == 2 \
                and size(model_endpoint.applications[-2]) == 3) \
                or (len(model_endpoint.applications) == 1 \
                    and size(model_endpoint.applications[-1]) == 2):
            recent_application = model_endpoint.applications[-1]
            assert size(recent_application) == 2
            self.spin_up_new_instance(model_endpoint, recent_application, processors)

    def scale_down_to_spot(self, model_endpoint):
            if any(app.pending_instances for app in model_endpoint.applications[-2:]):
                return False      # đang có instance chờ vào phục vụ: không gộp/bớt deployment lúc này
            if len(model_endpoint.applications[-1].instances) == 3:
                #logging.debug([len(app.instances) for app in model_endpoint.applications])
                recent_application = model_endpoint.applications[-1]
                old_instance = recent_application.instances[-1]
                recent_application.allocator.start_spin_down_instance(old_instance)
            elif len(model_endpoint.applications) > 1 \
                    and len(model_endpoint.applications[-1].instances) == 2 \
                    and len(model_endpoint.applications[-2].instances) == 2:
                #logging.debug([len(app.instances) for app in model_endpoint.applications])
                recent_application = model_endpoint.applications[-1]
                old_instance = recent_application.instances[-1]
                recent_application.allocator.start_spin_down_instance(old_instance)
                remaining_instance = recent_application.instances[-1]
                penultimate_application = model_endpoint.applications[-2]
                penultimate_application.add_instance(remaining_instance)
                remaining_instance.application = penultimate_application
                recent_application.remove_instance(remaining_instance)
                model_endpoint.remove_application(recent_application)
                del recent_application
            elif len(model_endpoint.applications) > 1 \
                    and len(model_endpoint.applications[-1].instances) == 2 \
                    and len(model_endpoint.applications[-2].instances) == 3:
                #logging.debug([len(app.instances) for app in model_endpoint.applications])
                recent_application = model_endpoint.applications[-2]
                assert len(recent_application.instances) == 3
                last_instance = recent_application.instances[-1]
                recent_application.allocator.start_spin_down_instance(last_instance)

    def force_scale_up(self, model_endpoint):
        """
        For the scaling up or scaling down for a model_endpoint
        """
        #logging.debug(f"Force scale up called at {model_endpoint} for {model_endpoint.model_name} at time {clock()}")
        if self.cluster.has_spot_instance(model_endpoint.model_name) and model_endpoint.scaling_level >= 1:
            #logging.debug(f"Scaling up {self.cluster.region.region_name} {model_endpoint.model_name}")
            self.scale_up_from_spot(model_endpoint)
            #logging.debug([len(app.instances) for app in model_endpoint.applications])
        elif self.cluster.has_spot_instance_any() and model_endpoint.scaling_level >= 2:
            #logging.debug(f"Scaling up other {self.cluster.region.region_name} {model_endpoint.model_name}")
            processors = self.cluster.free_processors_and_kill_spot()
            self.scale_up_from_spot_other(model_endpoint, processors)

    def force_scale_down(self, model_endpoint):
        """
        For the scaling up or scaling down for a model_endpoint
        """
        #logging.debug(f"Force scale down called at {model_endpoint} for {model_endpoint.model_name} at time {clock()}")
        if model_endpoint.scaling_level >= 1:
            self.scale_down_to_spot(model_endpoint)
        for model_ep in self.cluster.region.model_endpoint_routers:
            self.results['timestamp'].append(clock())
            self.results['model'].append(model_ep.model_name)
            self.results['prod'].append(str(sum([len(app.instances) for app in model_ep.applications])))
            self.results['spot'].append(str(self.cluster.get_spot_instance_count(model_ep.model_name)))
            self.results['memory_util'].append(model_endpoint.get_memory() / model_endpoint.get_max_memory())


    def scale(self, model_endpoint):
        """
        Scales the application based on memory utilisation.
        """
        if model_endpoint.model_name not in self.scaling_in_progress:
            self.scaling_in_progress[model_endpoint.model_name] = False
            self.next_scale_time[model_endpoint.model_name] = 0

        # reset scaling_in_progress if time has crossed
        if clock() >= self.next_scale_time[model_endpoint.model_name]:
            self.scaling_in_progress[model_endpoint.model_name] = False

        # return if scaling in progress
        if self.scaling_in_progress[model_endpoint.model_name]:
            return

        memory_utilisation = model_endpoint.get_memory() / model_endpoint.get_max_memory()
        mem_util = str([[ins.memory / ins.max_memory for ins in app.instances] for app in model_endpoint.applications])
        if memory_utilisation > SCALE_UP_THRESHOLD:
            if self.cluster.has_spot_instance(model_endpoint.model_name) and model_endpoint.scaling_level >= 1:
                #logging.debug([len(app.instances) for app in model_endpoint.applications])
                #logging.debug(f"Scaling up {self.cluster.region.region_name} {model_endpoint.model_name} {mem_util} at {clock()}")
                # make space
                self.scale_up_from_spot(model_endpoint)
                #logging.debug([len(app.instances) for app in model_endpoint.applications])

                # set scaling progress and next scaling time
                self.scaling_in_progress[model_endpoint.model_name] = True
                self.next_scale_time[model_endpoint.model_name] = clock() + self.overheads.reclaim_spot
            elif self.cluster.has_spot_instance_any() and model_endpoint.scaling_level >= 2:
                # TODO: find number of gpus needed
                # gpus = 8
                #logging.debug([len(app.instances) for app in model_endpoint.applications])
                #logging.debug(f"Scaling up other {self.cluster.region.region_name} {model_endpoint.model_name} {mem_util} at {clock()}")
                processors = self.cluster.free_processors_and_kill_spot()
                # maintain count of free gpus per cluster
                # if insufficient, randomly free up those many gpus by freeing spot instances

                self.scale_up_from_spot_other(model_endpoint, processors)
                #logging.debug([len(app.instances) for app in model_endpoint.applications])
                # set scaling progress and next scaling time
                self.scaling_in_progress[model_endpoint.model_name] = True
                self.next_scale_time[model_endpoint.model_name] = clock() + self.overheads.spin_up
        elif memory_utilisation < SCALE_DOWN_THRESHOLD and model_endpoint.scaling_level >= 1:
            # model_endpoint.scale_down()

            #logging.debug([len(app.instances) for app in model_endpoint.applications])
            #logging.debug(f"Scaling down {self.cluster.region.region_name} {model_endpoint.model_name} {mem_util} at {clock()}")
            self.scale_down_to_spot(model_endpoint)
            #logging.debug([len(app.instances) for app in model_endpoint.applications])
            self.scaling_in_progress[model_endpoint.model_name] = True
            self.next_scale_time[model_endpoint.model_name] = clock() + self.overheads.spin_down
            # #logging.debug(f"Tried to scale down {self.cluster.region.region_name} {model_endpoint.model_name} {mem_util} at {clock()}")
        for model_ep in self.cluster.region.model_endpoint_routers:
            self.results['timestamp'].append(clock())
            self.results['model'].append(model_ep.model_name)
            self.results['prod'].append(str(sum([len(app.instances) for app in model_ep.applications])))
            self.results['spot'].append(str(self.cluster.get_spot_instance_count(model_ep.model_name)))
            self.results['memory_util'].append(memory_utilisation)
        
class GlobalArbiterAwareShortTermArbiter(BasicArbiter):
    """LT-I (§6.4): mỗi giờ co giãn thẳng tới số instance ILP đề xuất; không co giãn phản ứng giữa giờ."""

    def scale(self, model_endpoint):
        self.log_state(model_endpoint)

    def log_state(self, model_endpoint):
        for model_ep in self.cluster.region.model_endpoint_routers:
            self.results['timestamp'].append(clock())
            self.results['model'].append(model_ep.model_name)
            self.results['prod'].append(str(sum([len(app.instances) for app in model_ep.applications])))
            self.results['spot'].append(str(self.cluster.get_spot_instance_count(model_ep.model_name)))
            self.results['memory_util'].append(model_endpoint.get_memory() / model_endpoint.get_max_memory())


class GlobalAribiterMemoryUtilizationScaling(BasicArbiter):
    """Arbiter that is aware of the recommendations by the global arbiter"""
    """
    Run with 
        long_term_scaling=True
        short_term_scaling=True
        controller.regions.0.arbiter=global_arbiter_short_term_scaling
        controller.regions.1.arbiter=global_arbiter_short_term_scaling
        controller.regions.2.arbiter=global_arbiter_short_term_scaling
    """
    
    def __init__(self,
                 cluster,
                 overheads):
        super().__init__(cluster, overheads)            
    
    def scale_down_to_spot(self, model_endpoint):
        if any(app.pending_instances for app in model_endpoint.applications[-2:]):
            return False      # đang có instance chờ vào phục vụ: không gộp/bớt deployment lúc này
        if len(model_endpoint.applications[-1].instances) == 3:
            #logging.debug([len(app.instances) for app in model_endpoint.applications])
            recent_application = model_endpoint.applications[-1]
            old_instance = recent_application.instances[-1]
            recent_application.allocator.start_spin_down_instance(old_instance)
            return True
        elif len(model_endpoint.applications) > 1 \
                and len(model_endpoint.applications[-1].instances) == 2 \
                and len(model_endpoint.applications[-2].instances) == 2:
            #logging.debug([len(app.instances) for app in model_endpoint.applications])
            recent_application = model_endpoint.applications[-1]
            old_instance = recent_application.instances[-1]
            recent_application.allocator.start_spin_down_instance(old_instance)
            remaining_instance = recent_application.instances[-1]
            penultimate_application = model_endpoint.applications[-2]
            penultimate_application.add_instance(remaining_instance)
            remaining_instance.application = penultimate_application
            recent_application.remove_instance(remaining_instance)
            model_endpoint.remove_application(recent_application)
            del recent_application
            return True
        elif len(model_endpoint.applications) > 1 \
                and len(model_endpoint.applications[-1].instances) == 2 \
                and len(model_endpoint.applications[-2].instances) == 3:
            #logging.debug([len(app.instances) for app in model_endpoint.applications])
            recent_application = model_endpoint.applications[-2]
            assert len(recent_application.instances) == 3
            last_instance = recent_application.instances[-1]
            recent_application.allocator.start_spin_down_instance(last_instance)
            return True
        return False


    def scale_up_logic(self, model_endpoint):
        if self.cluster.has_spot_instance(model_endpoint.model_name) and model_endpoint.scaling_level >= 1:
            #logging.debug(f"Scaling up {self.cluster.region.region_name} {model_endpoint.model_name}")
            self.scale_up_from_spot(model_endpoint)
            #logging.debug([len(app.instances) for app in model_endpoint.applications])
            
            # set scaling progress and next scaling time
            self.scaling_in_progress[model_endpoint.model_name] = True
            self.next_scale_time[model_endpoint.model_name] = clock() + self.overheads.reclaim_spot
        elif self.cluster.has_spot_instance_any() and model_endpoint.scaling_level >= 2:
            #logging.debug(f"Scaling up other {self.cluster.region.region_name} {model_endpoint.model_name}")
            processors = self.cluster.free_processors_and_kill_spot()
            self.scale_up_from_spot_other(model_endpoint, processors)
            
            # set scaling progress and next scaling time
            self.scaling_in_progress[model_endpoint.model_name] = True
            self.next_scale_time[model_endpoint.model_name] = clock() + self.overheads.spin_up
        else:
            #logging.debug("Failed to up scale")
            # indicate no scaling
            self.scaling_in_progress[model_endpoint.model_name] = False


    def scale(self, model_endpoint):
        """
        Implement scaling logic here
        """
        # add to dictionary if not there
        if model_endpoint.model_name not in self.changes:
            self.changes[model_endpoint.model_name] = 0
            self.scaling_in_progress[model_endpoint.model_name] = False
            self.next_scale_time[model_endpoint.model_name] = 0
        
        # reset scaling_in_progress if time has crossed
        if clock() >= self.next_scale_time[model_endpoint.model_name]:
            self.scaling_in_progress[model_endpoint.model_name] = False
        
        # return if scaling in progress
        if self.scaling_in_progress[model_endpoint.model_name]:
            for model_ep in self.cluster.region.model_endpoint_routers:
                self.results['timestamp'].append(clock())
                self.results['model'].append(model_ep.model_name)
                self.results['prod'].append(str(sum([len(app.instances) for app in model_ep.applications])))
                self.results['spot'].append(str(self.cluster.get_spot_instance_count(model_ep.model_name)))
                self.results['memory_util'].append(model_endpoint.get_memory() / model_endpoint.get_max_memory())
            return

        memory_utilisation = model_endpoint.get_memory() / model_endpoint.get_max_memory()
        # return if no scaling to do
        if self.changes[model_endpoint.model_name] > 0 and memory_utilisation > SCALE_UP_THRESHOLD:
            self.scale_up_logic(model_endpoint)
            # if scaled, subtract from changes to make
            if self.scaling_in_progress[model_endpoint.model_name]:
                self.changes[model_endpoint.model_name] -= 1
        elif self.changes[model_endpoint.model_name] < 0 and memory_utilisation < SCALE_DOWN_THRESHOLD:
            if self.scale_down_to_spot(model_endpoint):
                #logging.debug(f"Scaling down {model_endpoint}")
                self.changes[model_endpoint.model_name] += 1

        for model_ep in self.cluster.region.model_endpoint_routers:
            self.results['timestamp'].append(clock())
            self.results['model'].append(model_ep.model_name)
            self.results['prod'].append(str(sum([len(app.instances) for app in model_ep.applications])))
            self.results['spot'].append(str(self.cluster.get_spot_instance_count(model_ep.model_name)))
            self.results['memory_util'].append(memory_utilisation)
        

    def force_scale_up(self, model_endpoint):
        if model_endpoint.model_name not in self.changes.keys():
            self.changes[model_endpoint.model_name] = 0
            self.scaling_in_progress[model_endpoint.model_name] = False
            self.next_scale_time[model_endpoint.model_name] = 0
        self.changes[model_endpoint.model_name] += 1
        #logging.debug(f"force_scale_up for {model_endpoint.model_name} at {model_endpoint}: {self.changes[model_endpoint.model_name]}")
    
    def force_scale_down(self, model_endpoint):
        # LT-U (§6.4): chỉ ghi nhận mục tiêu; giảm thật khi bộ nhớ < 30% (trong scale())
        if model_endpoint.model_name not in self.changes.keys():
            self.changes[model_endpoint.model_name] = 0
            self.scaling_in_progress[model_endpoint.model_name] = False
            self.next_scale_time[model_endpoint.model_name] = 0
        self.changes[model_endpoint.model_name] -= 1


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
        return model_endpoint.tokens_last_minute() / predicted if predicted > 0 else float("inf")

    def scale(self, model_endpoint):
        name = model_endpoint.model_name
        target_reached = self.changes.get(name, 0) == 0
        in_window = clock() % 3600 >= 3600 - LTUA_WINDOW
        if not (target_reached and in_window and name in self.arima_forecast):
            return super().scale(model_endpoint)
        if clock() >= self.next_scale_time.get(name, 0):
            self.scaling_in_progress[name] = False
        if not self.scaling_in_progress.get(name, False):
            ratio = self.ratio_between_arima_and_actual(model_endpoint)
            if ratio >= LTUA_UP_RATIO:
                self.scale_up_logic(model_endpoint)
            elif ratio <= LTUA_DOWN_RATIO:
                self.scale_down_to_spot(model_endpoint)
        for model_ep in self.cluster.region.model_endpoint_routers:
            self.results['timestamp'].append(clock())
            self.results['model'].append(model_ep.model_name)
            self.results['prod'].append(str(sum([len(app.instances) for app in model_ep.applications])))
            self.results['spot'].append(str(self.cluster.get_spot_instance_count(model_ep.model_name)))
            self.results['memory_util'].append(model_endpoint.get_memory() / model_endpoint.get_max_memory())


class ChironArbiter(BasicArbiter):
    """
    Chiron Arbiter.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_write = 0
    def scale(self, model_endpoint):
        """
        Scales the application based on memory utilisation.
        """
        if model_endpoint.model_name not in self.scaling_in_progress:
            self.scaling_in_progress[model_endpoint.model_name] = False
            self.next_scale_time[model_endpoint.model_name] = 0

        # reset scaling_in_progress if time has crossed
        if clock() >= self.next_scale_time[model_endpoint.model_name]:
            self.scaling_in_progress[model_endpoint.model_name] = False

        # return if scaling in progress
        if self.scaling_in_progress[model_endpoint.model_name]:
            return
        memory_utilisation = model_endpoint.get_memory() / model_endpoint.get_max_memory()
        # if clock() - self.last_write > 5:
        # logging.info(f"{model_endpoint.model_name} {[len(app.instances) for app in model_endpoint.applications]} {round(memory_utilisation, 2)}")
        if model_endpoint.model_name.endswith("-d"):
            ttft_batch = 24*60*60
            instance_cnt = sum([len(app.instances) for app in model_endpoint.applications])
            pending_time = model_endpoint.pending_requests * model_endpoint.prompt_time + \
            model_endpoint.pending_tokens / (model_endpoint.decode_throughput * instance_cnt)
            if pending_time > ttft_batch:
                # scale up
                if self.cluster.has_spot_instance(model_endpoint.model_name) and model_endpoint.scaling_level >= 1:
                    self.scale_up_from_spot(model_endpoint)
                    self.scaling_in_progress[model_endpoint.model_name] = True
                    self.next_scale_time[model_endpoint.model_name] = clock() + self.overheads.reclaim_spot
                elif self.cluster.has_spot_instance_any() and model_endpoint.scaling_level >= 2:
                    processors = self.cluster.free_processors_and_kill_spot()
                    self.scale_up_from_spot_other(model_endpoint, processors)
                    self.scaling_in_progress[model_endpoint.model_name] = True
                    self.next_scale_time[model_endpoint.model_name] = clock() + self.overheads.spin_up
            # if no batch requests, scale down to 0
            if model_endpoint.pending_requests == 0 and instance_cnt > 0:
                # while model_endpoint.applications[0].instances > 0:
                self.scale_down_to_spot(model_endpoint)
                self.scaling_in_progress[model_endpoint.model_name] = True
                self.next_scale_time[model_endpoint.model_name] = clock() + self.overheads.spin_down
        else:
            model_name = model_endpoint.model_name.removesuffix("-p")
            iw_model_endpoint = self.cluster.region.get_model_endpoint(model_name+'-p')
            mix_model_endpoint = self.cluster.region.get_model_endpoint(model_name)
            cnt_iw_total = sum([len(app.instances) for app in iw_model_endpoint.applications])
            cnt_mix_total = sum([len(app.instances) for app in mix_model_endpoint.applications])
            cnt_iw_running = 0
            for app in iw_model_endpoint.applications:
                for instance in app.instances:
                    if instance.cnt_iw_requests > 0:
                        cnt_iw_running += 1
            cnt_mix_running = 0
            for app in mix_model_endpoint.applications:
                for instance in app.instances:
                    if instance.cnt_iw_requests > 0:
                        cnt_mix_running += 1
            ibp = (cnt_iw_running + cnt_mix_running) / (cnt_iw_total + cnt_mix_total)
            # if clock() - self.last_write > 5:
            #     self.last_write = clock()
            #     logging.info(f"Time: {clock()//1}, ibp={round(ibp, 2)}, {cnt_iw_running}, {cnt_mix_running}, {cnt_iw_total}, {cnt_mix_total}")
            # print([a.model_name for a in self.cluster.region.model_endpoint_routers])
            if ibp > 0.6:
                if self.cluster.has_spot_instance(model_endpoint.model_name) and model_endpoint.scaling_level >= 1:
                    self.scale_up_from_spot(model_endpoint)
                    self.scaling_in_progress[model_endpoint.model_name] = True
                    self.next_scale_time[model_endpoint.model_name] = clock() + self.overheads.reclaim_spot
                elif self.cluster.has_spot_instance_any() and model_endpoint.scaling_level >= 2:
                    processors = self.cluster.free_processors_and_kill_spot()
                    self.scale_up_from_spot_other(model_endpoint, processors)
                    self.scaling_in_progress[model_endpoint.model_name] = True
                    self.next_scale_time[model_endpoint.model_name] = clock() + self.overheads.spin_up
            else:
                self.scale_down_to_spot(model_endpoint)
                self.scaling_in_progress[model_endpoint.model_name] = True
                self.next_scale_time[model_endpoint.model_name] = clock() + self.overheads.spin_down
        
        for model_ep in self.cluster.region.model_endpoint_routers:
            self.results['timestamp'].append(clock())
            self.results['model'].append(model_ep.model_name)
            self.results['prod'].append(str(sum([len(app.instances) for app in model_ep.applications])))
            self.results['spot'].append(str(self.cluster.get_spot_instance_count(model_ep.model_name)))
            self.results['memory_util'].append(memory_utilisation)
