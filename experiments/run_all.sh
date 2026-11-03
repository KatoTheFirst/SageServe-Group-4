#!/bin/bash
# Pha 4: mọi thí nghiệm trên trace v2. Tối đa 12 bài cùng lúc: week chiếm 4, các đợt còn lại chiếm tối đa 8.
# Dùng: PY=... RESULTS_ROOT=D:/SageServe_results/v2/full bash experiments/run_all.sh
cd "$(dirname "$0")/.."
log() { echo "$(date '+%d/%m %H:%M:%S') $*" >> "$RESULTS_ROOT/run_all.log"; }
mkdir -p "$RESULTS_ROOT"
( log "bắt đầu week"; bash experiments/run.sh week; log "xong week" ) &
week=$!
for batch in "lt nov2024" "burst h100" "scale5 s4 chiron" "niw_ratio" "sched"; do
  log "bắt đầu đợt: $batch"
  pids=()
  for e in $batch; do bash experiments/run.sh $e & pids+=($!); done
  wait "${pids[@]}"
  log "xong đợt: $batch"
done
wait $week
log "XONG"
