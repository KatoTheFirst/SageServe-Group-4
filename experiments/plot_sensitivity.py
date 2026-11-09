"""Biểu đồ độ nhạy Pha 3: khoảng dao động của khoảng cách Reactive − LT-UA (% instance-hours) theo từng yếu tố."""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

d = pd.read_csv(sys.argv[1]).set_index("yếu tố")["khoảng cách tổng %"]
base = d["base"]
F = [("θ ±30%", ["thm30", "thp30"]), ("Dao động mức phút: phẳng, gai", ["flat", "spike"]), ("Khởi động 300 / 1200 s", ["su300", "su1200"]),
     ("ε 0,63 / 1,0", ["eps70", "eps100"]), ("Mức tải ±50%", ["r50", "r150"]), ("β 7% / 13%", ["b7", "b13"])]
rows = sorted(((n, min(base, *d[k]), max(base, *d[k])) for n, k in F), key=lambda r: r[2] - r[1])
fig, ax = plt.subplots(figsize=(8, 3.6), dpi=150)
for y, (n, lo, hi) in enumerate(rows):
    ax.plot([lo, hi], [y, y], color="#2F6DB5", lw=6, solid_capstyle="round")
    ax.text(hi + 0.5, y, f"{lo:.1f}–{hi:.1f}", va="center", fontsize=9, color="#333333")
ax.axvline(base, color="#888888", lw=1)
ax.text(base, len(rows) - 0.4, f"gốc {base:.1f}%", ha="center", fontsize=9, color="#555555")
ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=9)
ax.set_xlabel("Reactive − LT-UA (% instance-hours), bản cắt 12–15h", fontsize=9)
ax.set_xlim(0, max(30, max(r[2] for r in rows) + 5))
ax.grid(axis="x", color="#E6E6E6", lw=0.7)
ax.set_axisbelow(True)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.tick_params(length=0)
fig.tight_layout()
fig.savefig(sys.argv[2])
