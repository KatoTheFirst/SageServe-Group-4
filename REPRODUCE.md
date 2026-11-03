# Tái hiện SageServe (arXiv 2502.14617v3) – hướng dẫn cho nhóm

Code ở nhánh này đã được sửa để chạy **theo bài báo**. Mỗi thí nghiệm dưới đây ghi: lệnh chạy, lệnh phân tích, và
**hướng kết quả của bài báo** để đối chiếu (so theo xu hướng/kết luận, không ép khớp con số).

## 1. Môi trường

```bash
conda create -n sim python=3.11 && conda activate sim
pip install -r requirements.txt
python -m pytest            # toàn bộ khoảng 5 phút, gồm mô phỏng end-to-end
```

Windows: đặt `PYTHONIOENCODING=utf-8`. Runner dùng biến `PY` (mặc định `python`), ví dụ
`PY=E:/Anaconda_XSTK/envs/sim/python.exe bash experiments/run.sh lt`.

## 2. Trace

**Từ 3/11/2026, mọi thí nghiệm dùng trace v2** (`sha256sum -c traces/SHA256SUMS_v2`). Trace v2 sinh từ v1 bằng `make_trace_v2.py`; mỗi cờ sửa đúng một cổng trượt của `TRACE_SPEC.md` (D2, D3, D8 trong `DECISIONS.md`). Chấm trace: `python qualify_trace.py <trace> --role t7|t11 ...`.

| Trace v2 | Lệnh (từ trace v1 cùng tên) |
|---|---|
| `composed_day_3regions_v2`, `_niw9_v2`, `_niw1_v2`, `_5models_v2` | `python make_trace_v2.py traces/<v1>.csv traces/<v2>.csv --iwn_diurnal 0.6 --niw_sigma 0.22` |
| `composed_week_3regions_v2` | như trên, thêm `--fill_week_iwn` |
| `fork_day_3regions_v2` | `python make_trace_v2.py traces/fork_day_3regions.csv traces/fork_day_3regions_v2.csv --region_share 0.31 0.31 0.38 --clip_max 9 --spikes IW 1.77 1.77 --spikes NIW 2.5 3.75` |
| `fork_s4_westus_v2` | `python make_trace_v2.py traces/fork_s4_westus.csv traces/fork_s4_westus_v2.csv --niw_ratio 7 --clip_max 9 --spikes IW 1.77 1.77 --spikes NIW 2.5 3.75` |
| `composed_day_3regions_burst8_v2` | `python inject_burst.py traces/composed_day_3regions_v2.csv traces/composed_day_3regions_burst8_v2.csv` |
| `*_12to15_v2` | `python cut_trace.py traces/<v2>.csv 12 15 traces/<tên>_12to15_v2.csv` |
| `composed_day_3regions_12to15_iwn6_v2` | bản cắt trên, đặt `sla` = 6 cho dòng `scenario == "IW-N"` |

Dự báo: `python generate_causal_arima_forecasts.py --trace traces/<v2>.csv --output_dir traces/forecasts/<v2>`. Đã kiểm sinh lại `composed_day_3regions_v2`, `fork_day_3regions_v2`, `fork_s4_westus_v2`: trùng hash.

θ v2 (`benchmark_theta.py`, cách đo ở dưới): A100 `data/theta_tps_v2.csv` Bloom 386,42, Llama-2 976,26; H100 `data/theta_tps_h100_v2.csv` 549,11 / 1361,78; trace thứ hai `data/theta_tps_fork_v2.csv` 1209,56 / 3122,88. Mô hình khác giữ θ cũ (D9).

Phần dưới mô tả trace v1 (giữ nguyên, kiểm bằng `sha256sum -c traces/SHA256SUMS`).

**Lấy trace nhanh (khuyên dùng):** các trace đã đóng băng nằm ở GitHub Release `traces-v1` của repo (dạng .csv.gz, 264 MB):
`python fetch_traces.py` – tự tải, giải nén vào `traces/` và kiểm sha256. Dự báo ARIMA đi kèm đã có
sẵn trong `traces/forecasts/`. Chỉ cần đọc phần dưới nếu muốn tự sinh lại trace từ dữ liệu thô.

Bài báo có hai trace: **T7/2025** (mặc định cho §7) và **T11/2024** (dùng ở §4 và mục "Validation for Nov, 2024 Trace" của §7.2.7).
- **Trace chính** – vai trò T7/2025 – ghép từ nguồn mở (`compose_trace.py`): IW = Azure LLM 2024 (code → IW-F, conv → IW-N),
  mô hình theo tỉ trọng ServeGen, vùng theo ma trận nhu cầu Fig. 4, NIW = batch ServeGen, IW:NIW = 3:1.
