"""Sinh lại thư mục phan_tich (đầu vào của experiments/doi_chieu.py) cho một gốc kết quả theo bố cục v2.1.
Lệnh như cột "Lệnh"/"Bằng chứng" của RESULTS.md và như v21/phan_tich (8–11/11/2026); script ngoài repo chép từ v21/phan_tich, chỉ đổi gốc thành tham số.
Mỗi lệnh chạy qua experiments/chay_phan_tich.py (luật 9: RAM < 70%), tuần tự, cwd = repo, PYTHONPATH = repo.
Dùng: python sinh_phan_tich.py <gốc R> <gốc sens (chứa sens/, sens2/)> <thư mục ra P> [--chi <tên bước,...>]"""
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PY = sys.executable
HERE = os.path.dirname(os.path.abspath(__file__))
R, SR, P = sys.argv[1], sys.argv[2], sys.argv[3]
CHI = sys.argv[sys.argv.index("--chi") + 1].split(",") if "--chi" in sys.argv else None
ST4 = ["reactive", "lt_i", "lt_u", "lt_ua"]
S4 = [PY, "analyze_s4.py"]


def runs(d, names=ST4):
    return [f"{R}/{d}/{n}" for n in names]


B = []                                                             # (tên bước, file stdout, lệnh)
B.append(("s4", f"{P}/s4.txt", S4 + runs("s4", ["unified", "siloed"]) + ["--out", f"{P}/s4"]))
B.append(("s4load", f"{P}/s4load.txt", S4 + [f"{R}/s4load/unified", "--out", f"{P}/s4load"]))
B.append(("lt", f"{P}/s4_lt.txt", S4 + runs("lt") + ["--skip_hours", "1", "--out", f"{P}/lt"]))
B.append(("chiron", f"{P}/s4_chiron.txt", S4 + [f"{R}/lt/reactive", f"{R}/chiron/chiron", "--skip_hours", "1", "--out", f"{P}/chiron"]))
for n in ("theta177", "scale5", "burst", "h100", "niw1", "niw9", "nov2024"):
    B.append((n, f"{P}/s4_{n}.txt", S4 + runs(n) + ["--skip_hours", "1", "--out", f"{P}/{n}"]))
B.append(("week", f"{P}/week_s4.txt", S4 + runs("week", ["reactive", "lt_u", "lt_ua"]) + ["--skip_hours", "1", "--out", f"{P}/week"]))
B.append(("week4", f"{P}/week4_s4.txt", S4 + runs("week") + ["--skip_hours", "1", "--out", f"{P}/week4"]))
B.append(("orc", f"{P}/orc.txt", [PY, f"{HERE}/orc.py", R, P]))
for sla in ("sla6", "sla60"):
    B.append((f"sched_{sla}", f"{P}/sched_{sla}.txt", [PY, "analyze_sched.py"] + runs(f"sched/{sla}", ["fcfs", "edf", "pf", "dpa"])))
B.append(("waste_lt", f"{P}/waste_lt.txt", [PY, "analyze_waste.py"] + runs("lt") + ["--skip_hours", "1"]))
B.append(("waste_nov", f"{P}/waste_nov.txt", [PY, "analyze_waste.py"] + runs("nov2024") + ["--skip_hours", "1"]))
for n, f in (("lt", "miss_lt"), ("nov2024", "miss_nov"), ("week", "week_miss")):
    B.append((f, f"{P}/{f}.txt", [PY, "experiments/analyze_hourly_miss.py", f"{R}/{n}"]))
B.append(("can_thiep", f"{P}/can_thiep.txt", [PY, f"{HERE}/can_thiep.py", R]))
B.append(("thu_tu_oracle", f"{P}/thu_tu_oracle.txt", [PY, f"{HERE}/thu_tu_oracle.py", f"{R}/oracle", "--tom", f"{P}/thu_tu_oracle_tom.csv"]))
B.append(("smooth_nov", f"{P}/smooth_nov.txt", [PY, f"{HERE}/smooth_nov.py", R]))
B.append(("burst_day", f"{P}/burst_day.txt", [PY, "experiments/analyze_burst_day.py", f"{R}/burst"]))
for n, f in (("lt", "reactive_behavior_lt"), ("nov2024", "reactive_behavior_nov2024")):
    B.append((f, f"{P}/{f}.txt", [PY, "experiments/reactive_behavior.py", f"{R}/{n}/reactive"]))
B.append(("week4_ngay", f"{P}/week4_ngay.txt", [PY, "experiments/analyze_week.py", f"{R}/week"]))
B.append(("week4_fig16b", f"{P}/week4_fig16b.txt", [PY, f"{HERE}/fig16b_week.py", f"{R}/week", f"{P}/week4_fig16b.csv"]))
B.append(("sens", f"{P}/sens/analyze_sensitivity.txt", [PY, "experiments/analyze_sensitivity.py", f"{SR}/sens", "--out", f"{P}/sens/SENSITIVITY.csv"]))
B.append(("burst_cut", f"{P}/sens/burst_cut.txt", [PY, "experiments/analyze_burst_cut.py", f"{SR}/sens2"]))
B.append(("h100_cut", f"{P}/sens/h100_cut.txt", [PY, f"{HERE}/h100_cut.py", SR]))

os.makedirs(f"{P}/sens", exist_ok=True)
env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": REPO, "SAGE_ANALYSIS_LOG": f"{P}/nhat_ky_phan_tich.txt"}
env.pop("SAGE_RAM_MAX", None)                                      # luật 9: ngưỡng mặc định 70%
loi = []
for ten, out, cmd in B:
    if CHI and ten not in CHI:
        continue
    rc = subprocess.run([PY, "experiments/chay_phan_tich.py", out] + cmd, cwd=REPO, env=env).returncode
    print(f"{ten}: mã {rc}", flush=True)
    if rc:
        loi.append(ten)
print("LỖI:", loi if loi else "không")
sys.exit(1 if loi else 0)
