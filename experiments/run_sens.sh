#!/bin/bash
# Pha 3 (SENSITIVITY.md): độ nhạy trên bản cắt v2 12–15h (3 giờ), mỗi bài một yếu tố. Tối đa 12 bài cùng lúc.
# Dùng: PY=... bash experiments/run_sens.sh sens|sens2 [thư mục kết quả]
#   sens  -> D:/SageServe_results/v2/sens : nền, dạng phút phẳng/gai, khởi động 300/1200 s, Reactive chờ, ε, β, θ ±30%, tải ±50%
#   sens2 -> D:/SageServe_results/v2/sens2: burst x8 trong/ngoài 20 phút cuối giờ (có LT-UA tắt luật giảm), H100
# Cần trace sens_*: python experiments/make_sens_traces.py (script này tự gọi nếu thiếu).
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8
PY=${PY:-python}; EXP=$1; R=${2:-D:/SageServe_results/v2/$EXP}; MAX=12; BASE=composed_day_3regions_12to15_v2; TH=data/theta_tps_v2.csv
A() { echo "controller.regions.0.arbiter=$1 controller.regions.1.arbiter=$1 controller.regions.2.arbiter=$1"; }
[ -f traces/sens_burst_out.csv ] || $PY experiments/make_sens_traces.py
forecast() { for t in "$@"; do [ -d traces/forecasts/$t ] || $PY generate_causal_arima_forecasts.py --trace traces/$t.csv --output_dir traces/forecasts/$t > /dev/null 2>&1; done; }
mkdir -p $R
case $EXP in
  sens)
    forecast sens_flat sens_spike sens_rate50 sens_rate150
    $PY -c "
import pandas as pd
t=pd.read_csv('$TH')
for n,f in (('m30',.7),('p30',1.3)): t.assign(theta_tps=t.theta_tps*f).to_csv(f'$R/theta_{n}.csv',index=False)"
    go() { # go <tên> <trace> <reactive|lt_ua> [SAGE_*=..] [hydra...]
      local n=$1 t=$2 k=$3; shift 3; local env=""; while [[ "$1" == SAGE_* ]]; do env="$env $1"; shift; done
      while [ $(jobs -rp | wc -l) -ge $MAX ]; do sleep 5; done
      local mode="long_term_scaling=False"; [ $k = lt_ua ] && mode="long_term_scaling=True $(A global_arbiter_ARIMA_checking)"
      mkdir -p $R/$n
      env $env $PY experiments/run_patched.py performance_model.db_path=data/perf_model_4models.csv end_time=10800 output_dir=$R/$n/$k trace=random_trace trace.filename=$t controller=us3-4models global_arbiter.arima_traces=traces/forecasts/$t global_arbiter.theta_file=${THF:-$TH} $mode "$@" < /dev/null > $R/$n/$k.out 2>&1 &
    }
    go base $BASE reactive; go base $BASE lt_ua
    go flat sens_flat reactive; go flat sens_flat lt_ua; go spike sens_spike reactive; go spike sens_spike lt_ua
    go su300 $BASE reactive SAGE_SPIN_UP=300; go su300 $BASE lt_ua SAGE_SPIN_UP=300; go su1200 $BASE reactive SAGE_SPIN_UP=1200; go su1200 $BASE lt_ua SAGE_SPIN_UP=1200
    go wait $BASE reactive SAGE_WAIT=1
    go eps70 $BASE lt_ua global_arbiter.epsilon=0.63; go eps100 $BASE lt_ua global_arbiter.epsilon=1.0
    go b7 $BASE lt_ua SAGE_BETA=0.07; go b13 $BASE lt_ua SAGE_BETA=0.13
    THF=$R/theta_m30.csv go thm30 $BASE lt_ua; THF=$R/theta_p30.csv go thp30 $BASE lt_ua
    go r50 sens_rate50 reactive; go r50 sens_rate50 lt_ua; go r150 sens_rate150 reactive; go r150 sens_rate150 lt_ua ;;
  sens2)
    forecast sens_burst_in sens_burst_out
    go() { # go <thư mục> <trace> <controller> <θ> [hydra...]; E=SAGE_*=.. để vá
      local out=$1 t=$2 c=$3 th=$4; shift 4; mkdir -p $(dirname $R/$out)
      env ${E:-X=1} $PY experiments/run_patched.py performance_model.db_path=data/perf_model_4models.csv end_time=10800 output_dir=$R/$out trace=random_trace trace.filename=$t controller=$c global_arbiter.arima_traces=traces/forecasts/$t global_arbiter.theta_file=$th "$@" < /dev/null > $R/$out.out 2>&1 &
    }
    for n in in out; do t=sens_burst_$n
      go burst_$n/reactive $t us3-4models $TH long_term_scaling=False
      go burst_$n/lt_u $t us3-4models $TH long_term_scaling=True $(A global_arbiter_memory_utilization)
      go burst_$n/lt_ua $t us3-4models $TH long_term_scaling=True $(A global_arbiter_ARIMA_checking)
      E=SAGE_NO_DOWN=1 go burst_$n/lt_ua_nodown $t us3-4models $TH long_term_scaling=True $(A global_arbiter_ARIMA_checking)
    done
    go h100/reactive $BASE us3-4models-h100 data/theta_tps_h100_v2.csv long_term_scaling=False
    go h100/lt_ua $BASE us3-4models-h100 data/theta_tps_h100_v2.csv long_term_scaling=True $(A global_arbiter_ARIMA_checking) ;;
  *) echo "Dùng: bash experiments/run_sens.sh sens|sens2"; exit 1 ;;
esac
wait
echo "[+] Xong $EXP"
