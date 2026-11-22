import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import forecast_v2 as v2


def test_no_future_leakage(monkeypatch):
    # No access to y[origin:] in forecast_v2_one; identical output despite future changes.
    monkeypatch.setattr(v2, 'fit_arima', lambda history,horizon:(np.full(horizon,np.mean(history)), '(1,0,0)'))
    a=np.full(600, 100.0)
    b=a.copy();b[360:]=999999
    p1,_,flags1=v2.forecast_v2_one(a,360,0)
    p2,_,flags2=v2.forecast_v2_one(b,360,0)
    np.testing.assert_allclose(p1,p2)
    assert flags1 == flags2


def test_outlier_preserves_burst():
    x=np.full(180,100.0)
    x[20]=9999
    x[130:144]=8000
    cleaned, count=v2.remove_isolated_outliers(x)
    assert cleaned[20]==100.0
    assert np.all(cleaned[134:140]==8000)
    assert count>=1


def test_weekend_same_regime():
    y=np.ones(3*1440+60)
    # Saturday at day 1, Sunday at day 2, start weekday Friday
    saturday_pred,days=v2.analogous_day(y[:2*1440],2*1440,4)
    assert days==1 and len(saturday_pred)==60
    sat,days=v2.analogous_day(y[:1440],1440,4)
    assert sat is None


def test_retrain_schedule(monkeypatch):
    count=[]
    def fit(x,h):
        count.append((len(x),h))
        return np.full(h,100.),'mock'
    monkeypatch.setattr(v2,'fit_arima',fit)
    y=np.full(2000,100.)
    # Mon origin 180, 240, 300 => fit, reuse, fit (2 hour weekday cadence)
    cache=None
    for origin in [180,240,300]:
        pred,cache,flags=v2.forecast_v2_one(y,origin,0,cache)
        assert len(pred)==60
    assert len(count)==2
    # Sat origin 180 with Fri start => retrain horizon 60
    v2.forecast_v2_one(y,1620,4,None)
    assert count[-1][1]==60


def test_horizon_and_mape():
    r=v2.calc_metrics([0,10,20],[100,15,10])
    assert abs(r['mape_pct']-50)<1e-8
    assert r['positive_minutes']==2
    assert r['peak_mape_pct']==400


def test_output_schema_and_niw(tmp_path,monkeypatch):
    monkeypatch.setattr(v2,'fit_arima',lambda history,horizon:(np.full(horizon,42.),'mock'))
    series={('bloom-176b',0):np.full(360,50.)}
    v2.write_simulator_forecasts(series,tmp_path,0)
    f=pd.read_csv(tmp_path/'final_bloom-176b_prod_1minute_region0_arima.csv')
    assert list(f.columns)==['Time','Predicted','issue_time','order']
    assert len(f)==360
    assert (f.Time.diff().dropna()==60).all()
    assert (f.issue_time<=f.Time).all()


def test_streaming_trace_region(tmp_path):
    data=pd.DataFrame([
        ['m','prod',59,10,'021'], ['m','prod',61,20,'021'],
        ['m','dev',61,30,'021'], ['m','prod',121,40,'102']
    ],columns=['model_type','workload_type','arrival_timestamp','prompt_size','regions'])
    file=tmp_path/'small.csv';data.to_csv(file,index=False)
    series=v2.load_trace(str(file),chunk_size=2)
    assert series[('m',0)].tolist()==[10,20,0]
    assert series[('m',1)].tolist()==[0,0,40]
    v2.write_niw_csv(str(file),tmp_path,series.keys(),chunk_size=2)
    f=pd.read_csv(tmp_path/'final_m_dev_region0_exact.csv')
    assert len(f)==1 and f.prompt_size.iloc[0]==30
