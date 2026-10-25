#!/bin/bash
# Chạy một thí nghiệm của bài báo SageServe. Trace chính (ghép, vai trò T7/2025) cho mọi thí nghiệm;
# trace thứ hai (fork GitHub, vai trò T11/2024) chỉ ở nơi bài báo dùng T11/2024: §4 và §7.2.7 (nov2024).
# Dùng: bash experiments/run.sh <tên> [end_time]
# Tên: s4 | lt | chiron | sched | nov2024 | scale5 | burst | week | h100 | niw_ratio   (xem REPRODUCE.md)
# Mọi bài trong một thí nghiệm chạy song song; kết quả ở results/<tên>/<cấu hình>/
set -e
cd "$(dirname "$0")/.."
PY=${PY:-python}
EXP=$1
END=${2:-86400}
PERF="performance_model.db_path=data/perf_model_4models.csv"
THETA=""
ROOT=${RESULTS_ROOT:-results}      # vd. RESULTS_ROOT=D:/SageServe_results khi ổ chứa repo không đủ chỗ
arb() { echo "controller.regions.0.arbiter=$1 controller.regions.1.arbiter=$1 controller.regions.2.arbiter=$1"; }
run() {  # run <thư mục kết quả> <override...>
  local out=$1; shift
  mkdir -p "$(dirname "$out")"
  $PY run.py $PERF end_time=$END output_dir=$out "$@" > $out.out 2>&1 &
}
lt_runs() {  # lt_runs <trace> <thư mục> [controller]
  local T=$1 D=$2 C=${3:-us3-4models}
  local COMMON="trace=random_trace trace.filename=$T controller=$C global_arbiter.arima_traces=traces/forecasts/$T $THETA"
  run $D/reactive $COMMON long_term_scaling=False
  run $D/lt_i $COMMON long_term_scaling=True $(arb global_arbiter_short_term_scaling)
  run $D/lt_u $COMMON long_term_scaling=True $(arb global_arbiter_memory_utilization)
  run $D/lt_ua $COMMON long_term_scaling=True $(arb global_arbiter_ARIMA_checking)
}
case $EXP in
  s4)         # §4, Fig. 8, Table 1: Siloed vs Unified, West, thứ Ba – bài báo dùng trace T11/2024 -> trace thứ hai
    T="trace=random_trace trace.filename=fork_s4_westus scaling_level=1"
    run $ROOT/s4/unified $T controller=us1-4models
    run $ROOT/s4/siloed $T controller=us1-4models-siloed siloed=True ;;
  lt)         # §7.2.1-7.2.2, Fig. 11: Reactive / LT-I / LT-U / LT-UA, 3 vùng
    lt_runs composed_day_3regions $ROOT/lt ;;
  chiron)     # §7.2.3: Chiron 10/5/5, Θ = 0,6
    run $ROOT/chiron/chiron trace=random_trace trace.filename=composed_day_3regions controller=us3-4models-chiron siloed=True ;;
  sched)      # §7.2.6, Fig. 15: FCFS / EDF / PF / DPA, trace chính 3 vùng giờ 12–15h, năng lực cố định để có tranh chấp
              # như bài báo (FCFS TTFT Q3 ~5,6 s); 2 kịch bản SLA IW-N: 60 s (§2.2) và 6 s (suy từ số liệu §7.2.6)
    for sc in "composed_day_3regions_12to15 sla60" "composed_day_3regions_12to15_iwn6 sla6"; do
      set -- $sc
      for p in fcfs edf pf dpa; do
        run $ROOT/sched/$2/$p trace=random_trace trace.filename=$1 controller=us3-4models-fixed75 short_term_scaling=False queue_policy=$p
      done
    done ;;
  nov2024)    # §7.2.7 "Validation for Nov, 2024 Trace": 4 chiến lược trên trace thứ hai, 3 vùng
    THETA="global_arbiter.theta_file=data/theta_tps_fork.csv"     # θ đo trên Reactive của chính trace này (request dài hơn)
    lt_runs fork_day_3regions $ROOT/nov2024 ;;
  scale5)     # §7.2.5 (thay thế): thêm mô hình thứ 5 llama4-sub (profile llama2-70b, luồng thật thứ Tư)
    lt_runs composed_day_3regions_5models $ROOT/scale5 us3-5models ;;
  week)       # §7.2.7: cả tuần (thứ Sáu 10/5 → thứ Năm 16/5/2024), 4 chiến lược
    END=${2:-604800}
    lt_runs composed_week_3regions $ROOT/week ;;
  burst)      # §7.2.7: burst x8 (cần inject_burst.py + dự báo, xem REPRODUCE.md)
    lt_runs composed_day_3regions_burst8 $ROOT/burst ;;
  h100)       # Phụ lục A: cụm H100 (θ riêng, xem REPRODUCE.md)
    THETA="global_arbiter.theta_file=data/theta_tps_h100.csv"
    lt_runs composed_day_3regions $ROOT/h100 us3-4models-h100 ;;
  niw_ratio)  # Phụ lục A: IW:NIW 9:1 và 1:1
    lt_runs composed_day_3regions_niw9 $ROOT/niw9
    lt_runs composed_day_3regions_niw1 $ROOT/niw1 ;;
  *) echo "Tên thí nghiệm không hợp lệ: $EXP"; exit 1 ;;
esac
wait
echo "[+] Xong $EXP"
