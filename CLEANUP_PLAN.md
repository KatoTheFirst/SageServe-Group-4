# CLEANUP_PLAN – kế hoạch dọn kết quả (3/11/2026)

**Đã thực hiện 3/11/2026 theo duyệt của người dùng (D20):**
- X1, X2, X3: đã xóa 72 bài, 26,60 GB. Riêng `v2/full/oracle_pha4/lt_u` chỉ xóa nếu `E:/SageServe_results_p5/oracle/lt/lt_u` chạy xong và trùng từng byte; nếu không trùng thì giữ và báo người dùng.
  → 3/11 15:39: `compare_runs.py` cho TRÙNG (2040 file, 0 khác biệt, cấu hình giống) → đã chép `summary/`, `.hydra/` vào kho lưu và xóa bản cũ.
- Z: không làm.
- N 1–5: GIỮ hết, **xem lại sau khi checklist "xong" đạt và REPRODUCE.md chuyển sang v2**.
- Bản lưu cấu hình và tóm tắt của các bài đã xóa: `D:/SageServe_results/_archive_summaries/`.

Phần dưới là kế hoạch gốc, giữ nguyên để đối chiếu.

**Phạm vi:** thư mục kết quả ngoài git: `D:/SageServe_results` và `E:/SageServe_Chuyên đề TT&MMT/results` (ignored). Không xét `E:/SageServe_results_p5`, nơi 12 bài Pha 5 đang chạy (đã kiểm tiến trình python lúc lập kế hoạch). Không xét file do git theo dõi, `traces/`, `data/`, `output/`, `*.md`, `*.patch`. Thư mục `__pycache__`, `.pytest_cache` chỉ vài trăm KB nên bỏ qua.

**Cách lập:**
- Kiểm kê chỉ đọc bằng `inventory.py`. Một "bài" là thư mục có `.hydra`. Bài "đủ" khi `summary/` không rỗng và file `.out` đi kèm (nếu có) chứa `TraceSimulator completed`.
- Phân loại theo bảng luật trong `classify.py`; luật đầu tiên khớp được áp dụng.
- Danh sách GIỮ lấy từ đường dẫn mà tài liệu và script nhắc: `$R` = `D:/SageServe_results/v2/full`, `v2/sens`, `v2/sens2`, `v2/verify`, `results/{lt,chiron,s4,sched,nov2024,burst}`. Cộng thêm hai mục luôn giữ: bài Reactive dùng cho cổng/θ (`v2/cut`) và đường cong đo θ (`theta_bench`).

**Kết quả thử phương án Z (nén `detailed/*.csv` bằng gzip), chạy trên bản sao của `v2/full/sched/sla60/fcfs`:**
- `analyze_sched.py` vẫn ra đúng số (34,76 / 0,01%).
- `experiments/analyze_sched_floor.py` **lỗi** `ValueError: No objects to concatenate`, vì script chỉ tìm `*.csv`.
- `analyze_s4.py` và các script khác không đọc `detailed/`.
- Mức nén chỉ 20 MB → 8,6 MB trên một bài 309 MB. Tổng `detailed/` trên các bài là 13,59 GB, nén ước tiết kiệm khoảng 7,7 GB.
- **Không đề xuất Z** nếu không sửa `analyze_sched_floor.py`.

**X4 (thư mục debug `instances/`, `debug/`):** không có, 0 GB.

## Tổng

| Loại | GB | Ổ |
|---|---:|---|
| X1 – bài dở | 3,66 | D: |
| X2 – trước Pha 0, không tài liệu nào nhắc | 8,60 | E: |
| X3 – bản trùng hoặc đã chạy lại | 15,28 | D: 12,41 (gồm 0,94 có điều kiện) · E: 2,86 |
| X4 – debug | 0 | – |
| Z – nén (không đề xuất) | ~7,7 | – |
| N – cần anh/chị quyết (GIỮ cho đến khi có quyết định) | 34,78 | D: 31,38 · E: 3,40 |
| GIỮ | 75,80 | D: 62,33 · E: 13,47 |

Dung lượng trống lúc lập kế hoạch: D: 1,3 GB, E: 20 GB (E: sẽ giảm thêm khi 15 bài Pha 5 ghi xong, khoảng 13 GB). Nếu duyệt cả X1–X3: D: còn khoảng 17,4 GB, E: thêm 11,5 GB.

## Danh sách đề xuất xóa (X1–X3) và cần quyết (N)

