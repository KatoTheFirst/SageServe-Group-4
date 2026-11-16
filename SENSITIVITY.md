# SENSITIVITY – Pha 3

**Số v2.1** (code tag `v2.1-fix`, 2c70582; kết quả ở `E:/SageServe_results_v21/sens`, `.../sens2`; chạy xong 8/11/2026, 31 bài, 0 lỗi). Số v2 cũ có trong git history của file này.

Bản cắt 12–15h của `composed_day_3regions_v2`, A100, θ `data/theta_tps_v2.csv`, bỏ giờ đầu, mỗi lần đổi một yếu tố. Số đầy đủ: `SENSITIVITY.csv`.
Chạy: `python experiments/make_sens_traces.py` (sinh `traces/sens_*.csv`; sha256 sens_flat 9d90fa80…, sens_spike 68846dae…, sens_rate50 7e1316bc…, sens_rate150 13f5f69c…, sens_burst_in d2d3372c…, sens_burst_out 61afbf20…), rồi `PY=<python> bash experiments/run_sens.sh sens E:/SageServe_results_v21/sens` (21 bài, ~3 giờ mô phỏng mỗi bài; biến `SAGE_SPIN_UP`, `SAGE_WAIT`, `SAGE_BETA` đặt trong script). Phân tích (chạy ở gốc repo): `python experiments/analyze_sensitivity.py E:/SageServe_results_v21/sens --out SENSITIVITY.csv`; biểu đồ: `python experiments/plot_sensitivity.py SENSITIVITY.csv SENSITIVITY.png`.

![Độ nhạy](SENSITIVITY.png)

## Khoảng cách Reactive − LT-UA

| Yếu tố | Mức | Reactive IH | LT-UA IH | Khoảng cách tổng | Llama-2 | Bloom | Lãng phí R → U (instance-hours) |
|---|---|---:|---:|---:|---:|---:|---:|
| Gốc | | 200,75 | 166,00 | **17,3%** | 15,9% | 21,6% | 3,25 → 2,19 (−33%) |
| d) θ | −30% | 200,75 | 200,00 | **0,4%** | 2,1% | −0,2% | 3,25 → 3,75 (+16%) |
| d) θ | +30% | 200,75 | 145,50 | **27,5%** | 16,9% | 37,6% | 3,25 → 1,01 (−69%) |
| a) Dao động phút | phẳng | 227,50 | 156,25 | 31,3% | 21,4% | 40,1% | 4,66 → 1,69 (−64%) |
| a) Dao động phút | gai 1,77× | 236,50 | 162,50 | 31,3% | 16,4% | 41,8% | 5,11 → 1,85 (−64%) |
| b) Khởi động | 300 s | 197,75 | 166,50 | 15,8% | 11,7% | 20,8% | 1,66 → 1,22 (−26%) |
| b) Khởi động | 1200 s | 225,75 | 163,00 | 27,8% | 12,8% | 37,4% | 9,35 → 4,22 (−55%) |
| c) Cooldown Reactive | chờ instance sẵn sàng | 192,00 | 166,00 | 13,5% | – | – | 2,18 → 2,19 |
| d) ε | 0,63 | 200,75 | 168,50 | 16,1% | 11,8% | 21,2% | 3,25 → 0,91 (−72%) |
| d) ε | 1,0 | 200,75 | 170,25 | 15,2% | 11,8% | 19,8% | 3,25 → 2,81 (−13%) |
| d) β | 7% / 13% | 200,75 | 166,00 | 17,3% | 15,9% | 21,6% | không đổi |
| e) Mức tải | ×0,5 | 121,75 | 97,75 | 19,7% | 22,7% | 26,4% | 1,31 → 0,20 (−85%) |
| e) Mức tải | ×1,5 | 283,50 | 235,25 | 17,0% | 10,0% | 22,1% | 1,88 → 4,23 (+125%) |

Dòng c) chỉ chạy Reactive. LT-UA lấy từ dòng gốc vì LT-UA không dùng cooldown Reactive.

## Kết luận

