# Tái hiện SageServe (arXiv 2502.14617v3) – hướng dẫn cho nhóm

Code ở nhánh này đã được sửa để chạy **theo bài báo**. Mỗi thí nghiệm dưới đây ghi: lệnh chạy, lệnh phân tích, và
**hướng kết quả của bài báo** để đối chiếu (so theo xu hướng/kết luận, không ép khớp con số).

## 1. Môi trường

```bash
conda create -n sim python=3.11 && conda activate sim
pip install -r requirements.txt
python -m pytest            # 9 test: ILP §5, bộ lập lịch §6.5, burst
```

Windows: đặt `PYTHONIOENCODING=utf-8`. Runner dùng biến `PY` (mặc định `python`), ví dụ
`PY=E:/Anaconda_XSTK/envs/sim/python.exe bash experiments/run.sh lt`.

## 2. Trace (đã đóng băng – kiểm tra bằng `sha256sum -c traces/SHA256SUMS`)

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
Khi đó năng lực 1 instance đo được (θ) là Bloom 375, Llama-2 945 TPS – cùng cỡ §2.1 của bài báo (50–177, 68–293).

θ cho ILP: `python analyze_capacity.py results/<bài Reactive> <trace> data/theta_tps.csv` (TPS/instance khi bộ nhớ 60–80%).

Mỗi trace dùng LT cần dự báo ARIMA-60 (Phụ lục B):
`python generate_causal_arima_forecasts.py --trace traces/<tên>.csv --output_dir traces/forecasts/<tên>`

Cắt giờ cao điểm: `python cut_trace.py traces/composed_day_3regions.csv 12 15 traces/composed_day_3regions_12to15.csv`

## 3. Thí nghiệm

`bash experiments/run.sh <tên> [end_time giây, mặc định 86400]`. Mỗi bài cả ngày ghi khoảng 1 GB, bài cả tuần khoảng 30 GB cho 4 bài;
khi ổ chứa repo không đủ chỗ: `RESULTS_ROOT=D:/SageServe_results bash experiments/run.sh week`. Thời gian đo trên laptop 12 nhân: 4 bài song song cả ngày
3 vùng ≈ 3 giờ; §4 cả ngày ≈ 1,5–3 giờ mỗi bài.

| Tên | Bài báo | Phân tích | Hướng kết quả phải thấy | Kết quả hiện tại |
|---|---|---|---|---|
| `s4` | §4, Fig. 8, Table 1 | `python analyze_s4.py results/s4/unified results/s4/siloed --out results/s4/compare` | Unified ít hơn Siloed ~35%, độ trễ không xấu hơn | ✔ −32,7%, độ trễ ngang |
| `lt` | §7.2.1–7.2.2, Fig. 11 | `python analyze_s4.py results/lt/reactive results/lt/lt_i results/lt/lt_u results/lt/lt_ua --skip_hours 1 --out results/lt/compare` | LT-I ≤ LT-UA ≤ LT-U < Reactive (−24/−23/−20%); LT-U/UA không xấu độ trễ | ✔ −10,4 / −4,8 / −3,8% (Llama-2: −7,6 / −16,5 / −12,3%), độ trễ ngang |
| (lt) | §7.2.4, Fig. 13b | `python analyze_waste.py results/lt/reactive results/lt/lt_i results/lt/lt_u results/lt/lt_ua` | LT giảm ~70% GPU-giờ lãng phí khi tăng máy | ✔ LT-U −68%, LT-UA −67% |
| `chiron` | §7.2.3 | `python analyze_s4.py results/lt/reactive results/chiron/chiron --skip_hours 1 --out results/chiron/compare` | Chiron ~3x Reactive, độ trễ đuôi không tốt hơn, dùng phần cứng kém hơn | ✔ 2,7x |
| `scale5` | §7.2.5 (thay thế) | như `lt` với `results/scale5/*` | mô hình thêm vào: ít instance-hours hơn và độ trễ tốt hơn Reactive | ✔ llama4-sub LT-UA −5,2%, vi phạm 8,5→7,5% |
| `sched` | §7.2.6, Fig. 15 | `python analyze_sched.py results/sched/sla60/{fcfs,edf,pf,dpa}` (và `sla6`) | FCFS: IW-F vi phạm > IW-N; PF ưu tiên IW-F, IW-N trả giá; EDF, DPA ở giữa/điều chỉnh được | ✔ hướng, biên độ nhỏ (1–3 điểm) |
| `nov2024` | §7.2.7 (T11/2024) | như `lt` với `results/nov2024/*` | Llama 2: Reactive 302, LT-I 227, LT-U 248, LT-UA 233 (~−25%) | ✔ hướng: −10,2 / −8,6 / −8,3% (θ đo riêng cho trace này) |
| `burst` | §7.2.7 | như `lt` với `results/burst/*` | LT-UA xử lý burst tốt hơn LT-I/LT-U | ½ LT-UA −24% vs LT-U −17,5% và có tăng vượt mục tiêu khi burst; nhưng vi phạm SLA cao hơn Reactive |
| `week` | §7.2.7 cả tuần | như `lt` với `results/week/*` | LT-U ≈ LT-UA ngày thường, LT-UA tốt hơn cuối tuần | ✔ cả tuần −8,9 / −5,8 / −4,0% (LT-I/UA/U), LT-U/UA không xấu độ trễ; ✔ T2–T3 LT-U ≈ LT-UA; ✘ cuối tuần LT-UA không tốt hơn LT-U (CN: LT-U −17,0%, LT-UA −14,1%). Chạy ~7,5 giờ, ~30 GB |
| `h100` | Phụ lục A | như `lt` | A100: LT-UA tiết kiệm ~28% so với Reactive (nhiều hơn H100 vì A100 tải mô hình lâu hơn) | ✔ thứ tự: H100 LT-I −9,9 / LT-UA −5,8 / LT-U −5,6%; ✘ A100 không tiết kiệm hơn H100 (cùng 600 s khởi động – bài báo không cho thời gian tải A100) |
| `niw_ratio` | Phụ lục A | như `lt` | xu hướng tiết kiệm giữ nguyên khi đổi IW:NIW | ✔ 9:1: −8,3 / −5,2 / −4,9%; 1:1: −11,9 / −2,3 / −2,0% |
| – | Phụ lục B, Fig. 17 | `python compare_forecasters.py traces/composed_day_3regions.csv` | MA nhanh nhưng kém; TVAR, HMM chính xác hơn ARIMA nhưng chậm hơn nhiều | ✔ MA 27%, ARIMA 25%, TVAR 24,5% (~20x chậm), HMM ~4x chậm |