| # | Đường dẫn | Dung lượng (GB) | Sửa cuối | Loại | Lý do |
|---|---|---:|---|---|---|
| 1 | `D:/SageServe_results/niw1/lt_i` | 1.06 | 2026-10-27 09:08 | X1 | bài dở (27/10): .out không có 'TraceSimulator completed' |
| 2 | `D:/SageServe_results/niw1/lt_u` | 1.30 | 2026-10-27 09:08 | X1 | bài dở (27/10): .out không có 'TraceSimulator completed' |
| 3 | `D:/SageServe_results/niw1/lt_ua` | 1.30 | 2026-10-27 09:08 | X1 | bài dở (27/10): .out không có 'TraceSimulator completed' |
| 4 | `E:/SageServe_Chuyên đề TT&MMT/results/0` (17 bài) | 0.07 | 2026-10-26 21:57 | X2 | thử nghiệm đầu tiên 13–15/10 (cấu hình code gốc), không tài liệu nào nhắc; một số bài dở |
| 5 | `E:/SageServe_Chuyên đề TT&MMT/results/_diag/lt_ua_noarima` | 1.00 | 2026-10-26 23:27 | X2 | chẩn đoán lẻ 26/10 (LT-UA không ARIMA), trước Pha 0, không tài liệu nào nhắc |
| 6 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/burst/lt_i` | 0.01 | 2026-10-25 04:16 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 7 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/burst/lt_u` | 0.01 | 2026-10-25 04:15 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 8 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/burst/lt_ua` | 0.01 | 2026-10-25 04:16 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 9 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/burst/reactive` | 0.01 | 2026-10-25 04:02 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 10 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/h100/lt_i` | 0.01 | 2026-10-25 06:05 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 11 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/h100/lt_u` | 0.01 | 2026-10-25 06:04 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 12 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/h100/lt_ua` | 0.01 | 2026-10-25 06:03 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 13 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/h100/reactive` | 0.01 | 2026-10-25 05:57 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 14 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/lt/lt_i` | 0.01 | 2026-10-25 01:52 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 15 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/lt/lt_u` | 0.01 | 2026-10-25 01:50 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 16 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/lt/lt_ua` | 0.01 | 2026-10-25 01:52 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 17 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/lt/reactive` | 0.01 | 2026-10-25 01:47 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 18 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/niw1/lt_i` | 0.01 | 2026-10-25 06:47 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 19 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/niw1/lt_u` | 0.01 | 2026-10-25 06:48 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 20 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/niw1/lt_ua` | 0.01 | 2026-10-25 06:47 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 21 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/niw1/reactive` | 0.01 | 2026-10-25 06:46 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 22 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/niw9/lt_i` | 0.00 | 2026-10-25 05:50 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 23 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/niw9/lt_u` | 0.00 | 2026-10-25 05:49 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 24 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/niw9/lt_ua` | 0.00 | 2026-10-25 05:48 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 25 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/niw9/reactive` | 0.00 | 2026-10-25 05:45 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 26 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/nov2024/lt_i` | 0.01 | 2026-10-25 03:48 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 27 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/nov2024/lt_u` | 0.01 | 2026-10-25 03:45 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 28 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/nov2024/lt_ua` | 0.01 | 2026-10-25 03:44 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 29 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/nov2024/reactive` | 0.01 | 2026-10-25 03:40 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 30 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/scale5/lt_i` | 0.01 | 2026-10-25 04:18 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 31 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/scale5/lt_u` | 0.01 | 2026-10-25 04:15 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 32 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/scale5/lt_ua` | 0.01 | 2026-10-25 04:17 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 33 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_cua_so/scale5/reactive` | 0.01 | 2026-10-25 04:12 | X2 | kết quả trước khi sửa cửa sổ dự báo (25/10), đã bị thay, không tài liệu nào nhắc |
| 34 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_spinup/chiron/chiron` | 0.00 | 2026-10-25 01:36 | X2 | kết quả trước khi sửa spin-up tức thì (26/10), đã bị thay, không tài liệu nào nhắc |
| 35 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_spinup/lt/lt_i` | 0.92 | 2026-10-26 17:16 | X2 | kết quả trước khi sửa spin-up tức thì (26/10), đã bị thay, không tài liệu nào nhắc |
| 36 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_spinup/lt/lt_u` | 1.00 | 2026-10-26 17:13 | X2 | kết quả trước khi sửa spin-up tức thì (26/10), đã bị thay, không tài liệu nào nhắc |
| 37 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_spinup/lt/lt_ua` | 1.00 | 2026-10-26 17:11 | X2 | kết quả trước khi sửa spin-up tức thì (26/10), đã bị thay, không tài liệu nào nhắc |
| 38 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_spinup/lt/reactive` | 0.99 | 2026-10-26 17:08 | X2 | kết quả trước khi sửa spin-up tức thì (26/10), đã bị thay, không tài liệu nào nhắc |
| 39 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_spinup/nov2024/lt_i` | 0.85 | 2026-10-26 17:21 | X2 | kết quả trước khi sửa spin-up tức thì (26/10), đã bị thay, không tài liệu nào nhắc |
| 40 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_spinup/nov2024/lt_u` | 0.86 | 2026-10-26 17:19 | X2 | kết quả trước khi sửa spin-up tức thì (26/10), đã bị thay, không tài liệu nào nhắc |
| 41 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_spinup/nov2024/lt_ua` | 0.86 | 2026-10-26 17:19 | X2 | kết quả trước khi sửa spin-up tức thì (26/10), đã bị thay, không tài liệu nào nhắc |
| 42 | `E:/SageServe_Chuyên đề TT&MMT/results/_truoc_sua_spinup/nov2024/reactive` | 0.87 | 2026-10-26 17:11 | X2 | kết quả trước khi sửa spin-up tức thì (26/10), đã bị thay, không tài liệu nào nhắc |
| 43 | `D:/SageServe_results/bravo_ver/h100/reactive` | 0.97 | 2026-11-02 19:26 | X3 | chạy lại Reactive 2/11 để kiểm tất định, trùng từng byte với bài 27/10 (đã ghi STATUS/bộ nhớ) |
| 44 | `D:/SageServe_results/bravo_ver/niw1/reactive` | 1.35 | 2026-11-02 20:13 | X3 | chạy lại Reactive 2/11 để kiểm tất định, trùng từng byte với bài 27/10 (đã ghi STATUS/bộ nhớ) |
| 45 | `D:/SageServe_results/bravo_ver/niw9/reactive` | 0.86 | 2026-11-02 19:18 | X3 | chạy lại Reactive 2/11 để kiểm tất định, trùng từng byte với bài 27/10 (đã ghi STATUS/bộ nhớ) |
| 46 | `D:/SageServe_results/bravo_ver/nov2024/reactive` | 0.87 | 2026-11-02 19:29 | X3 | chạy lại Reactive 2/11 để kiểm tất định, trùng từng byte với bài 27/10 (đã ghi STATUS/bộ nhớ) |
| 47 | `D:/SageServe_results/bravo_ver/scale5/reactive` | 1.25 | 2026-11-02 19:52 | X3 | chạy lại Reactive 2/11 để kiểm tất định, trùng từng byte với bài 27/10 (đã ghi STATUS/bộ nhớ) |
| 48 | `D:/SageServe_results/niw9/lt_i` | 0.79 | 2026-10-27 06:18 | X3 | LT v1 27/10, đã chạy lại 2/11 ở `D:/SageServe_results/bravo/<tên>` (REPRODUCE: "các bài LT chạy lại 2/11/2026") |
| 49 | `D:/SageServe_results/niw9/lt_u` | 0.86 | 2026-10-27 06:09 | X3 | LT v1 27/10, đã chạy lại 2/11 ở `D:/SageServe_results/bravo/<tên>` (REPRODUCE: "các bài LT chạy lại 2/11/2026") |
| 50 | `D:/SageServe_results/niw9/lt_ua` | 0.86 | 2026-10-27 07:15 | X3 | LT v1 27/10, đã chạy lại 2/11 ở `D:/SageServe_results/bravo/<tên>` (REPRODUCE: "các bài LT chạy lại 2/11/2026") |
| 51 | `D:/SageServe_results/scale5/lt_i` | 1.16 | 2026-10-27 06:51 | X3 | LT v1 27/10, đã chạy lại 2/11 ở `D:/SageServe_results/bravo/<tên>` (REPRODUCE: "các bài LT chạy lại 2/11/2026") |
| 52 | `D:/SageServe_results/scale5/lt_u` | 1.25 | 2026-10-27 06:34 | X3 | LT v1 27/10, đã chạy lại 2/11 ở `D:/SageServe_results/bravo/<tên>` (REPRODUCE: "các bài LT chạy lại 2/11/2026") |
| 53 | `D:/SageServe_results/scale5/lt_ua` | 1.25 | 2026-10-27 06:34 | X3 | LT v1 27/10, đã chạy lại 2/11 ở `D:/SageServe_results/bravo/<tên>` (REPRODUCE: "các bài LT chạy lại 2/11/2026") |
| 54 | `D:/SageServe_results/v2/full/oracle_pha4/lt_u` | 0.94 | 2026-11-03 12:43 | X3 | trùng cấu hình với `E:/SageServe_results_p5/oracle/lt/lt_u` (Pha 5, đang chạy); CHỈ xóa sau khi bài đó xong và global_router trùng từng byte |
| 55 | `E:/SageServe_Chuyên đề TT&MMT/results/h100/lt_i` | 0.90 | 2026-10-27 03:56 | X3 | LT v1 27/10, đã chạy lại 2/11 ở `D:/SageServe_results/bravo/h100` |
| 56 | `E:/SageServe_Chuyên đề TT&MMT/results/h100/lt_u` | 0.98 | 2026-10-27 04:50 | X3 | LT v1 27/10, đã chạy lại 2/11 ở `D:/SageServe_results/bravo/h100` |
| 57 | `E:/SageServe_Chuyên đề TT&MMT/results/h100/lt_ua` | 0.98 | 2026-10-27 04:49 | X3 | LT v1 27/10, đã chạy lại 2/11 ở `D:/SageServe_results/bravo/h100` |
| 58 | `D:/SageServe_results/bravo/burst/lt_i` | 1.03 | 2026-11-02 14:32 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 59 | `D:/SageServe_results/bravo/burst/lt_u` | 1.11 | 2026-11-02 14:21 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 60 | `D:/SageServe_results/bravo/burst/lt_ua` | 1.12 | 2026-11-02 14:21 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 61 | `D:/SageServe_results/bravo/h100/lt_i` | 0.93 | 2026-11-02 13:38 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 62 | `D:/SageServe_results/bravo/h100/lt_u` | 0.99 | 2026-11-02 13:31 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 63 | `D:/SageServe_results/bravo/h100/lt_ua` | 0.98 | 2026-11-02 13:33 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 64 | `D:/SageServe_results/bravo/lt/lt_i` | 0.94 | 2026-11-02 11:31 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 65 | `D:/SageServe_results/bravo/lt/lt_u` | 1.00 | 2026-11-02 11:28 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 66 | `D:/SageServe_results/bravo/lt/lt_ua` | 1.00 | 2026-11-02 11:28 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 67 | `D:/SageServe_results/bravo/niw1/lt_i` | 1.25 | 2026-11-02 15:56 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 68 | `D:/SageServe_results/bravo/niw1/lt_u` | 1.35 | 2026-11-02 15:53 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 69 | `D:/SageServe_results/bravo/niw1/lt_ua` | 1.35 | 2026-11-02 16:01 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 70 | `D:/SageServe_results/bravo/niw9/lt_i` | 0.82 | 2026-11-02 14:52 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 71 | `D:/SageServe_results/bravo/niw9/lt_u` | 0.86 | 2026-11-02 14:48 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 72 | `D:/SageServe_results/bravo/niw9/lt_ua` | 0.85 | 2026-11-02 14:53 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 73 | `D:/SageServe_results/bravo/nov2024/lt_i` | 0.84 | 2026-11-02 14:12 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 74 | `D:/SageServe_results/bravo/nov2024/lt_u` | 0.86 | 2026-11-02 13:58 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 75 | `D:/SageServe_results/bravo/nov2024/lt_ua` | 0.86 | 2026-11-02 13:57 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 76 | `D:/SageServe_results/bravo/scale5/lt_i` | 1.19 | 2026-11-02 14:36 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 77 | `D:/SageServe_results/bravo/scale5/lt_u` | 1.26 | 2026-11-02 14:27 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 78 | `D:/SageServe_results/bravo/scale5/lt_ua` | 1.26 | 2026-11-02 14:29 | N | LT v1 chạy lại 2/11 – nguồn số ở cột "Kết quả" v1 của REPRODUCE.md (commit 27345e2, số T43 của anh/chị). Giữ hay xóa? |
| 79 | `D:/SageServe_results/bravo_daymix/lt/lt_i` | 0.84 | 2026-11-02 10:29 | N | θ theo tỉ lệ cả ngày – bằng chứng cho câu "TTFT P95 7073 s" ở REPRODUCE.md và SENSITIVITY.md (không nhắc đường dẫn). Giữ hay xóa? |
| 80 | `D:/SageServe_results/bravo_daymix/lt/lt_u` | 0.99 | 2026-11-02 10:27 | N | θ theo tỉ lệ cả ngày – bằng chứng cho câu "TTFT P95 7073 s" ở REPRODUCE.md và SENSITIVITY.md (không nhắc đường dẫn). Giữ hay xóa? |
| 81 | `D:/SageServe_results/bravo_daymix/lt/lt_ua` | 0.99 | 2026-11-02 10:27 | N | θ theo tỉ lệ cả ngày – bằng chứng cho câu "TTFT P95 7073 s" ở REPRODUCE.md và SENSITIVITY.md (không nhắc đường dẫn). Giữ hay xóa? |
| 82 | `D:/SageServe_results/bravo_daymix/lt/reactive_check` | 1.00 | 2026-11-02 10:12 | N | θ theo tỉ lệ cả ngày – bằng chứng cho câu "TTFT P95 7073 s" ở REPRODUCE.md và SENSITIVITY.md (không nhắc đường dẫn). Giữ hay xóa? |
| 83 | `D:/SageServe_results/bravo_ver/burst/lt_ua_nodown` | 1.12 | 2026-11-02 19:53 | N | bài đối chứng tắt luật ≤0,5× của LT-UA (v1) và Reactive chạy lại; bằng chứng cho phát hiện 2/11 về burst v1. Giữ hay xóa? |
| 84 | `D:/SageServe_results/bravo_ver/burst/reactive` | 1.11 | 2026-11-02 19:42 | N | bài đối chứng tắt luật ≤0,5× của LT-UA (v1) và Reactive chạy lại; bằng chứng cho phát hiện 2/11 về burst v1. Giữ hay xóa? |
| 85 | `D:/SageServe_results/niw1/reactive` | 1.35 | 2026-10-27 03:09 | N | Reactive v1 27/10 – REPRODUCE: "Reactive ... giữ số 27/10" (cơ sở của số v1). Giữ hay xóa? |
| 86 | `D:/SageServe_results/niw9/reactive` | 0.86 | 2026-10-27 01:04 | N | Reactive v1 27/10 – REPRODUCE: "Reactive ... giữ số 27/10" (cơ sở của số v1). Giữ hay xóa? |
| 87 | `D:/SageServe_results/scale5/reactive` | 1.25 | 2026-10-27 02:02 | N | Reactive v1 27/10 – REPRODUCE: "Reactive ... giữ số 27/10" (cơ sở của số v1). Giữ hay xóa? |
| 88 | `E:/SageServe_Chuyên đề TT&MMT/results/h100/reactive` | 0.97 | 2026-10-27 01:14 | N | Reactive v1 27/10 của h100 – cơ sở số v1. Giữ hay xóa? |
| 89 | `E:/SageServe_Chuyên đề TT&MMT/results/nv2/offline` | 1.00 | 2026-10-26 15:15 | N | kết quả NV2 (Load Predictor online/offline) – đầu việc của anh/chị. Giữ hay xóa? |
| 90 | `E:/SageServe_Chuyên đề TT&MMT/results/nv2/online` | 1.00 | 2026-10-26 15:15 | N | kết quả NV2 (Load Predictor online/offline) – đầu việc của anh/chị. Giữ hay xóa? |
| 91 | `E:/SageServe_Chuyên đề TT&MMT/results/nv2_6h/offline` | 0.21 | 2026-10-26 14:28 | N | kết quả NV2 (Load Predictor online/offline) – đầu việc của anh/chị. Giữ hay xóa? |
| 92 | `E:/SageServe_Chuyên đề TT&MMT/results/nv2_6h/online` | 0.21 | 2026-10-26 14:28 | N | kết quả NV2 (Load Predictor online/offline) – đầu việc của anh/chị. Giữ hay xóa? |

