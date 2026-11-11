"""Chạy một script phân tích theo ngân sách RAM (CLAUDE.md luật 9): chỉ khởi động khi RAM máy dùng < ngưỡng (mặc định 70%;
đổi bằng biến SAGE_RAM_MAX, ví dụ 85 khi không có mô phỏng nào chạy), đợi chứ không chen lúc đỉnh; chạy tuần tự từng lệnh.
Ghi stdout + stderr của lệnh ra <file_ra>, đo RSS đỉnh; nhật ký ở <thư mục của file_ra>/nhat_ky_phan_tich.txt (hoặc SAGE_ANALYSIS_LOG).
Dùng: python experiments/chay_phan_tich.py <file_ra> <lệnh...>"""
import datetime
import os
import subprocess
import sys
import time

import psutil

if len(sys.argv) < 3:
    print(__doc__)
    sys.exit(2)
out, cmd = sys.argv[1], sys.argv[2:]
MAX = float(os.environ.get("SAGE_RAM_MAX", "70"))
LOG = os.environ.get("SAGE_ANALYSIS_LOG", os.path.join(os.path.dirname(os.path.abspath(out)), "nhat_ky_phan_tich.txt"))


def log(m):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now():%d/%m %H:%M:%S} {m}\n")


while psutil.virtual_memory().percent >= MAX:
    time.sleep(30)
log(f"bắt đầu (RAM {psutil.virtual_memory().percent:.1f}%, ngưỡng {MAX:g}%): {out}")
with open(out, "w", encoding="utf-8") as f:
    p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    ps, peak, maxpct = psutil.Process(p.pid), 0, 0
    while p.poll() is None:
        try:
            peak = max(peak, ps.memory_info().rss)
        except psutil.NoSuchProcess:
            pass
        maxpct = max(maxpct, psutil.virtual_memory().percent)
        time.sleep(1)
log(f"xong mã {p.returncode} (RSS đỉnh {peak / 2**30:.2f} GB, RAM máy cao nhất {maxpct:.1f}%): {out}")
sys.exit(p.returncode)