- **Trace thứ hai** – vai trò T11/2024 – bộ sinh của fork GitHub SreenathKarthick11/Sage-Serve (`fork_trace.py`,
  mã gốc MIT trong `third_party/fork_trace_sim/`). **Chỉ dùng ở nơi bài báo dùng T11/2024.**
Dữ liệu thô: `python download_azure_traces.py`, `python download_servegen.py`.

| File | Lệnh sinh | Dùng cho |
|---|---|---|
| `fork_s4_westus.csv` (trace thứ hai) | `python fork_trace.py --rate_scale 0.024 --start_day 1 --days 1 --regions 0 --output_csv traces/fork_s4_westus.csv` | §4 (West, thứ Ba; tải để Bloom Unified đỉnh ~20 máy như Fig. 8a) |
| `fork_day_3regions.csv` (trace thứ hai) | `python fork_trace.py --rate_scale 0.024 --start_day 1 --days 1 --output_csv traces/fork_day_3regions.csv` | §7.2.7 T11/2024 (cùng tải với §4, qua G10) |
| `composed_s4_westus.csv` | `python compose_trace.py --days 1 --start_day 4 --single_region --niw_ratio 7 --sample_frac 0.17524 --output_scale 16 --output_csv traces/composed_s4_westus.csv` | nguồn của bản cắt giờ cao điểm |
| `composed_day_3regions.csv` | `python compose_trace.py --days 1 --start_day 4 --niw_ratio 3 --sample_frac 0.17524 --output_scale 16 --output_csv traces/composed_day_3regions.csv` | §7.2.1–7.2.4 |
| `composed_week_3regions.csv` | như trên với `--days 7 --start_day 0` | §7.2.7 cả tuần |
| `composed_day_3regions_burst8.csv` | `python inject_burst.py traces/composed_day_3regions.csv traces/composed_day_3regions_burst8.csv` | §7.2.7 burst |
| `composed_day_3regions_niw{9,1}.csv` | như `composed_day_3regions` với `--niw_ratio 9` / `--niw_ratio 1` | Phụ lục A |
| `composed_day_3regions_12to15.csv` | `python cut_trace.py traces/composed_day_3regions.csv 12 15 traces/composed_day_3regions_12to15.csv` | §7.2.6, đo θ |
| `composed_day_3regions_12to15_iwn6.csv` | bản trên với `sla` của IW-N = 6 | §7.2.6 kịch bản phụ |
| `composed_day_3regions_5models.csv` | `composed_day_3regions` + phần llama2-70b của ngày thứ Tư (`--start_day 5`) đổi nhãn `llama4-sub` | §7.2.5 (thay thế) |

**Vì sao `--output_scale 16`:** output của Azure 2024 rất ngắn (trung vị ~25 token) nên request gần như không giữ bộ nhớ KV;
simulator khi đó không phải co giãn và mọi chiến lược ra kết quả trùng nhau (đã kiểm: kể cả 12M request/ngày). Nhân output
IW x16 (trung vị 304, 79% vẫn < 1k – đúng §3/Fig. 10) là mức nhỏ nhất qua cổng **G10** (đo trực tiếp:
`python check_g10.py results/<bài Reactive>` – Bloom, Llama-2 cần ≥ 4 instance lúc cao điểm ở mọi vùng; x4, x8 trượt).
Trong từng tầng, output gần như không đổi theo giờ (IW-F trung vị ~128, IW-N ~624), nhưng tỉ lệ hai tầng đổi mạnh: IW-N chiếm 89% lúc 8h, 41% lúc 20h. Tỉ lệ output/input vì vậy dao động 0,29–0,63 trong ngày, nhiều khả năng lớn hơn trace thật của bài báo (chưa đối chiếu được). Trace thứ hai phẳng (0,11–0,12).

**θ cho ILP** (§2.1 "input TPS achieved at a target latency"; §5 "by benchmarking"):
`python benchmark_theta.py <trace> <controller 1 vùng> <file θ> --out <thư mục> [--hour H] [--models ...]`. 6 instance cố định, không co giãn, Poisson, tăng tải đến khi TTFT P95 của IW vượt Table 1 (Bloom 12,9 s; Llama-2 34,5 s; Llama-3.x 1 s). Trần thang tải là tổng tải IW giờ cao nhất: trên đó 1 instance đã đủ, θ không còn ảnh hưởng ILP.

