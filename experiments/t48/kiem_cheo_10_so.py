"""Kiểm chéo độc lập 10 số chính của nháp T48: analyze_s4.analyze đọc thẳng thư mục kết quả (seed0), không qua bản nhìn junction
hay bảng phân tích sinh nháp. Dùng (cwd = repo): python experiments/t48/kiem_cheo_10_so.py <gốc t48m> <thư mục lt (t48_d40/lt)>"""
import sys
sys.path.insert(0, ".")
from analyze_s4 import analyze
D, L = sys.argv[1], sys.argv[2]
L2, B = "llama2-70b", "bloom-176b"
ih = lambda d, sk, m=None: (lambda s: s.sum() if m is None else s[m])(analyze(d, sk)[0].instance_hours)
pct = lambda a, b: 100 * (a / b - 1)
rows = []
rows.append(("§4 IH Unified (không bỏ giờ)", ih(f"{D}/s4/unified/seed0", 0), "401,00"))
rows.append(("§4 IH Siloed (không bỏ giờ)", ih(f"{D}/s4/siloed/seed0", 0), "591,50"))
R = ih(f"{L}/reactive/seed0", 1, L2)
for s, nh in (("lt_i", "−21,94"), ("lt_u", "−20,97"), ("lt_ua", "−20,90")):
    rows.append((f"trace chính Llama-2 {s} % so Reactive", pct(ih(f"{L}/{s}/seed0", 1, L2), R), nh))
RW = ih(f"{D}/week/reactive/seed0", 1, L2)
for s, nh in (("lt_i", "−23,1"), ("lt_u", "−20,7"), ("lt_ua", "−22,7")):
    rows.append((f"week Llama-2 {s} % so Reactive", pct(ih(f"{D}/week/{s}/seed0", 1, L2), RW), nh))
T = lambda s, m=None: ih(f"{D}/theta177/{s}/seed0", 1, m)
rows.append(("θ177 LT-I % so Reactive (Bloom / Llama-2 / tổng)",
             " / ".join(f"{pct(T('lt_i', m), T('reactive', m)):+.2f}" for m in (B, L2, None)), "+60,1 / +64,3 / +51,8"))
r = analyze(f"{D}/s4load/unified/seed0", 0)[0]
rows.append(("s4load Bloom TTFT P95 (s)", r.loc[B, "iw_ttft_p95"], "21 486"))
for a, b, c in rows:
    print(f"{a:55s} | độc lập: {b if isinstance(b, str) else f'{b:.4f}':>24s} | nháp: {c}")
