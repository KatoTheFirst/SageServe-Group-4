# SageServe-Group-4
BTL Các chuyên đề trong truyền thông và mạng máy tính - Nhóm 4

## Hướng dẫn cho thành viên nhóm

Viết cho người không đọc code. Mọi lệnh chạy trong **Git Bash** (cài kèm Git for Windows), ở thư mục gốc repo, trừ khi ghi khác. Không dùng PowerShell: lệnh `curl`, `tr`, `sha256sum`, `source` ở dưới không chạy trong PowerShell.

### 1. Bắt đầu nhanh (5 bước)

| Bước | Lệnh | Mất bao lâu | Đúng khi |
|---|---|---|---|
| 1. Lấy code | Lần đầu: `git clone https://github.com/KatoTheFirst/SageServe-Group-4.git && cd SageServe-Group-4`. Đã có repo: `git checkout main && git pull`. Khi PR #2 chưa được gộp vào `main`, số v2.1 nằm ở nhánh `pha4-6-v2`: chạy thêm `git checkout pha4-6-v2` | dưới 1 phút (đo: 35 s) | Thư mục có `run.py`, `RESULTS.md` |
| 2. Môi trường Python 3.11 | Cách A (venv): `py -3.11 -m venv .venv && source .venv/Scripts/activate` (không có `py`: thay `py -3.11` bằng đường dẫn tới `python.exe` 3.11). Cách B (conda): `conda create -n sim python=3.11 && conda activate sim`. Sau đó: `pip install -r requirements.txt` và `export PYTHONIOENCODING=utf-8` | khoảng 5 phút (đo: tạo venv 15 s, cài 4 phút 19 s khi pip đã có sẵn gói tải về; lần đầu có thể lâu hơn) | `python --version` in `Python 3.11.x`; `pip` không báo `ERROR` |
| 3. Trace v2 và dự báo | 5 lệnh ngay dưới bảng | khoảng 1 phút (đo: 58 s) | Mọi dòng in `OK` (12 trace, 3 file θ, rồi các file dự báo), không dòng nào `FAILED` |
| 4. Kiểm thử | `python -m pytest` | khoảng 5 phút (đo: 5 phút 9 giây) | Dòng cuối `101 passed`, không có `failed` |
| 5. Chạy thử | `bash experiments/run.sh s4 300` (§4, chỉ 300 giây mô phỏng) | vài giây (đo: 6 s) | Dòng cuối `[+] Xong s4`; có `results/s4/unified/run.log` với dòng cuối chứa `TraceSimulator completed at 300`. Bài 300 s chỉ để thử máy chạy được: chưa có số để phân tích (mục 3) |

Lệnh bước 3 (tải 12 trace + dự báo từ Release `traces-v2`, khoảng 320 MB, rồi kiểm sha256):

```bash
B=https://github.com/KatoTheFirst/SageServe-Group-4/releases/download/traces-v2
for t in $(grep -o 'traces/[^ ]*_v2\.csv' traces/SHA256SUMS_v2); do curl -sSL $B/$(basename $t).gz | gunzip > $t; done
curl -sSL $B/forecasts_v2.tar.gz | tar -xz
curl -sSLO $B/SHA256SUMS_forecasts_v2
tr -d '\r' < traces/SHA256SUMS_v2 | sha256sum -c && sha256sum -c SHA256SUMS_forecasts_v2
```

Khi mở terminal mới, kích hoạt lại môi trường (`source .venv/Scripts/activate` hoặc `conda activate sim`) và `export PYTHONIOENCODING=utf-8`.

### 2. Lấy số cho bài tuần

- **Số chính thức nằm ở [RESULTS.md](RESULTS.md)** (bản v2.1, code ở tag `v2.1-fix`). Chép số từ đó và ghi nguồn là tên dòng RESULTS. Không cần chạy lại nếu chỉ lấy số.
- **Không dùng số, hình hay notebook cũ trước v2.1** (bài Tuần 5/6 trên code v2): cooldown đã sửa nên các dòng tiết kiệm Llama-2 đổi khoảng 5–9,5 điểm.
- Dòng nào còn ghi **"(số v2, chờ chạy lại v2.1)"** (ba dòng `week`) thì chưa có số mới; nếu dùng, ghi rõ là số v2.

Bảng dưới: tên thí nghiệm là tên dùng trong `experiments/run.sh`. Thời gian và RAM lấy từ nhật ký đợt chạy v2.1 (7–8/11/2026, laptop 12 nhân, 16 GB RAM, chạy chung 2–8 bài nên một bài chạy một mình có thể nhanh hơn). "không ghi": đợt đó không đo RAM từng bài.