| Trace | Mức tải đo θ Bloom, Llama-2 | Bloom | Llama-2 | Llama-3.1 | Llama-3.2 |
|---|---|---:|---:|---:|---:|
| Chính, A100 (`data/theta_tps.csv`) | giờ 8 (`--hour 8`) | 338,62 | 976,26 | 4145,95 | ≥ 16940,66 |
| Chính, H100 (`data/theta_tps_h100.csv`) | giờ 8 | 462,24 | 1361,78 | ≥ 4440,89 | ≥ 476,84 |
| Thứ hai, A100 (`data/theta_tps_fork.csv`) | cả ngày | 1126,8 | 3107,76 | ≥ 6938,89 | ≥ 2273,74 |

"≥" là chưa trượt ở mức cao nhất đã đo. Bloom và Llama-2 của trace chính đo ở giờ có tỉ lệ output/input cao nhất; đây là lựa chọn của bản tái hiện vì bài báo không nói tỉ lệ nào. θ đo theo tỉ lệ cả ngày (Bloom 528, Llama-2 1315) làm hỏng SLA: Llama-2 LT-U TTFT P95 7073 s, vi phạm IW 53%. θ của Bloom và Llama-2 vẫn cao hơn §2.1 (50–177, 68–293), nguyên nhân chưa kiểm chứng.

`analyze_capacity.py` (TPS/instance khi bộ nhớ 60–80%) là cách đo cũ, không còn dùng cho ILP.

Mỗi trace dùng LT cần dự báo ARIMA-60 (Phụ lục B):
`python generate_causal_arima_forecasts.py --trace traces/<tên>.csv --output_dir traces/forecasts/<tên>`

Cắt giờ cao điểm: `python cut_trace.py traces/composed_day_3regions.csv 12 15 traces/composed_day_3regions_12to15.csv`

## 3. Thí nghiệm

`bash experiments/run.sh <tên> [end_time giây, mặc định 86400]`. Mỗi bài cả ngày ghi khoảng 1 GB, bài cả tuần khoảng 30 GB cho 4 bài;
khi ổ chứa repo không đủ chỗ: `RESULTS_ROOT=D:/SageServe_results bash experiments/run.sh week`. Thời gian đo trên laptop 12 nhân: 4 bài song song cả ngày
3 vùng ≈ 3 giờ; §4 cả ngày ≈ 1,5–3 giờ mỗi bài.

**Kết quả hiện hành trên trace v2: `RESULTS.md`** (mỗi tuyên bố kèm lệnh tái tạo; `bash experiments/run_all.sh` chạy toàn bộ). Cột "Kết quả" dưới đây là số trên trace v1, giữ để đối chiếu.

Cột "Kết quả" (v1): các bài LT chạy lại 2/11/2026 với θ ở trên và LT-UA so tải IW theo vùng gốc; Reactive, `s4`, `chiron`, `sched` giữ số 27/10 (bài Reactive `lt` chạy lại trùng từng byte). Số % là instance-hours so với Reactive, bỏ giờ 0. Lãng phí: `analyze_waste.py --skip_hours 1`.

**Vì sao SLA của LT xấu hơn Reactive khi tải tăng dốc:** ARIMA-60 (đúng Phụ lục B) dự báo trễ, đỉnh dự báo chỉ đạt 40–65% đỉnh thực trong các giờ này (`forecast_log.csv`); LT-I, LT-U không được vượt mục tiêu ILP (§6.4, §7.2.7) và LT-UA chỉ tăng thêm khi tải ≥ 5x dự báo. Reactive không bị giới hạn này.