## Danh sách GIỮ

| Thư mục GIỮ | Số bài | GB | Lý do |
|---|---:|---:|---|
| `D:/SageServe_results/theta_bench/a100` | 114 | 1.25 | đường cong đo θ (data/theta_tps*.csv) |
| `D:/SageServe_results/theta_bench/a100_h8` | 44 | 0.25 | đường cong đo θ (data/theta_tps*.csv) |
| `D:/SageServe_results/theta_bench/fork` | 91 | 0.67 | đường cong đo θ (data/theta_tps*.csv) |
| `D:/SageServe_results/theta_bench/h100` | 82 | 0.63 | đường cong đo θ (data/theta_tps*.csv) |
| `D:/SageServe_results/theta_bench/h100_h8` | 54 | 0.39 | đường cong đo θ (data/theta_tps*.csv) |
| `D:/SageServe_results/theta_bench/v2_a100_h8` | 22 | 0.11 | đường cong đo θ (data/theta_tps*.csv) |
| `D:/SageServe_results/theta_bench/v2_fork` | 68 | 0.52 | đường cong đo θ (data/theta_tps*.csv) |
| `D:/SageServe_results/theta_bench/v2_h100_h8` | 22 | 0.12 | đường cong đo θ (data/theta_tps*.csv) |
| `D:/SageServe_results/v2/cut` | 3 | 0.36 | Reactive bản cắt dùng cho cổng T8/T9 (D8) – bài Reactive dùng đo θ/cổng |
| `D:/SageServe_results/v2/full` | 43 | 50.63 | RESULTS.md (`$R` = D:/SageServe_results/v2/full) |
| `D:/SageServe_results/v2/sens` | 21 | 2.88 | SENSITIVITY.md |
| `D:/SageServe_results/v2/sens2` | 10 | 1.56 | SENSITIVITY.md |
| `D:/SageServe_results/v2/verify` | 10 | 2.96 | RESULTS.md, mục Kiểm tra cuối |
| `E:/SageServe_Chuyên đề TT&MMT/results/burst/lt_i` | 1 | 0.99 | REPRODUCE.md nhắc `results/<tên>` |
| `E:/SageServe_Chuyên đề TT&MMT/results/burst/lt_u` | 1 | 1.10 | REPRODUCE.md nhắc `results/<tên>` |
| `E:/SageServe_Chuyên đề TT&MMT/results/burst/lt_ua` | 1 | 1.02 | REPRODUCE.md nhắc `results/<tên>` |
| `E:/SageServe_Chuyên đề TT&MMT/results/burst/reactive` | 1 | 1.11 | REPRODUCE.md nhắc `results/<tên>` |
| `E:/SageServe_Chuyên đề TT&MMT/results/chiron/chiron` | 1 | 1.51 | REPRODUCE.md nhắc `results/<tên>` |
| `E:/SageServe_Chuyên đề TT&MMT/results/lt/lt_i` | 1 | 0.91 | REPRODUCE.md nhắc `results/<tên>` |
| `E:/SageServe_Chuyên đề TT&MMT/results/lt/lt_u` | 1 | 1.00 | REPRODUCE.md nhắc `results/<tên>` |
| `E:/SageServe_Chuyên đề TT&MMT/results/lt/lt_ua` | 1 | 1.00 | REPRODUCE.md nhắc `results/<tên>` |
| `E:/SageServe_Chuyên đề TT&MMT/results/lt/reactive` | 1 | 1.00 | REPRODUCE.md nhắc `results/<tên>` |
| `E:/SageServe_Chuyên đề TT&MMT/results/nov2024/lt_i` | 1 | 0.85 | REPRODUCE.md nhắc `results/<tên>` |
| `E:/SageServe_Chuyên đề TT&MMT/results/nov2024/lt_u` | 1 | 0.86 | REPRODUCE.md nhắc `results/<tên>` |
| `E:/SageServe_Chuyên đề TT&MMT/results/nov2024/lt_ua` | 1 | 0.86 | REPRODUCE.md nhắc `results/<tên>` |
| `E:/SageServe_Chuyên đề TT&MMT/results/nov2024/reactive` | 1 | 0.87 | REPRODUCE.md nhắc `results/<tên>` |
| `E:/SageServe_Chuyên đề TT&MMT/results/s4/siloed` | 1 | 0.20 | REPRODUCE.md nhắc `results/<tên>` |
| `E:/SageServe_Chuyên đề TT&MMT/results/s4/unified` | 1 | 0.17 | REPRODUCE.md nhắc `results/<tên>` |
| `E:/SageServe_Chuyên đề TT&MMT/results/sched/sla6` | 4 | 0.01 | REPRODUCE.md nhắc `results/<tên>` |
| `E:/SageServe_Chuyên đề TT&MMT/results/sched/sla60` | 4 | 0.01 | REPRODUCE.md nhắc `results/<tên>` |

**Sau khi duyệt:** xóa đúng các dòng được duyệt. Chạy lại `python -m pytest`, `sha256sum -c` cho `traces/SHA256SUMS*` và lệnh dòng §4 của RESULTS.md. Ghi một dòng D mới vào DECISIONS.md.
