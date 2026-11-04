# TRACE_SPEC – đặc tả trace, đóng băng 2/11/2026 trước mọi mô phỏng mới

Trace được chấm **chỉ** theo bảng này, suy từ §2–§3, §4, §7.1 của bài báo, không theo kết quả §7. Đo bằng `qualify_trace.py`.
Dung sai là lựa chọn của nhóm: ±0,05 cho `ps` nêu bằng số, vì `ps` đo trên 168 điểm; số đọc từ hình lấy ×0,8–×1,25.
**Công khai:** trước khi viết bản này, nhóm đã biết một số giá trị của trace hiện tại (T5, T9). Vì vậy T9 ghi rõ phương pháp và không chỉnh ngưỡng theo trace.

Hai vai trò trace: `t7` = T7/2025 (`composed_*`, mặc định của §7), `t11` = T11/2024 (`fork_*`, §4 và kiểm chứng Nov).

| Mã | Chỉ số | Cách đo | Ngưỡng `t7` | Ngưỡng `t11` | Nguồn |
|---|---|---|---|---|---|
| T1 | IW / tổng request | đếm `scenario` | 65–80% (số bài báo 72%; 3:1 = 75%) | ngày 3 vùng: 65–80% (Phụ lục A 3:1); `fork_s4_westus`: 82–93% (§4: 1,4M : 0,2M = 7:1) | §3, §4, Phụ lục A |
| T2 | `ps` = ACF lag 24 giờ của số request theo giờ, cộng 3 vùng, trace tuần | `acf(nlags=24)` | IW-F A 0,65–1,00; IW-N A 0,55–0,85; IW-N B 0,25–0,55; NIW mọi mô hình ≤ 0,336 | NIW ≤ 0,336. IW: bài báo không cho số Nov, chỉ INFO | §3 |
| T3 | Cuối tuần / ngày thường (TB request/ngày, trace tuần) | đếm theo `day0` | IW-F ≤ 0,40 (đọc từ Fig. 3c ≈ 0,2); NIW 0,4–1,2 (§2.2 "stable", Fig. 3c ≈ 0,4) | IW ≤ 0,40 (đọc từ Fig. 3a ≈ 0,2); NIW 0,4–1,2 (đọc từ Fig. 3a ≈ 0,75) | §3, Fig. 3 |
| T4 | Lệch vùng/mô hình | request theo vùng gốc | IW-F: E > C > W; A: E/W 3–7 (§3 ≈ 4); B IW-F cao nhất ở C; B IW-N cao nhất ở W; NIW ở W ≤ 10% | IW mỗi vùng: max/min ≤ 1,5 (đọc từ Fig. 5 ≈ 1,0–1,4). Trace 1 vùng: N/A | §3, Fig. 4, Fig. 5 |
| T5 | Token | tỉ lệ request IW | từng mô hình: input > 1k > 50%; output < 1k > 50%; cắt ở 8192 ≤ 10% | như `t7` | §7.1, Fig. 10 |
| T6 | Dao động mức phút ở giờ cao điểm: max/median TPS (input+output tính tại lúc đến) theo phút, cộng 3 vùng; kèm CV | giờ có TPS IW cao nhất | IW-F 1,00–1,31 (đọc từ Fig. 3d ≈ 1,05); IW-N 1,00–1,38 (≈ 1,1); NIW 1,36–2,13 (≈ 1,7) | IW 1,42–2,21 (đọc từ Fig. 3b ≈ 1,77); NIW 3,0–4,7 (≈ 3,75) | Fig. 3b, 3d, 6d |
| T7 | Thời gian | xem dưới | tất cả đạt | tất cả đạt | §4, §6.3 |
| T8 | Mức tải: instance lớn nhất của Bloom, Llama-2 ở mọi vùng ≥ 4 | `check_g10.py` trên bài Reactive | ≥ 4 | ≥ 4 | G10 |
| T9 | θ cùng cỡ §2.1: trong vòng 1 bậc độ lớn của Q1–Q3 (từ Q1/10 đến Q3×10) | TPS/instance khi bộ nhớ 60–80%, `analyze_capacity.py` trên bài Reactive; `benchmark_theta.py` chỉ INFO | A100: Llama-2 6,8–2930; Bloom 5–1770. H100: Llama-2 9,5–5220; Bloom 8,2–3970 | như `t7` | §2.1 |

**T7 gồm:** (a) `arrival_timestamp` không giảm, tính bằng giây, nằm trong `[0, số ngày × 86400)`; (b) trace tuần: hai ngày tải IW thấp nhất đúng là thứ Bảy, Chủ Nhật theo `day0`; (c) trace ngày khớp đúng ngày thứ Ba của trace tuần cùng bộ sinh (tương quan số request theo giờ ≥ 0,95); (d) mọi file dự báo: `Time` là bội của 60, mỗi giờ từ 1 trở đi có đúng 60 phút, `issue_time` đúng đầu giờ đó (dự báo chỉ dùng quá khứ, giờ đang dự báo là giờ kế tiếp của dữ liệu huấn luyện); (e) `analyze_s4.py` và `analyze_waste.py` dùng một `skip_hours` chung cho mọi bài trong cùng lần gọi.

**Không gate:** trace biến thể (`burst8`, `niw9`, `niw1`, `5models`) cố ý đổi T1 hoặc T6: T1 của `niw9`, `niw1` và T6 của `burst8` là N/A. Các chỉ số khác phải đạt như trace gốc. MAPE ARIMA chỉ INFO, vì bài báo không đặt ngưỡng cho trace.

**Mâu thuẫn đã biết của bài báo:** §3 72% IW; §4 7:1; Phụ lục A 3:1. Fig. 5 cho West ~5 RPS IW trong khi §4 nói 1,4M IW/ngày (~16 RPS). Fig. 3c cho NIW cuối tuần giảm trong khi §2.2 nói ổn định. §2.1 (68–293 TPS) so với chú thích Fig. 9 (prompt TPS 21000).