| Tên | Bài báo | Phân tích | Hướng kết quả phải thấy | Kết quả |
|---|---|---|---|---|
| `s4` | §4, Fig. 8, Table 1 | `python analyze_s4.py results/s4/unified results/s4/siloed --out results/s4/compare` | Unified ít hơn Siloed ~35%, độ trễ không xấu hơn | ✔ −32,7%, độ trễ ngang |
| `lt` | §7.2.1–7.2.2, Fig. 11 | `python analyze_s4.py results/lt/reactive results/lt/lt_i results/lt/lt_u results/lt/lt_ua --skip_hours 1 --out results/lt/compare` | LT-I ≤ LT-UA ≤ LT-U < Reactive (−24/−23/−20%); LT-U/UA không xấu độ trễ | ½ LT-I / LT-U / LT-UA −5,9 / −3,9 / −5,0% (Llama-2: −15,5 / −14,0 / −15,1%; Bloom: −4,6 / −2,1 / −3,4%). Vi phạm IW Bloom ngang Reactive (14,1–14,3%); Llama-2 7,5 → 13,6 / 9,3 / 9,7%, TTFT P95 2,6 → 77,2 / 10,6 / 11,8 s |
| (lt) | §7.2.4, Fig. 13b | `python analyze_waste.py results/lt/reactive results/lt/lt_i results/lt/lt_u results/lt/lt_ua --skip_hours 1` | LT giảm ~70% GPU-giờ lãng phí khi tăng máy | ½ LT-U −30%, LT-UA −40%, ✘ LT-I +87% |
| `chiron` | §7.2.3 | `python analyze_s4.py results/lt/reactive results/chiron/chiron --skip_hours 1 --out results/chiron/compare` | Chiron ~3x Reactive, độ trễ đuôi không tốt hơn, dùng phần cứng kém hơn | ✔ 2,74x (Llama-2 3,9x; bài báo 3,2x) |
| `scale5` | §7.2.5 (thay thế) | như `lt` với `results/scale5/*` | mô hình thêm vào: ít instance-hours hơn và độ trễ tốt hơn Reactive | ½ llama4-sub −13,6 / −12,7 / −16,2% instance-hours; ✘ vi phạm 8,7 → 13,8 / 13,6 / 14,0%, TTFT P95 2,7 → 222–242 s (tải tăng gấp đôi lúc 12h, ARIMA đạt 41% đỉnh). Tổng −7,3 / −6,2 / −6,6% |
| `sched` | §7.2.6, Fig. 15 | `python analyze_sched.py results/sched/sla60/{fcfs,edf,pf,dpa}` (và `sla6`) | FCFS: IW-F vi phạm > IW-N; PF ưu tiên IW-F, IW-N trả giá; EDF, DPA ở giữa/điều chỉnh được | ✔ hướng, biên độ nhỏ (1–3 điểm) |
| `nov2024` | §7.2.7 (T11/2024) | như `lt` với `results/nov2024/*` | Llama 2: Reactive 302, LT-I 227, LT-U 248, LT-UA 233 (~−25%) | ½ hướng: −19,1 / −13,9 / −14,0% (Llama-2 −18,1 / −12,5 / −12,7%); ✘ độ trễ: vi phạm IW Bloom 39,3 → 55,7 / 52,5 / 52,5%, Llama-2 20,0 → 48,4 / 37,5 / 37,5%, TTFT P95 Llama-2 3,6 → 702–734 s (tải tăng dốc 6–10h). Lãng phí −75 / −76 / −76% |
| `burst` | §7.2.7 | như `lt` với `results/burst/*` | LT-UA xử lý burst tốt hơn LT-I/LT-U | ✘ LT-UA không hơn LT-U: −13,5 / −13,5% (LT-I −25,1%), vi phạm IW Llama-2 40,3 / 38,4% (LT-I 44,6%, Reactive 22,1%), TTFT P95 ~2600 s (Reactive 479 s). Lãng phí giảm 82–85% |
| `week` | §7.2.7 cả tuần | như `lt` với `results/week/*` | LT-U ≈ LT-UA ngày thường, LT-UA tốt hơn cuối tuần chưa chạy với θ mới (số cũ không còn hợp lệ). Chạy ~11 giờ |
| `h100` | Phụ lục A | như `lt` | A100: LT-UA tiết kiệm ~28% so với Reactive (nhiều hơn H100 vì A100 tải mô hình lâu hơn) | H100 LT-I −7,7 / LT-U −6,4 / LT-UA −7,5% (Llama-2 −17,9 / −16,9 / −19,0%), SLA gần Reactive; ✘ A100 (LT-UA −5,0%) không tiết kiệm hơn H100 (cùng 600 s khởi động – bài báo không cho thời gian tải A100) |
| `niw_ratio` | Phụ lục A | như `lt` | xu hướng tiết kiệm giữ nguyên khi đổi IW:NIW | ✔ 9:1: −4,2 / −4,3 / −5,0%; 1:1: −8,4 / −3,8 / −4,0%. Ở 1:1, NIW chỉ hoàn thành 86–89% trong ngày |
| – | Phụ lục B, Fig. 17 | `python compare_forecasters.py traces/composed_day_3regions.csv` | MA nhanh nhưng kém; TVAR, HMM chính xác hơn ARIMA nhưng chậm hơn nhiều | ✔ MA 27%, ARIMA 25%, TVAR 24,5% (~20x chậm), HMM ~4x chậm |

Biểu đồ cho slide: `python plot_slides.py nv1 results/s4/unified results/s4/siloed --out <tiền tố>` (§4) và
`python plot_slides.py nv2 <bài online> <bài offline> --out <tiền tố>` (Load Predictor).

