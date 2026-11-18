"""Summarize dev acceptance metrics and verify the logged optimizer plans."""
import ast
from pathlib import Path

import numpy as np
import pandas as pd

from run_matrix import CASES

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
MODELS = ["bloom-176b", "llama2-70b", "llama3.1-8b", "llama3.2-3b"]
TRACE = pd.read_csv(OUT / "azure_trace_dev_1day.csv")
THETA = pd.read_csv(ROOT / "data/theta_tps_v2.csv").set_index("model").loc[MODELS, "theta_tps"].to_numpy() * 60


def check_ilp(log, epsilon):
    regional_global = []
    current = []
    delta = []
    status = []
    for line in log:
        if "ILP region peak (TPM): " in line:
            regional, worldwide = line.split("ILP region peak (TPM): ")[1].split(", global peak: ")
            regional_global.append((np.array(ast.literal_eval(regional)), np.array(ast.literal_eval(worldwide))))
        elif "Current allocation at time " in line:
            current.append(np.array(ast.literal_eval(line.split(": ", 1)[1])))
        elif "ILP forecast at time " in line:
            delta.append(np.array(ast.literal_eval(line.split(": ", 1)[1])))
        elif "DEV_ILP_STATUS," in line:
            status.append(line.split("DEV_ILP_STATUS,")[1].split(",")[1])
    assert len(status) == len(regional_global) == len(current) == len(delta)
    assert all(s == "Optimal" for s in status)
    plans = np.array(current) + np.array(delta)
    assert (plans >= 0).all()
    for plan, (regional, worldwide) in zip(plans, regional_global):
        capacity = plan[:, :, 0].T * THETA[:, None]
        assert (capacity + 1e-5 >= epsilon * regional).all()
        assert (capacity.sum(axis=1) + 1e-5 >= worldwide).all()
    return plans[:, :, :, 0]


def summarize(name):
    path = OUT / name
    stdout = (OUT / f"{name}.out").read_text(encoding="utf-8")
    assert "TraceSimulator completed" in stdout and "Traceback" not in stdout, name
    log = (path / "run.log").read_text(encoding="utf-8").splitlines()
    g = pd.concat(pd.read_csv(file) for file in sorted((path / "global_router").glob("*.csv")))
    assert g.request_id.is_unique and set(g.request_id) == set(TRACE.request_id), name
    iw = g[g.workload_type == "prod"]
    niw = g[g.workload_type == "dev"]
    def ih_by_model():
        peaks = []
        for file in (path / "memory").glob("*.csv"):
            df = pd.read_csv(file, usecols=["time", "instance"])
            df = df[df.time.between(3600, 86400, inclusive="left")].copy()
            df["model"] = df.instance.str.split("_").str[1]
            counts = df.groupby(["model", "time"]).instance.nunique().rename("count").reset_index()
            counts["bin"] = counts.time // 900
            peaks.append(counts.groupby(["model", "bin"])["count"].max())
        return pd.concat(peaks).groupby(level=[0, 1]).max().groupby(level=0).sum() / 4

    ih = ih_by_model()
    result = {"case": name, "iw_done": len(iw), "niw_done": len(niw),
              "instance_hours": ih.sum(), "llama2_ih": ih["llama2-70b"],
              "iw_ttft_q3_s": iw.ttft.quantile(.75), "iw_ttft_p95_s": iw.ttft.quantile(.95),
              "iw_e2e_p95_s": iw.response_time.quantile(.95),
              "iw_sla_miss_pct": 100 * ((iw.ttft - 1) > iw.sla).mean(),
              "niw_e2e_p95_s": niw.response_time.quantile(.95),
              "niw_sla_miss_pct": 100 * (niw.response_time > niw.sla).mean()}
    detail = []
    for model in MODELS:
        im, nm = iw[iw.model_type == model], niw[niw.model_type == model]
        detail.append(dict(case=name, model=model, instance_hours=ih[model], iw_done=len(im), niw_done=len(nm),
                           iw_ttft_q3_s=im.ttft.quantile(.75), iw_ttft_p95_s=im.ttft.quantile(.95),
                           iw_e2e_p95_s=im.response_time.quantile(.95),
                           iw_sla_miss_pct=100 * ((im.ttft - 1) > im.sla).mean(),
                           niw_e2e_p95_s=nm.response_time.quantile(.95)))
    if name != "reactive":
        plans = check_ilp(log, CASES[name][1])
        result["ilp_solves"] = len(plans)
        result["ilp_plan_below_floor_pct"] = 100 * (plans < 2).mean()
        result["ilp_plan_instances"] = plans.sum()
        np.save(OUT / f"{name}_plans.npy", plans)
    values = [line.split("DEV_LTUA,")[1].split(",") for line in log if "DEV_LTUA," in line]
    assert all(float(v[0]) % 3600 >= 2400 for v in values), name
    for direction in ("up", "down", "hold"):
        chosen = [int(v[-1]) for v in values if v[-2] == direction and float(v[0]) < 86400]
        result[f"ltua_{direction}_signals"] = len(chosen)
        result[f"ltua_{direction}_moves"] = sum(p != 0 for p in chosen)
    return result, detail