| Thí nghiệm (`run.sh`) | Mục bài báo | Dòng RESULTS | Đầu việc Plan | Thời gian 1 bài | RAM đỉnh 1 bài |
|---|---|---|---|---|---|
| `s4` (2 bài) | §4, Fig. 8, Table 1 | §4, Fig. 8a; §4, Table 1 | T23, T25, T43 | 7–9 phút | không ghi |
| `lt` (4 bài) | §7.2.1–7.2.4, Fig. 11, 13 | §7.2.1–7.2.2 (dòng chính); §7.2.1; §7.2.2; §7.2.4 | T37, T39, T43 | 68–83 phút | không ghi |
| `chiron` (1 bài) | §7.2.3 | §7.2.3 (3 dòng) | T49 | 35 phút | không ghi |
| `scale5` (4 bài) | §7.2.5, Fig. 14 | §7.2.5 | T49 | 59–80 phút | 1,42–2,01 GB |
| `sched` (8 bài) | §7.2.6, Fig. 15 | §7.2.6 (4 dòng) | – | 10 phút | không ghi |
| `nov2024` (4 bài) | §7.2.7 (Nov 2024) | §7.2.7, Nov 2024 (2 dòng) | – | 47–76 phút | không ghi |
| `burst` (4 bài) | §7.2.7, Fig. 16a | §7.2.7, Fig. 16a; §7.2.7 burst | T49 | 55–75 phút | 1,68–2,38 GB |
| `week` (4 bài) | §7.2.7, Fig. 16b | §7.2.7 cả tuần (3 dòng, số v2) | T46 | chưa chạy ở v2.1 (v2: 9,0–11,4 giờ, 4 bài song song) | 3,68 GB (đo thử 45 phút đầu) |
| `h100` (4 bài) | Phụ lục A | Phụ lục A: A100 so với H100 | – | 40–52 phút | 1,01–1,55 GB |
| `niw_ratio` (8 bài) | Phụ lục A | Phụ lục A: IW:NIW | – | 9:1: 35–45 phút; 1:1: 91–96 phút | 9:1: 1,03–1,21 GB; 1:1: 1,97–3,38 GB |
| `oracle` (12 bài) | không có (chẩn đoán dự báo) | các dòng "oracle", "oracle_smooth" | T47 | 37–77 phút | không ghi |
| `beta`, `s4load`, `literal` | không có (chẩn đoán) | β; Table 1 theo mức tải §4; Reactive đúng chữ | T32, T46 | chưa chạy ở v2.1 (số v2) | – |
| `sens`, `sens2` (lệnh `bash experiments/run_sens.sh sens\|sens2 <thư mục>`) | độ nhạy (Pha 3) | [SENSITIVITY.md](SENSITIVITY.md); §7.2.7 bản cắt; Phụ lục A khởi động 1200 s | T46 | sens 6–24 phút; sens2 14–27 phút | sens 0,37–0,81 GB; sens2 0,54–1,11 GB |

### 3. Khi cần tự chạy một thí nghiệm

```bash
PY=python RESULTS_ROOT=<thư mục kết quả> bash experiments/run.sh <tên> [end_time]
```

- `<tên>`: một tên ở bảng mục 2. `end_time`: số giây mô phỏng, mặc định 86400 (1 ngày; `week` mặc định 604800). Mọi bài của một thí nghiệm chạy song song.
- `PY`: lệnh Python của môi trường (mặc định `python`, dùng được khi đã kích hoạt venv/conda).
- `RESULTS_ROOT`: nơi ghi kết quả, mặc định `results/` trong repo. Một bài cả ngày ghi khoảng 1 GB, `week` khoảng 30 GB cho 4 bài. Các đường dẫn `D:/...`, `E:/...` trong RESULTS.md là máy của An; **máy không có ổ D thì đặt `RESULTS_ROOT` sang ổ còn chỗ**, ví dụ `RESULTS_ROOT=C:/sage_results`, và thay `$R` trong lệnh phân tích bằng thư mục đó.
- Kết quả: `<RESULTS_ROOT>/<tên>/<cấu hình>/` (ví dụ `results/lt/lt_ua/`). File quan trọng:
  - `summary/`, `detailed/`, `memory/`: số liệu để phân tích và so bài. Bài quá ngắn như `s4 300` không có các thư mục này;
  - `sage_env.txt`: commit code (`CODE_COMMIT`) và biến môi trường của bài, dùng để biết bài chạy trên code nào;
  - `run.log` (dòng cuối `TraceSimulator completed at <giây>` là xong) và file `<cấu hình>.out` cạnh thư mục: nhật ký, xem khi lỗi.