`python check_paper_rules.py <kết quả> <trace> [--siloed]` kiểm tra các quy tắc vận hành (ngưỡng 70/30, cooldown 15 s,
tối đa instance, NIW hoàn thành) trên kết quả bất kỳ. LT-I trượt mục cooldown là đúng thiết kế (§6.4: tăng ngay tới mục tiêu mỗi giờ).

## 4. Điều đã sửa theo bài báo (và lựa chọn khi bài báo không nói)

| Phần | Theo bài báo | Lựa chọn khi bài báo không cho số |
|---|---|---|
| Co giãn | bộ nhớ hiệu dụng > 70% thêm, < 30% bớt; cooldown 15 s; khởi động 600 s; lấy lại spot trung vị 60 s, tối đa 300 s | spot: log-normal |
| NIW | Queue Manager: < 60% đưa 1, < 50% đưa 2; NIW sau IW, ngang IW sau 10 h; Siloed: NIW vào thẳng nhóm `-d` | tín hiệu mỗi 1 s |
| ILP §5 | ràng buộc từng vùng ≥ ε·đỉnh, toàn cục ≥ đỉnh tổng, δ ≥ −n; min α·δ + σ·max(δ,0); đỉnh dự báo cả giờ tới; β = 10% tải NIW giờ trước | ε = 0,9; σ = α·600/3600; θ đo bằng `benchmark_theta.py` (mục 2) |
| Dự báo | ARIMA cửa sổ 60 phút, TPM, dự báo 60 phút, mỗi giờ (nhân quả) | giờ 0 = trung bình giờ 0 |
| Load Predictor | `global_arbiter.forecast_mode=online`: mỗi giờ huấn luyện ARIMA-60 trên TPM quan sát trong simulator (trùng `offline` – lệch ≤ 1e-6); cả hai ghi `forecast_log.csv` (đỉnh/trung bình dự báo vs thực tế theo giờ). Cửa sổ dự báo canh theo phút tròn (trước 26/10 lấy nhầm phút đầu giờ sau → kết quả LT cũ hơi cấp thừa máy khi tải tăng) | — |
| LT-I / LT-U / LT-UA | §6.4; LT-UA: 20 phút cuối giờ, tải ≥ 5x dự báo → tăng, ≤ 0,5x → giảm. Tải so sánh là input TPS của IW theo vùng gốc, cùng đại lượng với dự báo (trước 2/11 đếm cả NIW và lưu lượng chuyển vùng) | — |
| Định tuyến | chuyển vùng khi quá tải; trễ chuyển vùng 90% ≤ 500 ms, < 2% tới 2,5 s | dạng phân phối |
| Bộ lập lịch §6.5 | FCFS / EDF / PF / DPA (`queue_policy`) | τ_p = 1 s, τ_n = 5 s |
| Chiron | 10/5/5 mỗi mô hình mỗi vùng, Θ = 0,6 | profile offline từ bảng hiệu năng (batch 64) |
| GPU | bài báo không nói rõ GPU của thí nghiệm chính → giữ A100 như code gốc; H100 cho Phụ lục A | — |
| Độ trễ co giãn | instance mới phục vụ sau 600 s (khởi động) / ~60 s (lấy lại spot) – đặt ở allocator; code gốc để 0 (sẵn sàng tức thì). Trước 27/10 nhánh khởi động từ GPU spot của mô hình khác (`scaling_level: 2`) vẫn gọi `pre_start=True` nên lên tức thì | — |
| ILP: số instance hiện có | đếm cả instance đang lấy lại spot / khởi động (trước 27/10 không đếm → ILP giao thêm máy trùng) | — |
| Cooldown | chỉ 15 s giữa hai quyết định (§4); bỏ khoảng chờ "đến khi instance sẵn sàng" của code gốc (làm Reactive không tăng quá đà nên LT không còn lợi thế) | — |
| Deployment đang co giãn | đếm cả instance đang lấy lại/khởi động (`arbiter.size`), không gộp/bớt deployment còn instance chờ, router bỏ qua deployment chưa phục vụ | — |
| θ theo trace | θ đo riêng cho từng trace và GPU (mục 2) | `data/theta_tps_fork.csv`, `data/theta_tps_h100.csv` |
| §7.2.6 | tranh chấp như bài báo (FCFS TTFT Q3 ~5,6 s): năng lực cố định 0,75 x Reactive | SLA IW-N 6 s là kịch bản phụ suy từ số liệu §7.2.6 |
| §7.2.5 | Llama 4 Scout không có trong bảng hiệu năng → mô hình thứ 5 dùng profile Llama-2-70B, luồng thật ngày thứ Tư | thay thế |
