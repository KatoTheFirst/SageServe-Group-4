"""Bảng v2.1 | T48 | bài báo cho TONG_HOP_T48.md, đọc thẳng đầu ra phân tích (cùng định nghĩa analyze_s4 / analyze_oracle như RESULTS v2.1).
Dùng: python bang_tong_hop.py <phan_tich v2.1> <phan_tich T48> <file md ra>"""
import re
import sys

import pandas as pd

P21, P48, OUT = sys.argv[1:4]
B, L2, L31, L32 = "bloom-176b", "llama2-70b", "llama3.1-8b", "llama3.2-3b"
M4 = [B, L2, L31, L32]
LT = ["lt_i", "lt_u", "lt_ua"]
TEN = {"reactive": "Reactive", "lt_i": "LT-I", "lt_u": "LT-U", "lt_ua": "LT-UA", "unified": "Unified", "siloed": "Siloed"}


def c(P, n):
    return pd.read_csv(f"{P}/{n}/compare_with_paper.csv", index_col=0)


def v(P, n, r, met, m):
    return float(c(P, n).loc[m, f"{r}:{met}"])


def ih(P, n, r, m=None):
    return sum(v(P, n, r, "instance_hours", x) for x in M4) if m is None else v(P, n, r, "instance_hours", m)


def f(x, d=2):
    return "–" if x is None else f"{x:,.{d}f}".replace(",", " ").replace(".", ",").replace("-", "−")


def p(a, b):
    return 100 * (a / b - 1)


L = []
w = L.append

# A. §4
w("### §4 Siloed / Unified (Fig. 8a, Table 1)\n")
w("| Chỉ số | Bài báo | v2.1 | T48 |\n|---|---:|---:|---:|")
for lab, fn, paper in [("IH Unified (tổng 4 mô hình)", lambda P: ih(P, "s4", "unified"), "350,8"),
                       ("IH Siloed", lambda P: ih(P, "s4", "siloed"), "538,4"),
                       ("Unified so Siloed (%)", lambda P: p(ih(P, "s4", "unified"), ih(P, "s4", "siloed")), "−34,8"),
                       ("TTFT P95 Bloom Unified / Siloed (s)", None, "12,9 / –"),
                       ("TTFT P95 Llama-2 Unified / Siloed (s)", None, "34,5 / –")]:
    if fn:
        w(f"| {lab} | {paper} | {f(fn(P21))} | {f(fn(P48))} |")
    else:
        m = B if "Bloom" in lab else L2
        w(f"| {lab} | {paper} | " + " | ".join(f"{f(v(P, 's4', 'unified', 'iw_ttft_p95', m))} / {f(v(P, 's4', 'siloed', 'iw_ttft_p95', m))}" for P in (P21, P48)) + " |")
w("\n**Kiểm mức tải §4 (D18, `s4load`, Unified):** ngưỡng Bloom ≥ 6,45 s **và** Llama-2 ≥ 17,25 s (0,5x Table 1).\n")
w("| Chỉ số | Bài báo | số v2 (27345e2; không có v2.1) | T48 |\n|---|---:|---:|---:|")
w(f"| TTFT P95 Bloom (s) | 12,9 | 20 834 | {f(v(P48, 's4load', 'unified', 'iw_ttft_p95', B), 0)} |")
w(f"| TTFT P95 Llama-2 (s) | 34,5 | 4,08 | {f(v(P48, 's4load', 'unified', 'iw_ttft_p95', L2))} |")
w(f"| Vi phạm IW Bloom (%) | – | 86 | {f(v(P48, 's4load', 'unified', 'iw_sla_miss_%', B), 1)} |")
w(f"| Kết luận D18 | | Llama-2 dưới ngưỡng → D, dừng | Llama-2 {f(v(P48, 's4load', 'unified', 'iw_ttft_p95', L2) / 34.5)}x, dưới ngưỡng → D, dừng |\n")

