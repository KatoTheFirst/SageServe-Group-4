"""Causal forecast v2 for SageServe Group 4 (standalone, no repo modification).

Metric: IW prompt TPM. CSV output is compatible with MilpGlobalArbiter.
Only information before an issuance hour may influence predictions.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import time
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA

HOUR = 60
ORDERS = [(1, 0, 0), (2, 0, 0), (1, 1, 1), (2, 1, 1), (0, 1, 1)]  # native repo grid


def load_trace(path: str, chunk_size: int = 300000):
    """Streaming aggregation. regions semantics match generate_causal_arima_forecasts.py."""
    aggregates = {}
    keys = set()
    max_minute = -1
    for c in pd.read_csv(path, usecols=['model_type','workload_type','arrival_timestamp','prompt_size','regions'],
                         dtype={'regions':'string'}, chunksize=chunk_size):
        c['arrival_timestamp'] = pd.to_numeric(c['arrival_timestamp'], errors='coerce')
        c['prompt_size'] = pd.to_numeric(c['prompt_size'], errors='coerce')
        c = c[c.arrival_timestamp.notna() & (c.arrival_timestamp >= 0) & c.prompt_size.notna() & (c.prompt_size >= 0)].copy()
        if c.empty:
            continue
        max_minute = max(max_minute, int(c.arrival_timestamp.max() // 60))
        c['region'] = c.regions.fillna('').astype(str).str.zfill(3).str[0].astype(int)
        keys.update((str(m), int(r)) for m, r in zip(c.model_type, c.region))
        c = c[c.workload_type.astype(str) == 'prod']
        if c.empty:
            continue
        c['minute'] = (c.arrival_timestamp // 60).astype('int64')
        g = c.groupby(['model_type','region','minute'], sort=False).prompt_size.sum()
        for (model, region, minute), tokens in g.items():
            bucket = aggregates.setdefault((str(model), int(region)), {})
            minute = int(minute)
            bucket[minute] = bucket.get(minute, 0.0) + float(tokens)
    if max_minute < 0 or not keys:
        raise ValueError('Trace empty/invalid; expected SageServe v2 CSV columns.')
    length = max_minute + 1
    series = {}
    for key in sorted(keys):
        y = np.zeros(length, dtype=float)
        for minute, total in aggregates.get(key, {}).items():
            y[minute] = total
        series[key] = y
    return series


def fit_arima(history, horizon):
    """Native v1 AIC order set; predict nonnegative TPM. Robust fallback."""
    history = np.asarray(history, dtype=float)
    if not len(history):
        return np.zeros(horizon), 'empty'
    if len(history) < 8 or np.max(history) == 0 or np.std(history) < 1e-10:
        return np.full(horizon, float(np.mean(history))), 'constant'
    best = None
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for order in ORDERS:
            try:
                fit = ARIMA(history, order=order).fit()
                if np.isfinite(fit.aic) and (best is None or fit.aic < best[0]):
                    best = (float(fit.aic), fit, order)
            except Exception:
                continue
    if best is None:
        return np.full(horizon, float(np.mean(history))), 'fallback_mean'
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        out = np.asarray(best[1].forecast(horizon), dtype=float)
    return np.clip(np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0), 0, None), str(best[2])


def remove_isolated_outliers(history, size=15, threshold=6.0):
    """Hampel-style filter on TRAIN observations only; preserve sustained runs of spikes."""
    a = np.asarray(history, dtype=float)
    b = a.copy()
    changed = 0
    for i in range(len(a)):
        lo, hi = max(0, i-size//2), min(len(a), i+size//2+1)
        local = a[lo:hi]
        median = float(np.median(local))
        sigma = 1.4826 * float(np.median(np.abs(local-median)))
        bound = median + threshold * max(sigma, median * 0.05, 1.0)
        if a[i] <= bound:
            continue
        # A multi-minute rise should be treated as a burst, not deleted as noise.
        neighbors = a[max(0, i-2):i].tolist() + a[i+1:min(len(a), i+3)].tolist()
        if sum(v > bound for v in neighbors) >= 1:
            continue
        b[i] = median
        changed += 1
    return b, changed


def weekday_at(origin_minute, start_weekday):
    return (start_weekday + int(origin_minute // 1440)) % 7


def analogous_day(history, origin, start_weekday):
    """Past-only seasonal profile, requiring prior day of SAME weekend/weekday category.
    True weekday-specific 7-day history is prioritized when available.
    """
    current_weekday = weekday_at(origin, start_weekday)
    is_weekend = current_weekday >= 5
    for days in [7, 1, 2, 3, 4, 5, 6]:
        lag = days*1440
        if origin < lag or origin - lag + 60 > len(history):
            continue
        previous_weekday = weekday_at(origin-lag, start_weekday)
        if (previous_weekday >= 5) != is_weekend:
            continue
        # history is exactly values 0 .. origin-1; minute-of-day analogy for next 60m
        return np.asarray(history[origin-lag:origin-lag+60], dtype=float), days
    return None, None


def recent_burst(history, factor=2.0):
    """Sustained last-10-min traffic versus previous 50 min; no future observations."""
    if len(history) < 60:
        return False, 1.0
    recent = float(np.mean(history[-10:]))
    reference = float(np.mean(history[-60:-10]))
    ratio = (recent + 1) / (reference + 1)
    return ratio >= factor and recent > 0, ratio


def v2_components(history, origin, start_weekday, model_cache,
                  weekend_weight=0.35, weekday_weight=0.15):
    """Blend 180-min robust ARIMA with causal same-regime seasonal analogue and burst state."""
    base = model_cache['forecast']
    idx = (origin - model_cache['trained_at'])
    if idx < 0 or idx + HOUR > len(base):
        raise ValueError('Forecast cache exhausted: retraining needed')
    pred = base[idx:idx+HOUR].copy()
    analogue, lag_days = analogous_day(history, origin, start_weekday)
    if analogue is not None:
        w = weekend_weight if weekday_at(origin, start_weekday) >= 5 else weekday_weight
        pred = (1-w) * pred + w * analogue
    # Burst persistent > 10 min is not considered a one-point outlier.
    burst, ratio = recent_burst(history)
    if burst:
        recent_level = float(np.median(history[-10:]))
        decaying_floor = recent_level * (0.5 ** (np.arange(HOUR, dtype=float) / 15.0))
        pred = np.maximum(pred, decaying_floor)
    return np.maximum(0, pred), {'analogue_lag_days':lag_days, 'burst_detected':burst, 'burst_ratio':ratio}


def forecast_v2_one(y, origin, start_weekday, cache=None,
                    weekday_retrain_hours=2, weekend_retrain_hours=1,
                    burst_factor=2.0):
    """One-hour-ahead causal v2; supports reuse of 2h ARIMA forecast on weekdays."""
    if origin < 180:
        raise ValueError('v2 requires at least 180 minutes of strictly previous history')
    history = np.asarray(y[:origin], dtype=float)
    weekend = weekday_at(origin, start_weekday) >= 5
    cadence = weekend_retrain_hours if weekend else weekday_retrain_hours
    burst, ratio = recent_burst(history, factor=burst_factor)
    due = (cache is None or origin >= cache['trained_at'] + cadence*HOUR
           or origin + HOUR > cache['trained_at'] + len(cache['forecast'])
           or burst and (cache is None or cache.get('burst_at_fit', False) is False))
    if due:
        cleaned, count = remove_isolated_outliers(history[-180:])
        # Give 60 extra minutes if cadence is 2h, avoiding lookahead.
        future, order = fit_arima(cleaned, max(HOUR, cadence*HOUR))
        cache = {'trained_at':origin,'forecast':future,'order':order,
                 'outliers_removed':count,'burst_at_fit':burst}
    pred, flags = v2_components(history, origin, start_weekday, cache)
    return pred, cache, {**flags,'retrained':due,'order':cache['order'],
                         'outliers_removed':cache['outliers_removed'],
                         'is_weekend':weekend}


def calc_metrics(actual, predicted):
    actual, predicted = np.asarray(actual,float), np.asarray(predicted,float)
    positive = actual > 0
    return {'mape_pct':float(100*np.mean(np.abs((predicted[positive]-actual[positive])/actual[positive]))) if positive.any() else np.nan,
            'peak_mape_pct':float(100*abs(predicted.max()-actual.max())/actual.max()) if actual.max()>0 else np.nan,
            'rmse_tpm':float(np.sqrt(np.mean((predicted-actual)**2))),
            'underpeak':int(predicted.max()<actual.max()),
            'positive_minutes':int(positive.sum())}


def evaluate(series, start_weekday, evaluation_start_hour=6, eval_last_hours=48):
    """Paired backtest. Same origins and actual future windows for v1/v2.
    Evaluated only on complete 60m hours; v2 warmup is 180m.
    """
    rows, pred_rows, artifacts = [], [], {}
    for (model, region), y in sorted(series.items()):
        hours = len(y)//HOUR
        first = max(3, int(evaluation_start_hour))
        if eval_last_hours > 0:
            first = max(first, hours-int(eval_last_hours))
        if hours <= first:
            continue
        cache = None
        # Include a couple of pre-evaluation hours to warm v2 model cache.
        warm = max(3, first-2)
        for h in range(warm, hours):
            origin = h*HOUR
            actual = y[origin:origin+HOUR]
            if len(actual) < HOUR: break
            t0=time.perf_counter()
            v2, cache, flags = forecast_v2_one(y,origin,start_weekday,cache)
            v2_time=time.perf_counter()-t0
            if h < first: continue
            t0=time.perf_counter()
            v1, old_order = fit_arima(y[origin-60:origin], HOUR)
            v1_time=time.perf_counter()-t0
            for method, pred, timing, order in [('v1',v1,v1_time,old_order),('v2',v2,v2_time,flags['order'])]:
                rows.append({'model':model,'region':region,'origin_minute':origin,
                             'weekday':weekday_at(origin,start_weekday),'is_weekend':flags['is_weekend'],
                             'method':method,'order':order,'train_predict_sec':timing,
                             'retrained':flags['retrained'] if method=='v2' else True,
                             'isolated_outliers_removed':flags['outliers_removed'] if method=='v2' else 0,
                             'burst_detected':flags['burst_detected'] if method=='v2' else False,
                             'seasonal_lag_days':flags['analogue_lag_days'] if method=='v2' else None,
                             **calc_metrics(actual,pred)})
                pred_rows.extend({'model':model,'region':region,'method':method,
                                  'origin_minute':origin,'minute':origin+j,
                                  'actual_tpm':float(actual[j]),'predicted_tpm':float(pred[j])}
                                 for j in range(HOUR))
        artifacts[(model,region)] = {'hours':hours,'evaluated_hours':max(0,hours-first)}
    if not rows:
        raise ValueError('No evaluation windows; reduce --evaluation-start-hour or use longer trace.')
    detail = pd.DataFrame(rows)
    summaries = detail.groupby(['model','region','method'],as_index=False).agg(
        mape_pct=('mape_pct','mean'),peak_mape_pct=('peak_mape_pct','mean'),
        rmse_tpm=('rmse_tpm','mean'),underpeak_rate=('underpeak','mean'),
        mean_runtime_sec=('train_predict_sec','mean'),windows=('origin_minute','nunique'))
    pivot = summaries.pivot(index=['model','region'], columns='method',values=['mape_pct','peak_mape_pct','rmse_tpm'])
    pairs = pivot.copy()
    pairs.columns = [f'{metric}_{method}' for metric,method in pairs.columns]
    pairs = pairs.reset_index()
    for metric in ['mape_pct','peak_mape_pct','rmse_tpm']:
        pairs[f'{metric}_delta_v2_minus_v1'] = pairs[f'{metric}_v2']-pairs[f'{metric}_v1']
    return detail,pd.DataFrame(pred_rows),summaries,pairs,artifacts


def write_niw_csv(trace_path, out_dir, keys, chunk_size=300000):
    """Stream NIW input as exact files expected by global_arbiter.py."""
    out_dir = Path(out_dir)
    handles = {}
    try:
        for model, r in keys:
            p = out_dir/f'final_{model}_dev_region{r}_exact.csv'
            handles[(model,r)] = p.open('w',encoding='utf-8',newline='')
            handles[(model,r)].write('arrival_timestamp,prompt_size\n')
        for c in pd.read_csv(trace_path, usecols=['model_type','workload_type','arrival_timestamp','prompt_size','regions'],
                             dtype={'regions':'string'},chunksize=chunk_size):
            c = c[c.workload_type.astype(str)=='dev'].copy()
            if c.empty: continue
            c['region'] = c.regions.fillna('').astype(str).str.zfill(3).str[0].astype(int)
            for (model,region), g in c.groupby(['model_type','region']):
                key=(str(model),int(region))
                if key in handles:
                    g[['arrival_timestamp','prompt_size']].to_csv(handles[key], header=False,index=False)
    finally:
        for f in handles.values():f.close()


def write_simulator_forecasts(series, output, start_weekday):
    """Generate complete causal forecast. Hour 0 warmup is explicitly noncausal like native repo."""
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    summary=[]
    for (model,region),y in sorted(series.items()):
        rows=[];cache=None
        for h in range(math.ceil(len(y)/HOUR)):
            origin=h*HOUR
            if origin==0:
                # Original repo convention; NOT used in evaluation.
                pred=np.full(HOUR,float(np.mean(y[:HOUR])))
                flags={'order':'warmup_noncausal','retrained':True,'burst_detected':False}
            elif origin < 180:
                pred,order=fit_arima(y[max(0,origin-60):origin],HOUR)
                flags={'order':order,'retrained':True,'burst_detected':False}
            else:
                pred,cache,flags=forecast_v2_one(y,origin,start_weekday,cache)
            pred=pred[:min(HOUR,len(y)-origin)]
            for j,p in enumerate(pred):
                rows.append({'Time':(origin+j)*60,'Predicted':round(float(p),2),
                             'issue_time':origin*60,'order':str(flags['order'])})
        pd.DataFrame(rows).to_csv(output/f'final_{model}_prod_1minute_region{region}_arima.csv',index=False)
        summary.append({'model':model,'region':region,'minutes':len(y),'forecast':'v2'})
    return summary


def main():
    p=argparse.ArgumentParser(description='SageServe Forecast v2: retraining, robust burst and weekend features')
    p.add_argument('--trace',required=True)
    p.add_argument('--out',default='results/forecast_v2')
    p.add_argument('--start-weekday',type=int,choices=range(7),required=True,
                   help='0=Monday ... 6=Sunday for minute 0 of the trace; REQUIRED to prevent incorrect weekend labels')
    p.add_argument('--evaluation-start-hour',type=int,default=6)
    p.add_argument('--eval-last-hours',type=int,default=48,help='0 means all eligible hours')
    p.add_argument('--write-simulator-forecasts',action='store_true')
    p.add_argument('--write-niw',action='store_true',help='write dev exact CSVs for simulator (requires --write-simulator-forecasts)')
    a=p.parse_args()
    if a.write_niw and not a.write_simulator_forecasts:p.error('--write-niw requires --write-simulator-forecasts')
    t0=time.perf_counter()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    series=load_trace(a.trace)
    detail,pred,summary,pairs,artifacts=evaluate(series,a.start_weekday,a.evaluation_start_hour,a.eval_last_hours)
    detail.to_csv(out/'mape_v1_v2_detail.csv',index=False)
    pred.to_csv(out/'minute_predictions_v1_v2.csv',index=False)
    summary.to_csv(out/'mape_v1_v2_by_pair.csv',index=False)
    pairs.to_csv(out/'mape_v1_v2_comparison.csv',index=False)
    group = detail.groupby(['method'],as_index=False).agg(
        mape_pct=('mape_pct','mean'),peak_mape_pct=('peak_mape_pct','mean'),
        rmse_tpm=('rmse_tpm','mean'),underpeak_rate=('underpeak','mean'),
        evaluated_windows=('origin_minute','size'))
    group.to_csv(out/'mape_v1_v2_overall.csv',index=False)
    regimes = detail.groupby(['method','is_weekend'],as_index=False).agg(
        mape_pct=('mape_pct','mean'),peak_mape_pct=('peak_mape_pct','mean'),
        rmse_tpm=('rmse_tpm','mean'),underpeak_rate=('underpeak','mean'),
        evaluated_windows=('origin_minute','size'))
    regimes.to_csv(out/'mape_v1_v2_weekday_weekend.csv',index=False)
    if a.write_simulator_forecasts:
        forecast_dir=out/'simulator_forecasts'
        write_simulator_forecasts(series,forecast_dir,a.start_weekday)
        if a.write_niw:write_niw_csv(a.trace,forecast_dir,series.keys())
    digest=hashlib.sha256()
    with Path(a.trace).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    meta={'trace':str(a.trace),'trace_sha256':digest.hexdigest(),
          'start_weekday':a.start_weekday,'models_and_regions':[list(k) for k in series],
          'evaluation_start_hour':a.evaluation_start_hour,'eval_last_hours':a.eval_last_hours,
          'metric_mape':'mean minute absolute percentage error on actual TPM > 0; mean across evaluated windows',
          'metric_peak_mape':'mean absolute percentage error of hourly maximum TPM; actual peak > 0',
          'unit':'prompt tokens per minute (TPM)','v1':'native ARIMA 60-min window and 5-order AIC search',
          'v2':'180-min robust AIC ARIMA; weekday 2h and weekend 1h refits, burst override and past-only seasonal analogue',
          'weekend_caveat':'one-week trace cannot provide a preceding same-weekday week; analogue uses same weekend/weekday class when available',
          'hour0':'warmup noncausal mean, excluded from backtest; simulator format parity',
          'by_pair':artifacts,'wall_seconds':time.perf_counter()-t0}
    # tuple keys are not JSON object keys
    meta['by_pair']={f'{m}@{r}':v for (m,r),v in artifacts.items()}
    (out/'metadata.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
    print(group.to_string(index=False)); print('\nSaved:',out)

if __name__=='__main__':main()