def forecast_stats():
    f = pd.read_csv(OUT / "lt_ua/forecast_log.csv").sort_values(["region", "model", "hour"])
    online = pd.read_csv(OUT / "lt_ua_online/forecast_log.csv")
    matched = f.merge(online, on=["hour", "region", "model"], suffixes=("_offline", "_online"), validate="1:1")
    assert len(matched) == len(f) == len(online)
    for name in ("peak", "mean"):
        matched[f"max_abs_{name}_tpm_delta"] = (matched[f"pred_{name}_tpm_offline"] -
                                               matched[f"pred_{name}_tpm_online"]).abs()
    f["persistence_peak_tpm"] = f.groupby(["region", "model"]).actual_peak_tpm.shift()
    aligned = []
    for (region, model), _ in f.groupby(["region", "model"]):
        pred = pd.read_csv(OUT / "forecasts" / f"final_{model}_prod_1minute_region{region}_arima.csv")
        peak = pred.groupby(pred.Time // 3600).Predicted.max().rename("hour_aligned_peak_tpm").reset_index()
        aligned.append(peak.rename(columns={"Time": "hour"}).assign(region=region, model=model))
    f = f.merge(pd.concat(aligned), on=["region", "model", "hour"], validate="1:1")
    f = f.merge(online[["region", "model", "hour", "pred_peak_tpm"]].rename(
        columns={"pred_peak_tpm": "online_peak_tpm"}), on=["region", "model", "hour"], validate="1:1")
    h = f[f.hour.between(1, 23) & (f.actual_peak_tpm > 0)].copy()
    def row(p):
        a = h.actual_peak_tpm
        e = h[p] - a
        return {"method": p, "samples": len(h), "mape_pct": 100 * (e.abs() / a).mean(),
                "wape_pct": 100 * e.abs().sum() / a.sum(), "bias_pct": 100 * e.sum() / a.sum(),
                "underpredict_pct": 100 * (e < 0).mean()}
    methods = ["hour_aligned_peak_tpm", "online_peak_tpm", "pred_peak_tpm", "persistence_peak_tpm"]
    pd.DataFrame([row(method) for method in methods]).to_csv(OUT / "forecast_metrics.csv", index=False)
    matched.to_csv(OUT / "forecast_comparison.csv", index=False)


if __name__ == "__main__":
    rows, models = [], []
    for name in CASES:
        result, detail = summarize(name)
        rows.append(result)
        models.extend(detail)
    table = pd.DataFrame(rows).set_index("case")
    for col in ("instance_hours", "llama2_ih"):
        table[f"{col}_delta_pct"] = (table[col] / table.loc["reactive", col] - 1) * 100
    table.to_csv(OUT / "metrics.csv")
    pd.DataFrame(models).to_csv(OUT / "metrics_by_model.csv", index=False)
    forecast_stats()
    print(table.round(4).to_string())