# B. LT trace chính, theo mô hình
w("### LT trên trace chính (ARIMA-60), theo mô hình\n")
PAPER = {"reactive": ("362,25", ""), "lt_i": ("274,5", "−24,2"), "lt_u": ("291", "−19,7"), "lt_ua": ("277,5", "−23,4")}
for m, mt in ((L2, "Llama-2"), (B, "Bloom"), (None, "Tổng 4 mô hình")):
    w(f"**{mt}**\n")
    w("| Chiến lược | Bài báo IH (%) | v2.1 IH | v2.1 % so Reactive | T48 IH | T48 % so Reactive | v2.1 TTFT P95 (s) | T48 TTFT P95 (s) | v2.1 vi phạm IW (%) | T48 vi phạm IW (%) |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in ["reactive"] + LT:
        pp = f"{PAPER[r][0]} ({PAPER[r][1]})" if m == L2 and r != "reactive" else (PAPER[r][0] if m == L2 else "–")
        row = [TEN[r], pp]
        for P in (P21, P48):
            row += [f(ih(P, "lt", r, m)), "–" if r == "reactive" else f(p(ih(P, "lt", r, m), ih(P, "lt", "reactive", m)))]
        if m:
            row += [f(v(P, "lt", r, "iw_ttft_p95", m)) for P in (P21, P48)] + [f(v(P, "lt", r, "iw_sla_miss_%", m)) for P in (P21, P48)]
        else:
            row += ["–"] * 4
        w("| " + " | ".join(row) + " |")
    w("")

# C. oracle, 18 cấu hình
w("### Dòng chính: 18 cấu hình (Llama-2; đạt = tiết kiệm VÀ TTFT Q3, P95 ≤ +10% so Reactive)\n")
w("| Trace | Dự báo | Chiến lược | v2.1 IH L2 % | T48 IH L2 % | v2.1 tổng % | T48 tổng % | v2.1 TTFT P95 L2 (s) | T48 TTFT P95 L2 (s) | v2.1 đạt | T48 đạt |")
w("|---|---|---|---:|---:|---:|---:|---:|---:|:-:|:-:|")
O = {P: pd.read_csv(f"{P}/orc_full.csv") for P in (P21, P48)}


def ob(P, tr, s, fc, col):
    t = O[P]
    return float(t[(t.trace == tr) & (t.strategy == s) & (t.forecast == fc)][col].iloc[0])


def dat(P, tr, s, fc):
    q = p(ob(P, tr, s, fc, "ttft_q3_l2"), ob(P, tr, "reactive", "-", "ttft_q3_l2"))
    p9 = p(ob(P, tr, s, fc, "ttft_p95_l2"), ob(P, tr, "reactive", "-", "ttft_p95_l2"))
    return ob(P, tr, s, fc, "ih_l2_vs_R_%") < 0 and q <= 10 and p9 <= 10


n = {P21: 0, P48: 0}
for tr in ("lt", "nov2024"):
    for fc in ("ARIMA", "oracle", "oracle_smooth"):
        for s in LT:
            d = [dat(P, tr, s, fc) for P in (P21, P48)]
            n[P21] += d[0]
            n[P48] += d[1]
            w(f"| {'chính' if tr == 'lt' else 'Nov'} | {fc} | {TEN[s]} | " + " | ".join(
                [f(ob(P, tr, s, fc, "ih_l2_vs_R_%"), 1) for P in (P21, P48)] + [f(ob(P, tr, s, fc, "ih_total_vs_R_%"), 1) for P in (P21, P48)]
                + [f(ob(P, tr, s, fc, "ttft_p95_l2")) for P in (P21, P48)] + ["✔" if x else "✘" for x in d]) + " |")
w(f"| **Tổng đạt** | | | | | | | | | **{n[P21]}/18** | **{n[P48]}/18** |\n")
for P in (P21, P48):
    for tr in ("lt", "nov2024"):
        pass
w("Reactive Llama-2 (IH; TTFT P95): " + "; ".join(
    f"{'v2.1' if P == P21 else 'T48'} chính {f(ob(P, 'lt', 'reactive', '-', 'ih_l2'))} IH, {f(ob(P, 'lt', 'reactive', '-', 'ttft_p95_l2'))} s, Nov {f(ob(P, 'nov2024', 'reactive', '-', 'ih_l2'))} IH, {f(ob(P, 'nov2024', 'reactive', '-', 'ttft_p95_l2'))} s"
    for P in (P21, P48)) + ". Bài báo: chính 362,25 IH; Nov 302 IH.\n")

# D. week
w("### Cả tuần (`week`, Llama-2 và tổng)\n")
w("| Chiến lược | v2.1 IH L2 (% so R) | T48 IH L2 (% so R) | v2.1 tổng % | T48 tổng % | v2.1 TTFT P95 L2 (s) | T48 TTFT P95 L2 (s) | v2.1 vi phạm IW L2 (%) | T48 vi phạm IW L2 (%) |")
w("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
for r in ["reactive"] + LT:
    row = [TEN[r]]
    for P in (P21, P48):
        row.append(f(ih(P, "week4", r, L2)) + ("" if r == "reactive" else f" ({f(p(ih(P, 'week4', r, L2), ih(P, 'week4', 'reactive', L2)), 1)})"))
    row += ["–" if r == "reactive" else f(p(ih(P, "week4", r), ih(P, "week4", "reactive")), 1) for P in (P21, P48)]
    row += [f(v(P, "week4", r, "iw_ttft_p95", L2)) for P in (P21, P48)] + [f(v(P, "week4", r, "iw_sla_miss_%", L2)) for P in (P21, P48)]
    w("| " + " | ".join(row) + " |")
w("\nBài báo (§7.2.7, Fig. 16b): \"insights ... also apply\" (LT < Reactive cả tuần), không cho số.\n")

# E. θ177
w("### Phụ lục θ = 177 TPS (nếu–thì; % IH so Reactive, Bloom / Llama-2 / tổng)\n")
w("| Chiến lược | v2.1 θ repo | T48 θ repo | v2.1 θ 177 | T48 θ 177 |\n|---|---|---|---|---|")
for r in LT:
    row = [TEN[r]]
    for n_ in ("lt", "theta177"):
        for P in (P21, P48):
            row.append(" / ".join(f(p(ih(P, n_, r, m), ih(P, n_, "reactive", m)), 1) for m in (B, L2, None)))
    w("| " + " | ".join([row[0], row[1], row[2], row[3], row[4]]) + " |")
w("\nBài báo: θ Bloom 50–177 TPS (§2.1); tiết kiệm −24,2 / −19,7 / −23,4% Llama-2. Kết luận \"θ = 177 thì tiết kiệm đổi chiều\" giữ nguyên ở T48.\n")

# F. sens
w("### Độ nhạy (bản cắt 12–15h, khoảng cách tổng Reactive − LT-UA, %)\n")
S = {P: pd.read_csv(f"{P}/sens/SENSITIVITY.csv").set_index("yếu tố") for P in (P21, P48)}
w("| Yếu tố | v2.1 | T48 |\n|---|---:|---:|")
for k, lab in [("base", "gốc"), ("thm30", "θ −30%"), ("thp30", "θ +30%"), ("flat", "phút phẳng"), ("spike", "phút gai"), ("su300", "khởi động 300 s"),
               ("su1200", "khởi động 1200 s"), ("eps70", "ε 0,63"), ("eps100", "ε 1,0"), ("r50", "tải ×0,5"), ("r150", "tải ×1,5")]:
    w(f"| {lab} | {f(S[P21].loc[k, 'khoảng cách tổng %'], 1)} | {f(S[P48].loc[k, 'khoảng cách tổng %'], 1)} |")
w("")
open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
print(open(OUT, encoding="utf-8").read())