- Phân tích: dòng RESULTS nào cũng ghi lệnh phân tích ở cột cuối. Ví dụ §4, sau khi chạy `bash experiments/run.sh s4` đủ 1 ngày (đo: 12 phút cho 2 bài song song):

  ```bash
  python analyze_s4.py results/s4/unified results/s4/siloed --out results/s4_compare
  ```

  Mất vài giây. In bảng instance-hours, TTFT, E2E theo mô hình, lưu `compare_with_paper.csv` và hình vào `results/s4_compare`. Đúng khi dòng cuối là `Tổng instance-hours: {'unified:instance_hours': 411.2, 'siloed:instance_hours': 595.8} ...`, khớp dòng §4, Fig. 8a của RESULTS (411,25 so với 595,75). Với thí nghiệm 4 chiến lược (`lt`, `nov2024`…): `python analyze_s4.py $R/<tên>/reactive $R/<tên>/lt_i $R/<tên>/lt_u $R/<tên>/lt_ua --skip_hours 1 --out $R/<tên>/compare`, với `R` là `RESULTS_ROOT` của bạn.
- So bài của mình với bài của nhóm (kết quả mô phỏng không có trên GitHub, xin An thư mục tương ứng): `python experiments/compare_runs.py <bài nhóm> <bài mình>`, ví dụ `python experiments/compare_runs.py <thư mục nhóm>/s4/unified results/s4/unified`. Đúng khi in `KẾT LUẬN: TRÙNG` (dòng "cấu hình khác ở: ['CODE_COMMIT']" là bình thường khi số trùng). In `KHÔNG TẤT ĐỊNH` (cùng cấu hình mà số khác) thì báo nhóm ngay.

### 4. Quy tắc nhóm

- Không commit thẳng vào `main`: tạo nhánh (`git checkout -b <tên-nhánh>`), đẩy lên, mở Pull Request.
- Không sửa trace, θ (`data/theta_tps*.csv`), tham số mô phỏng. Muốn đổi thì nêu trong nhóm trước và ghi vào [DECISIONS.md](DECISIONS.md) trước khi có số.
- Số đưa vào báo cáo/slide phải có nguồn: tên dòng RESULTS, hoặc lệnh đã chạy + đường dẫn file kết quả.
- Một thư mục kết quả chỉ một tiến trình ghi: không chạy hai lệnh cùng `RESULTS_ROOT` và cùng tên thí nghiệm một lúc.

### 5. Lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| `sha256sum -c` báo `FAILED` cho mọi trace dù tải đủ | Git trên Windows lưu `traces/SHA256SUMS_v2` với CRLF. Dùng đúng lệnh có `tr -d '\r' <` như bước 3 |
| `curl` báo lỗi tham số, hoặc `tr`/`sha256sum` không tồn tại | Đang ở PowerShell. Mở Git Bash và chạy lại |
| `UnicodeEncodeError` khi in chữ Việt | `export PYTHONIOENCODING=utf-8` rồi chạy lại |
| `run.sh` in `[-] Có bài lỗi trong <tên>` và trả mã ≠ 0 | Xem `<RESULTS_ROOT>/<tên>/<cấu hình>.out` và `<RESULTS_ROOT>/<tên>/<cấu hình>/run.log` của bài lỗi (dòng `Traceback` cuối) |
| Máy chậm hẳn, RAM máy trên 90% | Mỗi bài cần 0,4–3,7 GB RAM (bảng mục 2). Thí nghiệm có 4–12 bài chạy song song: đóng ứng dụng khác, hoặc chạy thí nghiệm nhỏ trước (`s4`, `sched`). Số bài song song phải theo RAM, không theo số nhân |
| Máy không có ổ D | Đặt `RESULTS_ROOT` sang ổ có chỗ (mục 3); không cần sửa file nào |

### 6. Tài liệu tham khảo

- [RESULTS.md](RESULTS.md): kết quả từng tuyên bố của bài báo, chấm điểm, lệnh tái tạo, mục Hạn chế.
- [DECISIONS.md](DECISIONS.md): vì sao làm vậy (mỗi quyết định có ngày và bằng chứng).
- [REPRODUCE.md](REPRODUCE.md): chạy lại toàn bộ (trace, θ, tham số, mọi thí nghiệm).
- [PLAN_MAPPING.md](PLAN_MAPPING.md): đầu việc Plan 12 tuần ↔ file trong repo.
- [CLAUDE.md](CLAUDE.md): luật làm việc của dự án.

---

## Tái hiện bài báo SageServe

Code trong repo đã được sửa để chạy theo bài báo SageServe (arXiv 2502.14617v3).