- **θ vẫn chi phối:** khoảng cách dao động 27,1 điểm, gần gấp 2 yếu tố đứng sau (v2: 21,3 điểm, gần gấp 3 lần). Hai yếu tố đứng sau:
  - Dao động phút: 14,0 điểm. Không đơn điệu: cả dạng phẳng lẫn dạng gai đều cho khoảng cách lớn hơn gốc.
  - Thời gian khởi động: 12,0 điểm (v2: dưới 3 điểm).

  Cooldown 3,8 điểm; mức tải 2,7; ε 2,1. β không đổi kết quả vì phần cộng thêm rất nhỏ so với đỉnh dự báo (ví dụ ±10 TPM trên 122.000 TPM).
- **Đổi so với v2:** sửa cooldown (K1, D30) làm Reactive co giãn nhiều hơn: IH gốc 191,50 → 200,75, LT-UA gần như không đổi (167,00 → 166,00). Vì vậy mọi khoảng cách tăng. Hai yếu tố làm Reactive tăng giờ máy mạnh nhất, khởi động 1200 s và dạng phút phẳng/gai, nay tăng khoảng cách nhiều hơn hẳn trước.
- **Theo luật Pha 3 (D11):**
  - (a) vẫn không chi phối và trace đạt T6, nên **không sửa trace**.
  - θ chi phối nên đã kiểm lại Pha 2: `benchmark_theta.py` đúng định nghĩa §2.1, nhưng bài báo không cho mức latency mục tiêu, tải đo hay bảng θ. **Loại C:** giữ θ đo được, không chỉnh để tăng tiết kiệm.

  Bằng chứng ghi trong D11 là số v2 (“các yếu tố khác dưới 5 điểm”). Ở v2.1, thời gian khởi động 12,0 điểm và dao động phút 14,0 điểm. Quyết định không đổi.
- **Giới hạn:** bản cắt 12–15h không có giờ 5–9, là các giờ khó nhất, nên SLA gần như không đổi ở mọi mức θ. Không suy từ đây rằng θ +30% an toàn: θ đo theo tỉ lệ cả ngày (Bloom 528, Llama-2 1315, cao hơn v2 37% và 35%) từng cho TTFT P95 Llama-2 7073 s trên trace v1.

## Lệch còn lại

**Burst.** Kết quả ở `E:/SageServe_results_v21/sens2`. Chạy: `PY=<python> bash experiments/run_sens.sh sens2 E:/SageServe_results_v21/sens2` (10 bài, gồm `SAGE_NO_DOWN=1` cho LT-UA tắt luật giảm). Phân tích: `python experiments/analyze_burst_cut.py E:/SageServe_results_v21/sens2`. Một burst ×8 dài 10 phút:

| Vị trí | Chiến lược | IH | Vi phạm Llama-2 | Vi phạm Bloom | Bộ nhớ Llama-2 hồi về < 70% |
|---|---|---:|---:|---:|---:|
| Trong 20 phút cuối giờ | Reactive | 337,0 | 34,75% | 42,60% | 898 s |
| | LT-U | 165,0 | 59,82% | 58,55% | 4800 s |
| | **LT-UA** | 239,5 | **39,37%** | **47,80%** | **1524 s** |
| Ngoài 20 phút cuối giờ | Reactive | 348,5 | 31,99% | 39,13% | 948 s |
| | LT-U = LT-UA | 165,5 | 66,81% | 64,49% | 6600 s |

- LT-UA hơn LT-U đúng như §7.2.7 khi burst rơi vào cửa sổ, và trùng hoàn toàn với LT-U khi burst nằm ngoài (giống v2). Bài báo không cho thời điểm burst: **loại C**.
- Vi phạm cao hơn Reactive là hệ quả của thiết kế: LT-I, LT-U không vượt mục tiêu ILP (§7.2.7).
- Tắt luật ≤ 0,5× không đổi kết quả trên hai bài này.

**A100 và H100.** Bản cắt: A100 17,3%, H100 18,6% (Llama-2 15,0%, Bloom 25,5%), A100 vẫn không hơn H100. Tăng thời gian khởi động A100 lên 1200 s cho 27,8%, tức khoảng cách **tăng** so với gốc (v2: 11,2%, không tăng). Điều này hợp với lý giải của Phụ lục A (“longer model loading times”): lãng phí khi tăng máy của Reactive lên 9,35 instance-hours (gốc 3,25). Bài báo không cho thời gian tải A100: **loại C**.

**Cuối tuần:** cần bài `week` của Pha 4, sẽ ghi vào `RESULTS.md`.
