"""Run the dev trace matrix, recording LT-UA decisions and CBC status."""
import logging
import os
from pathlib import Path
import runpy
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
CASES = {
    "reactive": ("basic_arbiter", .90, .10, 5, .50, "offline"),
    "lt_u": ("global_arbiter_memory_utilization", .90, .10, 5, .50, "offline"),
    "lt_ua": ("global_arbiter_ARIMA_checking", .90, .10, 5, .50, "offline"),
    "eps063": ("global_arbiter_ARIMA_checking", .63, .10, 5, .50, "offline"),
    "eps100": ("global_arbiter_ARIMA_checking", 1.0, .10, 5, .50, "offline"),
    "beta005": ("global_arbiter_ARIMA_checking", .90, .05, 5, .50, "offline"),
    "beta015": ("global_arbiter_ARIMA_checking", .90, .15, 5, .50, "offline"),
    "up3": ("global_arbiter_ARIMA_checking", .90, .10, 3, .50, "offline"),
    "down025": ("global_arbiter_ARIMA_checking", .90, .10, 5, .25, "offline"),
    "lt_ua_online": ("global_arbiter_ARIMA_checking", .90, .10, 5, .50, "online"),
    "floor_base": ("global_arbiter_ARIMA_checking", .90, .10, 5, .50, "online"),
    "floor_up3": ("global_arbiter_ARIMA_checking", .90, .10, 3, .50, "online"),
    "floor_down025": ("global_arbiter_ARIMA_checking", .90, .10, 5, .25, "online"),
}


def instrument():
    sys.path.insert(0, str(ROOT))
    import arbiter
    import global_arbiter
    import optimizer

    global_arbiter.NIW_BUFFER = float(os.environ["SAGE_BETA"])
    arbiter.LTUA_UP_RATIO = float(os.environ["SAGE_LTUA_UP_RATIO"])
    arbiter.LTUA_DOWN_RATIO = float(os.environ["SAGE_LTUA_DOWN_RATIO"])
    original_solve = optimizer.Optimizer.solve
    cls = arbiter.GlobalArbiterARIMAChecking
    original_scale = cls.scale
    original_ratio = cls.ratio_between_arima_and_actual
    evaluated = None

    def log_solve(self, current, regional, worldwide):
        result = original_solve(self, current, regional, worldwide)
        logging.info("DEV_ILP_STATUS,%s,%s,%s", arbiter.clock(), result.status, result.objective_value)
        if os.environ.get("SAGE_DEV_CLAMP_FLOOR") == "1":
            for region, models in enumerate(result.delta):
                for model, gpus in enumerate(models):
                    gpus[0] = max(gpus[0], 2 - current[model][region][0])
        return result

    def log_ratio(self, endpoint):
        nonlocal evaluated
        evaluated = original_ratio(self, endpoint)
        return evaluated

    def log_scale(self, endpoint):
        nonlocal evaluated
        evaluated = None
        before = sum(arbiter.size(app) for app in endpoint.applications)
        result = original_scale(self, endpoint)
        if evaluated is not None:
            after = sum(arbiter.size(app) for app in endpoint.applications)
            signal = (
                "up" if evaluated >= arbiter.LTUA_UP_RATIO else
                "down" if evaluated <= arbiter.LTUA_DOWN_RATIO else "hold"
            )
            logging.info("DEV_LTUA,%s,%s,%s,%s,%s,%s", arbiter.clock(),
                         endpoint.region.region_name, endpoint.model_name, evaluated, signal, after - before)
        return result

    optimizer.Optimizer.solve = log_solve
    cls.scale = log_scale
    cls.ratio_between_arima_and_actual = log_ratio
    sys.argv = [str(ROOT / "run.py"), *sys.argv[2:]]
    runpy.run_path(sys.argv[0], run_name="__main__")


def launch(item):
    name, (strategy, epsilon, beta, up, down, mode) = item
    env = dict(os.environ, PYTHONIOENCODING="utf-8", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
               SAGE_BETA=str(beta), SAGE_LTUA_UP_RATIO=str(up), SAGE_LTUA_DOWN_RATIO=str(down),
               SAGE_DEV_CLAMP_FLOOR=str(int(name.startswith("floor_"))))
    cmd = [
        sys.executable, str(__file__), "--instrument", "controller=us3-4models",
        "trace=random_trace", "trace.filename=azure_trace_dev_1day",
        f"trace.path={(OUT / 'azure_trace_dev_1day.csv').as_posix()}",
        "performance_model.db_path=data/perf_model_4models.csv",
        "global_arbiter.theta_file=data/theta_tps_v2.csv", f"global_arbiter.arima_traces={(OUT / 'forecasts').as_posix()}",
        f"global_arbiter.forecast_mode={mode}", f"global_arbiter.epsilon={epsilon}",
        f"long_term_scaling={name != 'reactive'}", "end_time=90000", f"output_dir={(OUT / name).as_posix()}",
        *(f"controller.regions.{region}.arbiter={strategy}" for region in range(3)),
    ]
    with (OUT / f"{name}.out").open("w", encoding="utf-8") as stream:
        result = subprocess.run(cmd, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    print(f"{name} exit {result.returncode}", flush=True)
    return result.returncode


if __name__ == "__main__":
    if sys.argv[1:2] == ["--instrument"]:
        instrument()
    else:
        selected = sys.argv[1:] or list(CASES)
        with ThreadPoolExecutor(max_workers=3) as pool:
            statuses = list(pool.map(launch, [(name, CASES[name]) for name in selected]))
        sys.exit(any(statuses))