### Trạng thái hiện tại (Pha 0–6 xong, 4/11/2026)

- **Trace:** mọi thí nghiệm dùng trace v2 (`traces/SHA256SUMS_v2`), sinh từ v1 bằng `make_trace_v2.py` để qua các cổng của `TRACE_SPEC.md`.
- **Kết luận chính** (nguyên văn từ [RESULTS.md](RESULTS.md)): "hướng của bài báo đứng được (khi dự báo tốt), biên độ thì không tái lập được; bài báo không cho sai số dự báo đỉnh, nên không biết bao nhiêu trong 20–24% đến từ cùng cơ chế (loại C)."
- **Số liệu và chấm điểm từng tuyên bố:** [RESULTS.md](RESULTS.md). **Quyết định và bằng chứng:** [DECISIONS.md](DECISIONS.md). **Đối chiếu với Plan 12 tuần:** [PLAN_MAPPING.md](PLAN_MAPPING.md).
- **Lấy trace:** xem mục "Lấy trace v2" ngay bên dưới.
- **Chạy:** `PY=<python> RESULTS_ROOT=<thư mục> bash experiments/run.sh <tên>`; mỗi dòng của RESULTS.md ghi lệnh chạy và lệnh phân tích. So hai bài: `python experiments/compare_runs.py <A> <B>`.

### Lấy trace v2

Mọi lệnh trong `experiments/run.sh` dùng trace v2. Tải 12 trace và dự báo từ GitHub Release `traces-v2` (y như [REPRODUCE.md](REPRODUCE.md) mục 2), chạy ở gốc repo:

```bash
B=https://github.com/KatoTheFirst/SageServe-Group-4/releases/download/traces-v2
for t in $(grep -o 'traces/[^ ]*_v2\.csv' traces/SHA256SUMS_v2); do curl -sSL $B/$(basename $t).gz | gunzip > $t; done
curl -sSL $B/forecasts_v2.tar.gz | tar -xz        # Windows Git Bash: thêm --force-local nếu đường dẫn có "C:"
curl -sSLO $B/SHA256SUMS_forecasts_v2
tr -d '\r' < traces/SHA256SUMS_v2 | sha256sum -c && sha256sum -c SHA256SUMS_forecasts_v2   # tr: git trên Windows checkout file này với CRLF
```

`python fetch_traces.py` hiện **chỉ tải trace v1** (Release `traces-v1`), không đủ để chạy `experiments/run.sh`.

- Chạy thí nghiệm: `bash experiments/run.sh <tên>` (s4, lt, chiron, sched, nov2024, scale5, burst, week, h100, niw_ratio)
- Kiểm thử: `python -m pytest`
- Hướng dẫn đầy đủ, kết quả đối chiếu và các điểm còn lệch: [REPRODUCE.md](REPRODUCE.md)

---

# LLM Serving Stack Simulator

## Setup

You can set up the simulator by installing its Python dependencies. We recommend starting with a fresh Python environment.

```python
# Create and activate new Python environment
conda create -n sim python=3.11
conda activate sim

# Install dependencies
pip install -r requirements.txt
```

## Inputs and Outputs

