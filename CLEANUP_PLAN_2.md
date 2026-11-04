# CLEANUP_PLAN_2 – dọn ổ sau PR #1 (4/11/2026)

Phạm vi quét: `D:/SageServe_results`, `E:/SageServe_results_p5`, `results/` của repo (ignored), file untracked/ignored khác của repo, worktree `E:/SageServe_wt_literal`, `E:/pha56_untracked.tar.gz`, scratchpad của phiên. Kiểm kê: 736 thư mục bài chạy, 129,1 GB. Trước khi dọn: D: trống 14,8 GB, E: trống 20,3 GB.

Không đụng (Luật 1): `traces/` (v1, v2, archive, forecasts) và mọi `SHA256SUMS*`; dữ liệu thô Azure / ServeGen; `third_party/fork_trace_sim/` (kể cả `__pycache__` trong đó); `data/`; mọi `.py`, `.sh`, `.yaml`, `tests/`. Ngoài phạm vi, không đụng: `E:/tmp` (3 file sqlite ngày 20/10, không rõ nguồn gốc, không thuộc dự án), `output/`, PDF, xlsx.

## Danh sách GIỮ (loại K)

Lấy từ các đường dẫn mà `RESULTS.md`, `SENSITIVITY.md`, `DECISIONS.md`, `REPRODUCE.md`, `PLAN_MAPPING.md`, `experiments/*.sh` nhắc, cộng Luật 1.

| Nhóm | Bài | GB | Nhắc ở |
|---|---:|---:|---|
| `D:/SageServe_results/v2/full` | 44 | 51,56 | RESULTS.md (`$R`) |
| `D:/SageServe_results/v2/verify` | 15 | 7,46 | RESULTS.md, Kiểm tra cuối |
| `D:/SageServe_results/v2/sens`, `v2/sens2` | 31 | 4,44 | SENSITIVITY.md, `run_sens.sh` |
| `E:/SageServe_results_p5/{oracle,oracle_smooth,beta,s4load}` | 15 | 13,07 | RESULTS.md (`$O`) |
| `results/s4` (repo) | 2 | 0,36 | REPRODUCE.md (`plot_slides.py nv1 results/s4/...`) |
| `D:/SageServe_results/_archive_summaries` | 73 bản lưu | 0,07 | D20 |

## Loại S – xóa luôn (đã kiểm điều kiện)

| Mục | Dung lượng | Kiểm |
|---|---:|---|
| `__pycache__/`, `experiments/__pycache__/`, `tests/__pycache__/`, `.pytest_cache/` (repo) | 0,9 MB | cache, sinh lại khi chạy |
| Thư mục `outputs/` timestamp của hydra | 0 | không có |
| Worktree `E:/SageServe_wt_literal` | 262 MB | HEAD `27345e2` nằm trong `pha4-6-v2`; 2 file đang sửa (`experiments/run.sh`, `experiments/run_patched.py`) trùng bản trong repo |
| Bài chạy chết/dở (không có summary) | 0 | không có (chỉ có bản lưu trong `_archive_summaries`, giữ) |
| `v2/full/oracle_pha4/lt_u` | 0 | đã xóa 3/11 sau khi compare_runs cho TRÙNG (CLEANUP_PLAN.md) |
| `pha5_backup.patch`, `pha6_backup.patch` | 68 KB | hai file giống nhau; áp vào `27345e2` cho 8 file, cả 8 bản sau khi áp có blob trùng trên `group4/pha4-6-v2` |
| File tạm ở scratchpad (C:) | 2,7 GB | bản nén Release, bản tải thử, bài thử 1 giờ, bản sinh lại trace sens, trích PDF; các script cần giữ đã chép vào `experiments/` |

## Loại R – chờ duyệt