Biểu đồ cho slide: `python plot_slides.py nv1 results/s4/unified results/s4/siloed --out <tiền tố>` (§4) và
`python plot_slides.py nv2 <bài online> <bài offline> --out <tiền tố>` (Load Predictor).

`python check_paper_rules.py <kết quả> <trace> [--siloed]` kiểm tra các quy tắc vận hành (ngưỡng 70/30, cooldown 15 s,
tối đa instance, NIW hoàn thành) trên kết quả bất kỳ.

## 4. Điều đã sửa theo bài báo (và lựa chọn khi bài báo không nói)

| Phần | Theo bài báo | Lựa chọn khi bài báo không cho số |
|---|---|---|
| Co giãn | bộ nhớ hiệu dụng > 70% thêm, < 30% bớt; cooldown 15 s; khởi động 600 s; lấy lại spot trung vị 60 s, tối đa 300 s | spot: log-normal |
| NIW | Queue Manager: < 60% đưa 1, < 50% đưa 2; NIW sau IW, ngang IW sau 10 h; Siloed: NIW vào thẳng nhóm `-d` | tín hiệu mỗi 1 s |
| ILP §5 | ràng buộc từng vùng ≥ ε·đỉnh, toàn cục ≥ đỉnh tổng, δ ≥ −n; min α·δ + σ·max(δ,0); đỉnh dự báo cả giờ tới; β = 10% tải NIW giờ trước | ε = 0,9; σ = α·600/3600; θ = TPS 1 instance ở bộ nhớ 60–80% trên bài Reactive của trace chính (`analyze_capacity.py`) |
| Dự báo | ARIMA cửa sổ 60 phút, TPM, dự báo 60 phút, mỗi giờ (nhân quả) | giờ 0 = trung bình giờ 0 |
| Load Predictor | `global_arbiter.forecast_mode=online`: mỗi giờ huấn luyện ARIMA-60 trên TPM quan sát trong simulator (trùng `offline` – lệch ≤ 1e-6); cả hai ghi `forecast_log.csv` (đỉnh/trung bình dự báo vs thực tế theo giờ). Cửa sổ dự báo canh theo phút tròn (trước 26/10 lấy nhầm phút đầu giờ sau → kết quả LT cũ hơi cấp thừa máy khi tải tăng) | — |
| LT-I / LT-U / LT-UA | §6.4; LT-UA: 20 phút cuối giờ, tải ≥ 5x dự báo → tăng, ≤ 0,5x → giảm | — |
| Định tuyến | chuyển vùng khi quá tải; trễ chuyển vùng 90% ≤ 500 ms, < 2% tới 2,5 s | dạng phân phối |
| Bộ lập lịch §6.5 | FCFS / EDF / PF / DPA (`queue_policy`) | τ_p = 1 s, τ_n = 5 s |
| Chiron | 10/5/5 mỗi mô hình mỗi vùng, Θ = 0,6 | profile offline từ bảng hiệu năng (batch 64) |
| GPU | bài báo không nói rõ GPU của thí nghiệm chính → giữ A100 như code gốc; H100 cho Phụ lục A | — |
| Độ trễ co giãn | instance mới phục vụ sau 600 s (khởi động) / ~60 s (lấy lại spot) – đặt ở allocator; code gốc để 0 (sẵn sàng tức thì) | — |
| Cooldown | chỉ 15 s giữa hai quyết định (§4); bỏ khoảng chờ "đến khi instance sẵn sàng" của code gốc (làm Reactive không tăng quá đà nên LT không còn lợi thế) | — |
| Deployment đang co giãn | đếm cả instance đang lấy lại/khởi động (`arbiter.size`), không gộp/bớt deployment còn instance chờ, router bỏ qua deployment chưa phục vụ | — |
| θ theo trace | θ đo trên bài Reactive của chính trace (trace thứ hai có request dài hơn: θ gấp ~2,7 lần) | `data/theta_tps_fork.csv` |
| §7.2.6 | tranh chấp như bài báo (FCFS TTFT Q3 ~5,6 s): năng lực cố định 0,75 x Reactive | SLA IW-N 6 s là kịch bản phụ suy từ số liệu §7.2.6 |
| §7.2.5 | Llama 4 Scout không có trong bảng hiệu năng → mô hình thứ 5 dùng profile Llama-2-70B, luồng thật ngày thứ Tư | thay thế |