SplitwiseSim takes in a hierarchical set of YAML configuration files as input, and it produces several CSV files as output. It uses [Hydra](https://hydra.cc/) for configuration management. You can learn more about configuration management from the [Hydra docs](https://hydra.cc/docs/intro/).

The top-level configuration file for SplitwiseSim is [`config.yaml`](configs/config.yaml), which points to lower-level configurations specified by other files in the `configs/` directory. Specifically, `config.yaml` captures the following key components:

- [cluster](configs/cluster/): the provisioned server SKUs in the cluster, along with their respective counts.
- [trace](#request-traces): request trace that specifies the set of requests that arrive into the cluster.
- [router](configs/router/): the cluster-level router that routes incoming requests to application-level schedulers; currently a no-op.
- [arbiter](configs/arbiter/): the cluster-level arbiter that manages compute resources between applications to support autoscaling; currently a no-op.
- [application](configs/applications/): the logical endpoint that the requests target, which specifies the model and the set of instances on which the request runs; currently, we support only one application.
- [model_repo](configs/model_repo/): the set of models (LLMs) available to run in the cluster; used for dynamic model instantiation.
- [orchestrator_repo](configs/orchestrator_repo/): the set of application resource orchestrators (i.e., schedulers and allocators) in the cluster; used for dynamic application management.
- [hardware_repo](configs/hardware_repo/): the set of available SKUs that can be provisioned in the cluster; used for dynamic server instantiation.
- [performance_model](#performance-model): an analytical model that helps estimate request runtimes with different batch, model, and hardware configurations.
- [start_state](configs/start_state/): starting state for the cluster, which helps simplify evaluation.

Several other aspects can be configured; please see [`config.yaml`](configs/config.yaml) for details.

SplitwiseSim generates the following key outputs:

- Summary of application-level metrics (`summary.csv`)
- Per-request metrics for each completed request for each application (`detailed/{application_id}.csv`)
- Request node-level metrics (`request_nodes.csv`)
- Instance-level execution metrics (in `instances/`, with `debug` enabled)

We provide various [utility functions](notebooks/utils.py) to process outputs, as shown in [`notebooks/example.ipynb`](notebooks/example.ipynb) and [`notebooks/plots.ipynb`](notebooks/plots.ipynb).

## How to run?

Simply modify [`config.yaml`](configs/confid.yaml) to and execute ```python run.py```.

### How to run experiments with separate scaling between prod/dev?

- Use controller us3-dp in config.yaml
- Use annotated traces ES_26_dp.csv in configs/trace/enterprise_sydney.yaml

### How to configure other knobs?

The following knobs are present in [`config.yaml`](configs/confid.yaml) to freely allow changes in execution configuration.

- feed_async: True/False to enable/disable the insertion of async requests whevnever memory utilisation falls below 0.5
- feed_async_granularity: Specify the number of async requests to insert at a time.
- scaling_level: Specify 0 for no scaling, 1 for scaling from/to spot only and 2 for inter model scaling along eith spot donations.
- scaling_interval: The number of seconds to wait between two scaling events per model endpoint. Use -1 to disable this knob, i.e., no restriction on the number of scaling events w.r.t time. 


## Long term scaling
All short term scaling scripts should still run as they are!

### Scaling on 1 hour window
Run with 
```bash
python3 run_lts.py trace.filename=ES_26 \
    short_term_scaling=False \
    long_term_scaling=True \
    global_arbiter.arima_traces=$PWD/traces/forecasts/ \
    global_arbiter.post_processing_strategy=<STRATEGY>
```
where STRATEGY can be `immediate`, `delay_changes`, `keep_maximum_instances`, `keep_minimum_instances`.

### Reactive Scaling, Proactive Guidance
Run with
```bash
python3 run.py trace.filename=final_data_day_1 short_term_scaling=True long_term_scaling=True global_arbiter.arima_traces=$PWD/traces/forecasts/ controller.regions.0.arbiter=global_arbiter_ARIMA_checking controller.regions.1.arbiter=global_arbiter_ARIMA_checking controller.regions.2.arbiter=global_arbiter_ARIMA_checking global_arbiter.arima_aware_arbiter=True

python3 run.py trace.filename=final_data_day_1 short_term_scaling=True long_term_scaling=True global_arbiter.arima_traces=$PWD/traces/forecasts/ controller.regions.0.arbiter=global_arbiter_memory_utilization controller.regions.1.arbiter=global_arbiter_memory_utilization controller.regions.2.arbiter=global_arbiter_memory_utilization global_arbiter.arima_aware_arbiter=True

python3 run.py trace.filename=final_data_day_1 short_term_scaling=True long_term_scaling=True global_arbiter.arima_traces=$PWD/traces/forecasts/ controller.regions.0.arbiter=global_arbiter_short_term_scaling controller.regions.1.arbiter=global_arbiter_short_term_scaling controller.regions.2.arbiter=global_arbiter_short_term_scaling global_arbiter.arima_aware_arbiter=True
```

## Citation
If you use our work, please consider citing our paper:
```
@article{10.1145/3771576,
author = {Jaiswal, Shashwat and Jain, Kunal and Simmhan, Yogesh and Parayil, Anjaly and Mallick, Ankur and Wang, Rujia and Amant, Renee St. and Bansal, Chetan and Ruhle, Victor and Kulkarni, Anoop and Kofsky, Steve and Rajmohan, Saravan},
title = {SAGESERVE: Optimizing LLM Serving on Cloud Data Centers with Forecast Aware Auto-Scaling},
year = {2025},
issue_date = {December 2025},
publisher = {Association for Computing Machinery},
address = {New York, NY, USA},
volume = {9},
number = {3},
url = {https://doi.org/10.1145/3771576},
doi = {10.1145/3771576},
journal = {Proc. ACM Meas. Anal. Comput. Syst.},
month = dec,
articleno = {61},
numpages = {24},
keywords = {forecast aware auto-scaling, llm inference serving, llm inference simulator, production traces, resource allocation, scheduling, workload analysis}
}
```
## Acknowledgement
This project uses code from the [Splitwise simulator](https://github.com/Mutinifni/splitwise-sim).
