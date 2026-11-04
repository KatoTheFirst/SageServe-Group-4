# STATUS – kiểm kê Pha 0 (2/11/2026)

**Git:** nhánh `group4`, đi trước `group4/main` 2 commit (`3e75138`, `27345e2`), chưa đẩy. Thêm `REPORT.md`, `output/`, PDF, Excel chưa theo dõi và không commit.

**Test:** `python -m pytest` → 51 passed (5 phút 14 giây), trên code trước Pha 1.

**Trace (`sha256sum -c traces/SHA256SUMS`):** 8 trace đúng hash. Thiếu file: `composed_day_3regions_12to15.csv`, `composed_day_3regions_12to15_iwn6.csv`, `composed_s4_westus.csv`. Lệch hash: `data/theta_tps.csv`, `data/theta_tps_fork.csv`, `data/theta_tps_h100.csv`, do θ đo lại ở `3e75138` mà chưa cập nhật SHA256SUMS.

**Khác bài báo đã ghi (REPRODUCE.md §4):** spot log-normal; tín hiệu Queue Manager mỗi 1 s; ε = 0,9; σ = α·600/3600; giờ 0 dự báo bằng trung bình; dạng phân phối trễ chuyển vùng; τ_p = 1 s, τ_n = 5 s; profile Chiron từ bảng hiệu năng, batch 64; GPU thí nghiệm chính giữ A100; năng lực cố định 0,75× và SLA 6 s ở §7.2.6; mô hình 5 dùng profile Llama-2.

**Phát hiện khi đọc lại bài báo bằng hình:**
- Fig. 11: Reactive 362,25, LT-I 274,5, LT-U 291, LT-UA 277,5, Chiron 1146 instance-hours (Llama-2, 3 vùng). Bài `lt` của nhóm: Reactive 362,25.
- Fig. 13b: Reactive lãng phí ~93 instance-hours (đọc từ hình), nhóm 4,68 GPU-giờ. Đơn vị và cách đo cần đối chiếu ở Pha 2.
- Fig. 12a: East có LT-U, LT-UA ≈ 100 so với Reactive ≈ 85 (đọc từ hình), trái câu "better for all regions" (§7.2.1).