| Nhóm | Bài | GB | Đường dẫn lớn nhất | Lý do / đề xuất |
|---|---:|---:|---|---|
| `D:/SageServe_results/bravo` | 21 | 21,86 | `bravo/niw1/lt_ua` (1,35) | kết quả v1, LT chạy lại 2/11; số v1 ở commit `27345e2`. Đề xuất xóa |
| `D:/SageServe_results/bravo_daymix` | 4 | 3,83 | `bravo_daymix/lt/reactive_check` (1,00) | kết quả v1 (θ theo tỉ lệ cả ngày). Đề xuất xóa |
| `D:/SageServe_results/bravo_ver` | 2 | 2,23 | `bravo_ver/burst/lt_ua_nodown` (1,12) | kết quả v1. Đề xuất xóa |
| `D:/SageServe_results/{niw1,niw9,scale5}/reactive` | 3 | 3,46 | `niw1/reactive` (1,35) | Reactive v1 27/10. Đề xuất xóa |
| `results/h100` (repo) | 1 | 0,97 | `results/h100/reactive` | h100 v1. Đề xuất xóa |
| `results/{lt,burst,nov2024,chiron,sched}` (repo) | 21 | 13,10 | `results/chiron/chiron` (1,51) | kết quả v1 27/10; không tài liệu nào còn nhắc, không gắn đầu việc nào. Đề xuất xóa |
| File lẻ trong `results/` (`rerun_*.sh/.log`, `rerun_summary.txt`, `sensitivity.csv`, `forecasters/`, `s4_compare/`) | – | < 0,01 | – | v1, không tài liệu nào nhắc |
| `D:/SageServe_results/theta_bench` (+ 6 log, `theta_h8.csv`) | 497 | 3,94 | `theta_bench/a100/llama3.2-3b/16941` | đường cong đo θ (gắn T29), không tài liệu nào nhắc đường dẫn. Đề xuất GIỮ |
| `D:/SageServe_results/v2/cut` | 3 | 0,36 | `v2/cut/fork_reactive` | Reactive bản cắt cho cổng T8/T9 (kế hoạch dọn cũ xếp GIỮ), không tài liệu nào nhắc đường dẫn. Đề xuất GIỮ |
| `results/nv2`, `results/nv2_6h` (repo) | 4 | 2,44 | `results/nv2/online` (1,00) | đầu việc của anh/chị (NV2): chỉ liệt kê, mặc định GIỮ |
| `E:/pha56_untracked.tar.gz` | – | 0,006 | – | 75 file: 26 có trên remote, 44 thuộc nhóm không đẩy và vẫn trùng trên đĩa, **5 file là bản cũ hơn bản đang có** (CLAUDE.md, DECISIONS.md, RESULTS.md, `experiments/compare_runs.py`, `tests/test_analysis_scripts.py`; đã sửa sau khi nén). Không đạt điều kiện S; đề xuất xóa vì bản mới đã nằm trên remote |

Trước khi xóa mỗi bài thuộc R: chép `summary/` và `.hydra/` (cùng `.out` rút 100 dòng đầu, 100 dòng cuối, như D20) vào `D:/SageServe_results/_archive_summaries/`.

Tổng: K 77,0 GB; R 52,2 GB (đề xuất xóa ≈ 45,5 GB; đề xuất giữ 6,7 GB gồm `theta_bench`, `v2/cut`, `nv2*`).

## Đã thực hiện

- 4/11 loại S (đã kiểm không có tiến trình python): xóa cache Python của repo (0,9 MB), worktree `E:/SageServe_wt_literal` (`git worktree remove --force`, 262 MB), `pha5_backup.patch`, `pha6_backup.patch`, toàn bộ scratchpad (2,7 GB). Trống thực tế trước → sau: C: 6,86 → 9,54 GB; D: 14,76 → 14,76 GB; E: 20,34 → 20,59 GB.
- 4/11 loại R (người dùng duyệt, đã kiểm không có tiến trình python):
  - XÓA mọi mục "Đề xuất xóa" ở bảng R, trừ `E:/pha56_untracked.tar.gz`. Tổng 24 mục, 58,57 GB (10⁹ byte). Số này lớn hơn 45,5 GB ở bảng vì bảng chỉ đo thư mục bài chạy, không tính log `.out` đứng cạnh.
  - Trước khi xóa, mỗi bài được chép `summary/`, `.hydra/`, `sage_env.txt` (nếu có) và `.out` (rút còn 100 dòng đầu, 100 dòng cuối) sang `D:/SageServe_results/_archive_summaries/`; các file lẻ của `results/` được chép nguyên. Nhật ký: `cleanup_2026-11-04.log`. Thư mục lưu tăng 70 MB → 129 MB.
  - GIỮ `E:/pha56_untracked.tar.gz`: đây là bản sao lưu duy nhất ngoài repo của `output/`. Đã chuyển sang `D:/SageServe_results/_archive_summaries/`, sha256 trước và sau khi chuyển trùng nhau (`038fb57d…`).
  - GIỮ `theta_bench`, `v2/cut`, `results/nv2`, `results/nv2_6h`. Không đụng `niw9/compare`, `scale5/compare`, `results/{_diag,_truoc_sua_cua_so,_truoc_sua_spinup}`: các mục này không có trong bảng R. Không đụng `E:/tmp`.
  - Trống thực tế (GiB, cùng đơn vị dòng trên) sau khi xóa và sau Bước 5: C: 9,42; D: 50,95; E: 37,46.
- 4/11 Bước 5 (ghi ở D24): pytest 89/89; `sha256sum -c` 13/13 và 15/15 OK, `SHA256SUMS_archive` 0/1 như đã biết từ D19. Chạy lại `s4` (2 bài) và `lt/lt_u` vào `D:/SageServe_results/v2/verify_d24` (1,56 GiB, GIỮ làm bằng chứng): `compare_runs.py` cho TRÙNG cả 3 bài; số của RESULTS.md khớp.
