# CLAUDE.md – SageServe-Group-4

## Luật làm việc dự án

Áp dụng từ Pha 0 (2/11/2026). Chi tiết và bằng chứng của từng quyết định ở `DECISIONS.md`.

1. **Luật quyết định ghi trước, số đến sau.** Mọi ngưỡng, tiêu chí hay cách chấm (đạt/trượt, xếp loại A–D, "≥ 5x"…) phải ghi vào `DECISIONS.md` TRƯỚC khi có số của thí nghiệm liên quan. Không sửa trace hay tham số sau khi nhìn kết quả để ép con số. Chỉ đảo một quyết định khi có bằng chứng định lượng mới, và ghi lại.
2. **Không sửa `.py`/`.yaml` trong thư mục làm việc khi còn bài đang chạy hoặc đang xếp hàng.** Kiểm tiến trình trước. Code mới chuẩn bị trong git worktree riêng ngoài thư mục repo (ví dụ `E:/SageServe_wt_<tên>`); chỉ chép về khi mọi bài đã bắt đầu.
3. **So bài theo số liệu, không theo byte.** Dùng `python experiments/compare_runs.py <A> <B>`: so `summary/` và `detailed/` (sai lệch ≤ 1e-9), bỏ qua log, `.hydra`, thời gian, đường dẫn. Nhãn phụ thuộc so sánh cấu hình (`.hydra/overrides.yaml` bỏ `output_dir`, cộng biến `SAGE_*` trong `sage_env.txt` do `run.py` ghi lúc chạy): số trùng → TRÙNG; cấu hình giống mà số khác → KHÔNG TẤT ĐỊNH (vấn đề tái lập, ưu tiên cao nhất); cấu hình khác hoặc không đọc được → KHÁC.
4. **Tách "chặn lỗi" khỏi "chính sách"** khi tạo biến thể theo đúng chữ bài báo: luật chỉ để tránh lỗi (chia cho 0, trạng thái hỏng) thì giữ; luật là lựa chọn hành vi mà bài báo không nêu thì tắt hoặc thay bằng hành vi bài báo mô tả.
5. **Chỉ số quyết định đếm 1–1, không đếm trùng.** Ví dụ flap: mỗi scale-out chỉ khớp một scale-in gần nhất trước nó, chưa được ghép. Nêu rõ phần bị loại (ví dụ bỏ giờ đầu).
6. **Việc ngoài danh sách đã duyệt: hỏi trước.** Kể cả bước phụ "dọn cho gọn"; không xóa hay ghi đè dữ liệu kết quả khi chưa được duyệt.
7. **Một thư mục kết quả, một tiến trình ghi.** Trước khi khởi động một bài hoặc pytest, kiểm không có tiến trình cùng đích đang chạy; mỗi thư mục kết quả chỉ một tiến trình ghi.
