"""Đối chiếu số v2.1 trong RESULTS.md và output/SO_DOI_V21.md với output của analyze_s4.py / analyze_oracle.py / analyze_sched.py / analyze_waste.py
trên kết quả v21. Mỗi claim = (file, đoạn chữ nguyên văn, danh sách giá trị tính lại; None = bỏ qua số đó, vd. số v2 hay số trong nhãn).
Số trong đoạn được tách theo thứ tự; lệch cho phép = nửa đơn vị chữ số cuối đang hiển thị (làm tròn hiển thị).
Dùng: python experiments/doi_chieu.py <repo> <thư mục phan_tich> [<gốc v21> [<gốc sens>]]   -> in danh sách, mã thoát 1 nếu có số sai/không tìm thấy đoạn.
<thư mục phan_tich> chứa đầu ra analyze_*.py (compare_with_paper.csv…, sens/SENSITIVITY.csv, sens/burst_cut.txt, sens/h100_cut.txt);
<gốc v21> mặc định là thư mục cha của <thư mục phan_tich> (có ram_dinh_theo_bai.json); <gốc sens> (chứa sens/, sens2/) mặc định = <gốc v21>.
output/SO_DOI_V21.md không có trên repo: thiếu file thì bỏ qua claim của nó (in số claim bỏ qua).
Chạy qua experiments/chay_phan_tich.py (CLAUDE.md luật 9).
Giai đoạn 5: thêm claim nhóm B vào CLAIMS_B rồi chạy lại."""
import io
import os
import re
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
if len(sys.argv) < 3:
    print(__doc__)
    sys.exit(2)
REPO, P = sys.argv[1], sys.argv[2]
V21 = sys.argv[3] if len(sys.argv) > 3 else os.path.dirname(os.path.abspath(P))
SENS_ROOT = sys.argv[4] if len(sys.argv) > 4 else V21
RES, SO = f"{REPO}/RESULTS.md", f"{REPO}/output/SO_DOI_V21.md"
B, L2, L31, L32 = "bloom-176b", "llama2-70b", "llama3.1-8b", "llama3.2-3b"
MODELS = [B, L2, L31, L32]
PAPER = {"lt_i": 24.21, "lt_u": 19.65, "lt_ua": 23.38}      # §7.2.1, tiết kiệm Llama-2 %
PAPER_S4 = 100 * (1 - 350.8 / 538.4)                          # Fig. 8a


# ---------- nguồn số ----------
_cache = {}


def s4(name):
    """compare_with_paper.csv của analyze_s4.py: hàng = mô hình, cột = '<bài>:<chỉ số>'."""
    if name not in _cache:
        _cache[name] = pd.read_csv(f"{P}/{name}/compare_with_paper.csv", index_col=0)
    return _cache[name]


def v(name, run, metric, model):
    return float(s4(name).loc[model, f"{run}:{metric}"])


def ih(name, run, model=None):
    return sum(v(name, run, "instance_hours", m) for m in MODELS) if model is None else v(name, run, "instance_hours", model)


def pct(a, b):
    return 100 * (a / b - 1)


orc = pd.read_csv(f"{P}/orc_lt.csv")                           # analyze_oracle.table(R, traces=('lt',))


def o(strategy, forecast, col):
    r = orc[(orc.strategy == strategy) & (orc.forecast == forecast)]
    assert len(r) == 1, (strategy, forecast)
    return float(r[col].iloc[0])


def sched(sla):
    """analyze_sched.py in bảng 2 tầng cột; đọc lại thành dict[(policy, chỉ số, tầng)]."""
    lines = open(f"{P}/sched_{sla}.txt", encoding="utf-8").read().splitlines()
    out = {}
    for l in lines[3:]:
        x = l.split()
        if len(x) == 9:
            pol, vals = x[0], list(map(float, x[1:]))
            for (met, tier), val in zip([(m, t) for m in ("n", "ttft_q3", "ttft_p95", "miss") for t in ("IW-F", "IW-N")], vals):
                out[(pol, met, tier)] = val
    return out


def waste():
    t = open(f"{P}/waste_lt.txt", encoding="utf-8").read().splitlines()
    out = {}
    for l in t[2:]:
        x = l.split()
        if len(x) == 5:
            out[x[0]] = {"events": float(x[3]), "total": float(x[4])}
    return out


S6, S60, W = sched("sla6"), sched("sla60"), waste()
U, S = "unified", "siloed"
LT = ["lt_i", "lt_u", "lt_ua"]
sav = {s: -o(s, "ARIMA", "ih_l2_vs_R_%") for s in LT}            # tiết kiệm Llama-2, số dương
savo = {s: -o(s, "oracle_smooth", "ih_l2_vs_R_%") for s in LT}
R_L2 = o("reactive", "-", "ih_l2")


def e2e_max_diff():
    return max(abs(pct(v("s4", U, "iw_e2e_p95", m), v("s4", S, "iw_e2e_p95", m))) for m in MODELS)


s4pct = -pct(ih("s4", U), ih("s4", S))
CLAIMS = [
    # ---------------- RESULTS.md ----------------
    (RES, "411,25 so với 595,75 (−31,0%, 0,89x); Unified 1,17x", [ih("s4", U), ih("s4", S), -s4pct, s4pct / PAPER_S4, ih("s4", U) / 350.8]),
    (RES, "Bloom 5,24 và 5,18 s (Unified xấu hơn 1,2%); Llama-2 5,16 và 6,22 s. Biên độ so bài báo 0,41x, 0,15x",
     [v("s4", U, "iw_ttft_p95", B), v("s4", S, "iw_ttft_p95", B), pct(v("s4", U, "iw_ttft_p95", B), v("s4", S, "iw_ttft_p95", B)),
      v("s4", U, "iw_ttft_p95", L2), v("s4", S, "iw_ttft_p95", L2), v("s4", U, "iw_ttft_p95", B) / 12.9, v("s4", U, "iw_ttft_p95", L2) / 34.5]),
    (RES, "tiết kiệm Llama-2 −20,2 / −20,0 / −20,2% nhưng TTFT P95 60,3 / 9,64 / 10,83 s (Reactive 2,60 s)",
     [-sav["lt_i"], -sav["lt_u"], -sav["lt_ua"], o("lt_i", "ARIMA", "ttft_p95_l2"), o("lt_u", "ARIMA", "ttft_p95_l2"), o("lt_ua", "ARIMA", "ttft_p95_l2"),
      o("reactive", "-", "ttft_p95_l2")]),
    (RES, "LT-I / LT-U / LT-UA Llama-2 −16,6 / −15,1 / −15,4% (0,69x / 0,77x / 0,66x), tổng −8,3 / −2,9 / −4,5%",
     [-savo[s] for s in LT] + [savo[s] / PAPER[s] for s in LT] + [o(s, "oracle_smooth", "ih_total_vs_R_%") for s in LT]),
    (RES, "TTFT Q3 +4 / +1 / +1%, P95 +9 / +4 / +4%, vi phạm IW 7,3 / 6,7 / 6,8% (Reactive 7,3%)",
     [pct(o(s, "oracle_smooth", "ttft_q3_l2"), o("reactive", "-", "ttft_q3_l2")) for s in LT]
     + [pct(o(s, "oracle_smooth", "ttft_p95_l2"), o("reactive", "-", "ttft_p95_l2")) for s in LT]
     + [o(s, "oracle_smooth", "miss_l2_%") for s in LT] + [o("reactive", "-", "miss_l2_%")]),
    (RES, "ARIMA: 384,0 (1,06x) → 306,25 / 307,25 / 306,5 (−20,2 / −20,0 / −20,2%; 0,84x / 1,02x / 0,86x); tổng −12,9 / −6,7 / −8,7%",
     [R_L2, R_L2 / 362.25] + [o(s, "ARIMA", "ih_l2") for s in LT] + [-sav[s] for s in LT] + [sav[s] / PAPER[s] for s in LT]
     + [o(s, "ARIMA", "ih_total_vs_R_%") for s in LT]),
    (RES, "(TTFT P95 Llama-2 9,6–60 s)", [o("lt_u", "ARIMA", "ttft_p95_l2"), o("lt_i", "ARIMA", "ttft_p95_l2")]),
    (RES, "Với oracle_smooth còn −15,1 đến −16,6% (0,66–0,77x)", [-savo["lt_u"], -savo["lt_i"], savo["lt_ua"] / PAPER["lt_ua"], savo["lt_u"] / PAPER["lt_u"]]),
    (RES, "(v2: Reactive 356,25, tiết kiệm −14,0 / −13,8 / −14,0%;", [None] * 4),
    (RES, "ARIMA: Llama-2 20,25 ≥ 20,18 ≥ 19,99% (cách nhau ≤ 0,26 điểm); tổng 12,9 ≥ 8,7 ≥ 6,7%. oracle_smooth: 16,6 ≥ 15,4 ≥ 15,1%",
     [sav["lt_i"], sav["lt_ua"], sav["lt_u"], max(sav.values()) - min(sav.values())]
     + [-o(s, "ARIMA", "ih_total_vs_R_%") for s in ("lt_i", "lt_ua", "lt_u")] + [savo[s] for s in ("lt_i", "lt_ua", "lt_u")]),
    (RES, "Bloom ≤ +5% ở mọi chỉ số (TTFT P95 4,38 → 4,57 / 4,58 s)",
     [None, v("lt", "reactive", "iw_ttft_p95", B), v("lt", "lt_u", "iw_ttft_p95", B), v("lt", "lt_ua", "iw_ttft_p95", B)]),
    ("BOUND", "Bloom ≤ +5% (max % lệch LT-U/LT-UA so Reactive, 6 chỉ số độ trễ + vi phạm IW)",
     max(pct(v("lt", s, m, B), v("lt", "reactive", m, B)) for s in ("lt_u", "lt_ua")
         for m in ("iw_ttft_q3", "iw_ttft_p95", "iw_e2e_q3", "iw_e2e_p95")) <= 5),
    (RES, "TTFT Q3 +11,7 / +12,0%, E2E Q3 +11,7 / +12,3%, E2E P95 +7,6 / +7,6%",
     [pct(o(s, "ARIMA", "ttft_q3_l2"), o("reactive", "-", "ttft_q3_l2")) for s in ("lt_u", "lt_ua")]
     + [pct(v("lt", s, "iw_e2e_q3", L2), v("lt", "reactive", "iw_e2e_q3", L2)) for s in ("lt_u", "lt_ua")]
     + [pct(v("lt", s, "iw_e2e_p95", L2), v("lt", "reactive", "iw_e2e_p95", L2)) for s in ("lt_u", "lt_ua")]),
    (RES, "**TTFT P95 2,60 → 9,64 / 10,83 s**", [o("reactive", "-", "ttft_p95_l2"), o("lt_u", "ARIMA", "ttft_p95_l2"), o("lt_ua", "ARIMA", "ttft_p95_l2")]),
    (RES, "Llama-2 TTFT Q3 1,55 → 2,02 s, P95 2,60 → 60,3 s",
     [o("reactive", "-", "ttft_q3_l2"), o("lt_i", "ARIMA", "ttft_q3_l2"), o("reactive", "-", "ttft_p95_l2"), o("lt_i", "ARIMA", "ttft_p95_l2")]),
    (RES, "Llama-2 1882,25 so với 384,0 (4,90x; 1,55x tỉ số bài báo); tổng 5587 so với 1826,75 (3,06x)",
     [ih("chiron", "chiron", L2), ih("chiron", "reactive", L2), ih("chiron", "chiron", L2) / ih("chiron", "reactive", L2),
      ih("chiron", "chiron", L2) / ih("chiron", "reactive", L2) / (1146 / 362.25), ih("chiron", "chiron"), ih("chiron", "reactive"),
      ih("chiron", "chiron") / ih("chiron", "reactive")]),
    (RES, "Bloom xấu hơn (TTFT P95 6,78 so với 4,38 s; E2E P95 +14%); Llama-2 tốt hơn 5–8% (2,46 so với 2,60 s; 223,3 so với 242,3 s)",
     [v("chiron", "chiron", "iw_ttft_p95", B), v("chiron", "reactive", "iw_ttft_p95", B),
      pct(v("chiron", "chiron", "iw_e2e_p95", B), v("chiron", "reactive", "iw_e2e_p95", B)),
      -pct(v("chiron", "chiron", "iw_ttft_p95", L2), v("chiron", "reactive", "iw_ttft_p95", L2)),
      -pct(v("chiron", "chiron", "iw_e2e_p95", L2), v("chiron", "reactive", "iw_e2e_p95", L2)),
      v("chiron", "chiron", "iw_ttft_p95", L2), v("chiron", "reactive", "iw_ttft_p95", L2),
      v("chiron", "chiron", "iw_e2e_p95", L2), v("chiron", "reactive", "iw_e2e_p95", L2)]),
    (RES, "Q3 bộ nhớ Llama-2 9,7% so với 51,1%, Bloom 43,2% so với 57,3%",
     [v("chiron", "chiron", "mem_util_q3_%", L2), v("chiron", "reactive", "mem_util_q3_%", L2),
      v("chiron", "chiron", "mem_util_q3_%", B), v("chiron", "reactive", "mem_util_q3_%", B)]),
    (RES, "Reactive 8,41 IH (235 lần) → LT-U 5,15 (−39%; 0,55x), LT-UA 5,84 (−31%; 0,44x), LT-I 8,25 (−2%; 117 lần)",
     [W["reactive"]["total"], W["reactive"]["events"], W["lt_u"]["total"], pct(W["lt_u"]["total"], W["reactive"]["total"]),
      -pct(W["lt_u"]["total"], W["reactive"]["total"]) / 70, W["lt_ua"]["total"], pct(W["lt_ua"]["total"], W["reactive"]["total"]),
      -pct(W["lt_ua"]["total"], W["reactive"]["total"]) / 70, W["lt_i"]["total"], pct(W["lt_i"]["total"], W["reactive"]["total"]), W["lt_i"]["events"]]),
    (RES, "34,8% và 2,5% (SLA IW-N 6 s; 60 s: 0,01%); Q3 1,47 / 0,85 s",
     [S6[("fcfs", "miss", "IW-F")], S6[("fcfs", "miss", "IW-N")], None, None, S60[("fcfs", "miss", "IW-N")],
      S6[("fcfs", "ttft_q3", "IW-F")], S6[("fcfs", "ttft_q3", "IW-N")]]),
    (RES, "IW-F 34,8 → 34,0%, IW-N 2,5 → 3,2%",
     [S6[("fcfs", "miss", "IW-F")], S6[("edf", "miss", "IW-F")], S6[("fcfs", "miss", "IW-N")], S6[("edf", "miss", "IW-N")]]),
    (RES, "IW-F 34,1% (EDF 34,0% thấp hơn); IW-N 3,3% (cao nhất)", [S6[("pf", "miss", "IW-F")], S6[("edf", "miss", "IW-F")], S6[("pf", "miss", "IW-N")]]),
    (RES, "IW-F 34,9% (cao nhất), IW-N 2,0% (thấp nhất)", [S6[("dpa", "miss", "IW-F")], S6[("dpa", "miss", "IW-N")]]),
    ("BOUND", "sched sla6: DPA IW-F cao nhất, IW-N thấp nhất; PF IW-N cao nhất; EDF IW-F thấp nhất",
     S6[("dpa", "miss", "IW-F")] == max(S6[(p, "miss", "IW-F")] for p in ("fcfs", "edf", "pf", "dpa"))
     and S6[("dpa", "miss", "IW-N")] == min(S6[(p, "miss", "IW-N")] for p in ("fcfs", "edf", "pf", "dpa"))
     and S6[("pf", "miss", "IW-N")] == max(S6[(p, "miss", "IW-N")] for p in ("fcfs", "edf", "pf", "dpa"))
     and S6[("edf", "miss", "IW-F")] == min(S6[(p, "miss", "IW-F")] for p in ("fcfs", "edf", "pf", "dpa"))),
]


def theta_row(strategy, th):
    name = "theta177" if th == "177" else "lt"
    r = "reactive"
    vals = [] if th == "-" else ([177] if th == "177" else [])
    vals += [ih(name, strategy, B), ih(name, strategy, L2), ih(name, strategy)]
    if strategy != r:
        vals += [pct(ih(name, strategy, B), ih(name, r, B)), pct(ih(name, strategy, L2), ih(name, r, L2)), pct(ih(name, strategy), ih(name, r))]
    vals += [v(name, strategy, "iw_ttft_p95", B), v(name, strategy, "iw_ttft_p95", L2), v(name, strategy, "iw_sla_miss_%", B), v(name, strategy, "iw_sla_miss_%", L2)]
    return vals


def theta_snip(label, th, vals_txt):
    return f"| {label} | {th} | {vals_txt}"


for line in open(RES, encoding="utf-8").read().splitlines():
    m = re.match(r"\| (Reactive|LT-I|LT-U|LT-UA) \| (\(không dùng θ\)|repo|177) \| [\d,]+ \| ", line)
    if m:
        st = {"Reactive": "reactive", "LT-I": "lt_i", "LT-U": "lt_u", "LT-UA": "lt_ua"}[m.group(1)]
        th = {"(không dùng θ)": "-", "repo": "repo", "177": "177"}[m.group(2)]
        CLAIMS.append((RES, line, theta_row(st, th)))
t177 = {s: (pct(ih("theta177", s), ih("theta177", "reactive")), pct(ih("theta177", s, L2), ih("theta177", "reactive", L2))) for s in LT}
CLAIMS += [
    (RES, "LT dùng nhiều giờ máy hơn Reactive (+11 đến +54% tổng, +21 đến +68% Llama-2)",
     [min(x[0] for x in t177.values()), max(x[0] for x in t177.values()), min(x[1] for x in t177.values()), max(x[1] for x in t177.values())]),
    (RES, "cả ba chiến lược LT dùng **nhiều** giờ máy hơn Reactive (+11 đến +54% tổng)",
     [min(x[0] for x in t177.values()), max(x[0] for x in t177.values())]),
    # ---------------- SO_DOI_V21.md ----------------
    (SO, "| IH Bloom | 242,25 / 203,25 (−16,1%) | **246,75 / 205,75 (−16,6%)** |", [None] * 3 + [ih("s4", S, B), ih("s4", U, B), pct(ih("s4", U, B), ih("s4", S, B))]),
    (SO, "| IH Llama-2 | 148,00 / 99,00 (−33,1%) | **147,00 / 99,50 (−32,3%)** |", [None] * 3 + [ih("s4", S, L2), ih("s4", U, L2), pct(ih("s4", U, L2), ih("s4", S, L2))]),
    (SO, "| IH Llama-3.1, Llama-3.2 | 101,00 / 53,00 | 101,00 / 53,00 (không đổi) |",
     [None, None, ih("s4", S, L31), ih("s4", U, L31)]),
    ("BOUND", "SO_DOI: IH Llama-3.2 bằng Llama-3.1 (101 / 53)", ih("s4", S, L32) == 101 and ih("s4", U, L32) == 53),
    (SO, "| **IH tổng** | 592,25 / 408,25 (−31,1%) | **595,75 / 411,25 (−31,0%)** |", [None] * 3 + [ih("s4", S), ih("s4", U), -s4pct]),
    (SO, "| Unified so với bài báo (350,8) | 1,16x | 1,17x |", [None, None, ih("s4", U) / 350.8]),
    (SO, "| TTFT P95 Bloom (s) | 5,15 / 5,06 (−1,7%) | **5,18 / 5,24 (+1,2%: Unified hơi xấu hơn)** |",
     [None] * 3 + [v("s4", S, "iw_ttft_p95", B), v("s4", U, "iw_ttft_p95", B), pct(v("s4", U, "iw_ttft_p95", B), v("s4", S, "iw_ttft_p95", B))]),
    (SO, "| TTFT P95 Llama-2 (s) | 5,39 / 4,73 (−12,2%) | **6,22 / 5,16 (−17,0%)** |",
     [None] * 3 + [v("s4", S, "iw_ttft_p95", L2), v("s4", U, "iw_ttft_p95", L2), pct(v("s4", U, "iw_ttft_p95", L2), v("s4", S, "iw_ttft_p95", L2))]),
    (SO, "| TTFT P95 Llama-3.1 / 3.2 (s) | 1,46 / 1,49; 1,15 / 1,15 | 1,46 / 1,49; 1,15 / 1,15 (không đổi) |",
     [None] * 4 + [v("s4", S, "iw_ttft_p95", L31), v("s4", U, "iw_ttft_p95", L31), v("s4", S, "iw_ttft_p95", L32), v("s4", U, "iw_ttft_p95", L32)]),
    (SO, "| E2E P95 Bloom (s) | 103,98 / 104,20 | 103,94 / 103,92 |", [None, None, v("s4", S, "iw_e2e_p95", B), v("s4", U, "iw_e2e_p95", B)]),
    (SO, "| E2E P95 Llama-2 (s) | 88,55 / 89,00 | 87,87 / 87,17 |", [None, None, v("s4", S, "iw_e2e_p95", L2), v("s4", U, "iw_e2e_p95", L2)]),
    (SO, "| E2E P95 Llama-3.1 / 3.2 (s) | 18,45 / 18,58; 10,28 / 10,29 | 18,45 / 18,60; 10,28 / 10,29 |",
     [None] * 4 + [v("s4", S, "iw_e2e_p95", L31), v("s4", U, "iw_e2e_p95", L31), v("s4", S, "iw_e2e_p95", L32), v("s4", U, "iw_e2e_p95", L32)]),
    (SO, "| Chênh E2E P95 lớn nhất (câu \"≤ 0,7%\") | 0,7% | 0,8% |", [None, None, e2e_max_diff()]),
    (SO, "| Bộ nhớ Bloom Q1 / trung vị / Q3 (%) | S 22,38 / 31,18 / 39,58; U 35,54 / 44,15 / 54,36 | S 21,93 / 31,11 / 39,58; U 35,53 / 44,10 / 54,07 |",
     [None] * 6 + [v("s4", r, f"mem_util_{q}_%", B) for r in (S, U) for q in ("q1", "median", "q3")]),
    (SO, "| Bộ nhớ Llama-2 Q1 / trung vị / Q3 (%) | S 7,48 / 12,12 / 24,19; U 15,37 / 23,92 / 42,40 | S 7,48 / 11,97 / 22,40; U 15,06 / 23,10 / 40,37 |",
     [None] * 6 + [v("s4", r, f"mem_util_{q}_%", L2) for r in (S, U) for q in ("q1", "median", "q3")]),
    (SO, "| Bộ nhớ Llama-3.1 Q1 / trung vị / Q3 (%) | S 0,40 / 0,79 / 1,32; U 0,79 / 1,58 / 2,65 | không đổi |",
     [v("s4", r, f"mem_util_{q}_%", L31) for r in (S, U) for q in ("q1", "median", "q3")]),
    (SO, "| Vi phạm SLA IW Bloom / Llama-2 (%) | S 27,99 / 11,12; U 27,81 / 10,89 | S 27,99 / 11,57; U 27,94 / 11,22 |",
     [None] * 4 + [v("s4", S, "iw_sla_miss_%", B), v("s4", S, "iw_sla_miss_%", L2), v("s4", U, "iw_sla_miss_%", B), v("s4", U, "iw_sla_miss_%", L2)]),
    (SO, "Unified < Siloed (✔); Table 1 vẫn ½, loại D (biên độ TTFT P95 so bài báo còn 0,41x và 0,15x)",
     [None, v("s4", U, "iw_ttft_p95", B) / 12.9, v("s4", U, "iw_ttft_p95", L2) / 34.5]),
    (SO, "nhưng Bloom giờ là +1,2% (xấu hơn chút), không còn −1,7%", [pct(v("s4", U, "iw_ttft_p95", B), v("s4", S, "iw_ttft_p95", B)), None]),
    (SO, "592,25 → 595,75, 31,07% → 30,97%", [None, ih("s4", S), None, s4pct]),
    (SO, "tổng (595,75 − 411,25) / 595,75 = 30,97%; Bloom 16,62%; Llama-2 32,31%",
     [ih("s4", S), ih("s4", U), ih("s4", S), s4pct, -pct(ih("s4", U, B), ih("s4", S, B)), -pct(ih("s4", U, L2), ih("s4", S, L2))]),
    (SO, "| IH Llama-2 Reactive | 356,25 | **384,00** |", [None, R_L2]),
    (SO, "| IH Llama-2 LT-I / LT-U / LT-UA | 306,25 / 307,0 / 306,5 | 306,25 / 307,25 / 306,5 |", [None] * 3 + [o(s, "ARIMA", "ih_l2") for s in LT]),
    (SO, "| Tiết kiệm Llama-2 | −14,0 / −13,8 / −14,0% | **−20,2 / −20,0 / −20,2%** |", [None] * 3 + [-sav[s] for s in LT]),
    (SO, "| IH tổng Reactive → LT | – → −8,7 / −4,7 / −6,0% | 1826,75 → 1590,75 / 1705,25 / 1668,5 (−12,9 / −6,7 / −8,7%) |",
     [None] * 3 + [o("reactive", "-", "ih_total")] + [o(s, "ARIMA", "ih_total") for s in LT] + [o(s, "ARIMA", "ih_total_vs_R_%") for s in LT]),
    (SO, "| TTFT P95 Llama-2 Reactive → LT | 2,64 → 60,31 / 9,79 / 9,75 s | 2,60 → 60,31 / 9,64 / 10,83 s |",
     [None] * 4 + [o("reactive", "-", "ttft_p95_l2")] + [o(s, "ARIMA", "ttft_p95_l2") for s in LT]),
    (SO, "| oracle_smooth Llama-2 LT-I / LT-U / LT-UA | −10,1 / −9,0 / −9,0% (324,25 IH ở LT-U) | **−16,6 / −15,1 / −15,4%** (320,25 / 326,0 / 324,75 IH) |",
     [None] * 4 + [-savo[s] for s in LT] + [o(s, "oracle_smooth", "ih_l2") for s in LT]),
    (SO, "| oracle_smooth TTFT P95 Llama-2 | +8 / +3 / +2% | +9 / +4 / +4% (2,84 / 2,70 / 2,70 s) |",
     [None] * 3 + [pct(o(s, "oracle_smooth", "ttft_p95_l2"), o("reactive", "-", "ttft_p95_l2")) for s in LT] + [o(s, "oracle_smooth", "ttft_p95_l2") for s in LT]),
    (SO, "| Chiron IH Llama-2 (so Reactive) | 1850,25 (5,19x) | 1882,25 (4,90x) |",
     [None, None, ih("chiron", "chiron", L2), ih("chiron", "chiron", L2) / ih("chiron", "reactive", L2)]),
    (SO, "| Chiron TTFT P95 Bloom / Llama-2 | 4,89 / 2,46 s | 6,78 / 2,46 s |", [None, None, v("chiron", "chiron", "iw_ttft_p95", B), v("chiron", "chiron", "iw_ttft_p95", L2)]),
    (SO, "| Lãng phí scale-up Reactive → LT-I / LT-U / LT-UA | 6,05 → 8,25 / 5,06 / 5,25 IH | 8,41 → 8,25 / 5,15 / 5,84 IH |",
     [None] * 4 + [W["reactive"]["total"], W["lt_i"]["total"], W["lt_u"]["total"], W["lt_ua"]["total"]]),
    (SO, "| sched (sla6, sla60), 8 bài | FCFS 34,76 / 2,50%, … |", [None, S6[("fcfs", "miss", "IW-F")], S6[("fcfs", "miss", "IW-N")]]),
]
# ---------------- nhóm B (8/11): nov2024, oracle cả 2 trace ----------------
OF = pd.read_csv(f"{P}/orc_full.csv")                           # analyze_oracle.table(R, O=R).round(4), phan_tich/orc4.py


def ob(tr, st, fc, col):
    r = OF[(OF.trace == tr) & (OF.strategy == st) & (OF.forecast == fc)]
    assert len(r) == 1, (tr, st, fc)
    return float(r[col].iloc[0])


def obp(tr, st, fc, col):                                       # % so Reactive cùng trace
    return pct(ob(tr, st, fc, col), ob(tr, "reactive", "-", col))


PAPER_NOV = {"lt_i": 100 * 75 / 302, "lt_u": 100 * 54 / 302, "lt_ua": 100 * 69 / 302}   # 302 → 227 / 248 / 233


def dat(tr, fc):
    return sum(ob(tr, s, fc, "ih_l2_vs_R_%") < 0 and obp(tr, s, fc, "ttft_q3_l2") <= 10 and obp(tr, s, fc, "ttft_p95_l2") <= 10 for s in LT)


N_DAT = sum(dat(tr, fc) for tr in ("lt", "nov2024") for fc in ("ARIMA", "oracle", "oracle_smooth"))
sv = lambda tr, s, fc: ob(tr, s, fc, "ih_l2_vs_R_%")


def waste_file(fn):
    out = {}
    for l in open(f"{P}/{fn}", encoding="utf-8").read().splitlines()[2:]:
        x = l.split()
        if len(x) == 5:
            out[x[0]] = {"events": float(x[3]), "total": float(x[4])}
    return out


WN = waste_file("waste_nov.txt")


def miss_file(fn):
    t = open(f"{P}/{fn}", encoding="utf-8").read()
    one = {r: (float(a), float(b)) for r, a, b in re.findall(r"(\w+): vi phạm SLA theo tầng ([\d.]+)%, SLA một tầng 60 s ([\d.]+)%", t)}
    net, top, lo, hi = re.search(r"ròng cả kỳ\): (\d+); 5 giờ .*?: (\d+), đỉnh dự báo / đỉnh thực ở các giờ đó ([\d.]+)–([\d.]+)", t).groups()
    hours = list(map(int, re.search(r"\[([\d, ]+)\]", t).group(1).split(",")))
    return one, int(net), int(top), float(lo), float(hi), hours


ML, MN = miss_file("miss_lt.txt"), miss_file("miss_nov.txt")
CT = {k: int(v) for k, v in re.findall(r"'(\w+)': (\d+)", open(f"{P}/can_thiep.txt", encoding="utf-8").read())}
q3n = [obp("nov2024", s, "oracle", "ttft_q3_l2") for s in LT]
p95n = [obp("nov2024", s, "oracle", "ttft_p95_l2") for s in LT]
p95os = [ob("nov2024", s, "oracle_smooth", "ttft_p95_l2") for s in LT]

# phân tích thứ tự ngược (oracle) + oracle_smooth Nov (8/11/2026)
TT = pd.read_csv(f"{P}/thu_tu_oracle_tom.csv").set_index(["trace", "chiến lược", "mô hình"])
tt = lambda tr, s_, m, c: float(TT.loc[(tr, s_, m), c])
SMT = open(f"{P}/smooth_nov.txt", encoding="utf-8").read()
SM_DEV = [float(x) for x in re.findall(r"= ([\d.]+)", "".join(l for l in SMT.splitlines() if l.startswith("[kiểm dự báo]")))]
SM_R = {tr: tuple(map(float, re.search(tr + r"\s+tổng 3 vùng llama2-70b : trung vị ([\d.]+), P90 [\d.]+, max ([\d.]+)", SMT).groups())) for tr in ("lt", "nov2024")}
SM_H = [(int(a), int(b), float(c)) for a, b, c in re.findall(r"giờ thiếu máy (\d+)/(\d+);.*?\((\d+\.\d)%\)", SMT)]
BD = {}                                                         # analyze_burst_day: thời gian hồi bộ nhớ Llama-2 (s) sau 3 burst
for l in open(f"{P}/burst_day.txt", encoding="utf-8"):
    if l.split() and l.split()[0] in ("reactive", "lt_i", "lt_u", "lt_ua"):
        BD[l.split()[0]] = [int(x) for x in re.findall(r"llama\s+(\d+)s", l)]
def rb(tr):                                                      # reactive_behavior.py: dòng 'tổng' (lấy lại spot, lãng phí instance-giờ)
    x = [l.split() for l in open(f"{P}/reactive_behavior_{tr}.txt", encoding="utf-8") if l.split()[:1] == ["tổng"]][0]
    return float(x[2]), float(x[6])


RBL, RBN = rb("lt"), rb("nov2024")

# GĐ5 (8/11/2026)
L4 = "llama4-sub"
np9 = lambda r: pct(ih("niw9", r, L2), ih("niw9", "reactive", L2))
np1 = lambda r: pct(ih("niw1", r, L2), ih("niw1", "reactive", L2))
ih5 = lambda r: sum(v("scale5", r, "instance_hours", m) for m in MODELS + [L4])
import json as _json
_rb = _json.load(open(f"{V21}/ram_dinh_theo_bai.json"))
RAMF = {h: max(x["dinh"] for x in _rb.values() if x["ho"] == h) / 2 ** 30 for h in ("burst", "h100", "niw", "scale5")}

CLAIMS_B = [
    (RES, "**v2.1, đủ 18 cấu hình: 8/18 đạt theo Llama-2 (v2: 7/18).**", [18, N_DAT, 18, None, 18]),
    (RES, "½ (giữ theo D23: 8/18, ARIMA 0/6)", [N_DAT, 18, dat("lt", "ARIMA") + dat("nov2024", "ARIMA"), 6]),
    (RES, "**oracle 2/3** — LT-I +1,3% (tốn hơn Reactive), LT-U −4,2%, LT-UA −7,6% (0,21x / 0,32x), tổng +4,2 / −1,6 / −1,7%, TTFT P95 2,50 / 2,52 / 2,52 s",
     [dat("lt", "oracle"), 3] + [sv("lt", s, "oracle") for s in LT] + [-sv("lt", s, "oracle") / PAPER[s] for s in ("lt_u", "lt_ua")]
     + [ob("lt", s, "oracle", "ih_total_vs_R_%") for s in LT] + [ob("lt", s, "oracle", "ttft_p95_l2") for s in LT]),
    (RES, "Trace Nov (Reactive 276,5 IH, TTFT P95 5,21 s): **ARIMA 0/3** — −36,7 / −33,1 / −33,2% nhưng TTFT P95 1179 / 1145 / 1145 s. **oracle 3/3** — "
          "−10,1 / −10,7 / −10,8% (0,41x / 0,60x / 0,47x), tổng +0,6 / −1,6 / −1,6%, TTFT Q3 −19 / −19 / −18%, P95 −42% (3,02 s). **oracle_smooth 0/3** — "
          "−34,5 / −31,0 / −31,0% nhưng TTFT Q3 +110 / +43 / +43%, P95 13,5–19,3 s.",
     [ob("nov2024", "reactive", "-", "ih_l2"), ob("nov2024", "reactive", "-", "ttft_p95_l2"), dat("nov2024", "ARIMA"), 3]
     + [sv("nov2024", s, "ARIMA") for s in LT] + [ob("nov2024", s, "ARIMA", "ttft_p95_l2") for s in LT] + [dat("nov2024", "oracle"), 3]
     + [sv("nov2024", s, "oracle") for s in LT] + [-sv("nov2024", s, "oracle") / PAPER_NOV[s] for s in LT]
     + [ob("nov2024", s, "oracle", "ih_total_vs_R_%") for s in LT] + q3n + [p95n[1], ob("nov2024", "lt_u", "oracle", "ttft_p95_l2"), dat("nov2024", "oracle_smooth"), 3]
     + [sv("nov2024", s, "oracle_smooth") for s in LT] + [obp("nov2024", s, "oracle_smooth", "ttft_q3_l2") for s in LT] + [min(p95os), max(p95os)]),
    ("BOUND", "Nov oracle: TTFT P95 cả 3 chiến lược làm tròn ra −42% và 3,02 s",
     all(abs(x + 42) <= 0.5 + 1e-6 for x in p95n)
     and all(abs(ob("nov2024", s, "oracle", "ttft_p95_l2") - 3.02) <= 0.005 + 1e-6 for s in LT)),
    (RES, "oracle: ngược, LT-UA 7,55 ≥ LT-U 4,17 ≥ LT-I −1,30% (LT-I tốn hơn Reactive). Nov: ARIMA 36,71 ≥ 33,18 ≥ 33,09% và oracle_smooth 34,54 ≥ 31,01 = 31,01% đạt; "
          "oracle ngược (LT-UA 10,85 ≥ LT-U 10,67 ≥ LT-I 10,13%)",
     [-sv("lt", s, "oracle") for s in ("lt_ua", "lt_u", "lt_i")] + [-sv("nov2024", s, "ARIMA") for s in ("lt_i", "lt_ua", "lt_u")]
     + [-sv("nov2024", s, "oracle_smooth") for s in ("lt_i", "lt_ua", "lt_u")] + [-sv("nov2024", s, "oracle") for s in ("lt_ua", "lt_u", "lt_i")]),
    (RES, "đỉnh dự báo ARIMA chỉ đạt 0,56–0,71 đỉnh thực (`lt`: giờ 5, 6, 8, 12, 13,", [ML[3], ML[4]] + ML[5]),
    ("BOUND", "lt: +14.098 trên ròng +11.340", ML[2] == 14098 and ML[1] == 11340),
    (RES, "0,38–0,61 (giờ 8–11, 14:", [MN[3], MN[4], MN[5][0], MN[5][3], MN[5][4]]),
    ("BOUND", "nov2024: giờ 8–11, 14; +108.278 / +117.095", MN[5] == [8, 9, 10, 11, 14] and MN[2] == 108278 and MN[1] == 117095),
    (RES, "vi phạm IW Llama-2 6,57% (Reactive 7,30%, LT-U ARIMA 9,57%); 5 giờ trên có 4695 vi phạm (Reactive 4696, LT-U ARIMA 18.794); TTFT P95 2,52 s (2,60 và 9,64 s). "
          "**Nhưng tiết kiệm cũng phần lớn mất:** Llama-2 368,0 IH (−4,2%), tổng 1797,25 (−1,6%)",
     [ob("lt", "lt_u", "oracle", "miss_l2_%"), ML[0]["reactive"][0], ML[0]["lt_u"][0], 5, CT["lt_u_oracle"], CT["reactive"],
      ob("lt", "lt_u", "oracle", "ttft_p95_l2"), ob("lt", "reactive", "-", "ttft_p95_l2"), ob("lt", "lt_u", "ARIMA", "ttft_p95_l2"),
      ob("lt", "lt_u", "oracle", "ih_l2"), sv("lt", "lt_u", "oracle"), ob("lt", "lt_u", "oracle", "ih_total"), ob("lt", "lt_u", "oracle", "ih_total_vs_R_%")]),
    ("BOUND", "can thiệp: LT-U ARIMA 18.794 vi phạm ở 5 giờ, khớp analyze_hourly_miss (18794 − 4696 = 14.098)",
     CT["lt_u"] == 18794 and CT["lt_u"] - CT["reactive"] == ML[2]),
    (RES, "(`nov2024`, 1859 lần, 43,56 IH): LT-I / LT-U / LT-UA 1,90 / 1,51 / 1,87 IH (−96 / −97 / −96%)",
     [WN["reactive"]["events"], WN["reactive"]["total"]] + [WN[s]["total"] for s in LT] + [pct(WN[s]["total"], WN["reactive"]["total"]) for s in LT]),
    (RES, "ARIMA: 276,5 (0,92x) → 175 / 185 / 184,75 (−36,7 / −33,1 / −33,2%; 1,48x / 1,85x / 1,45x); tổng −32,5 / −28,4 / −28,9%; thứ tự LT-I ≥ LT-UA ≥ LT-U đạt "
          "(LT-UA hơn LT-U 0,09 điểm). Hạ theo dòng chính: độ trễ ✘ (dòng dưới); với oracle chỉ còn −10,1 / −10,7 / −10,8% (0,41–0,60x), tổng +0,6 / −1,6 / −1,6%",
     [ob("nov2024", "reactive", "-", "ih_l2"), ob("nov2024", "reactive", "-", "ih_l2") / 302] + [ob("nov2024", s, "ARIMA", "ih_l2") for s in LT]
     + [sv("nov2024", s, "ARIMA") for s in LT] + [-sv("nov2024", s, "ARIMA") / PAPER_NOV[s] for s in LT] + [ob("nov2024", s, "ARIMA", "ih_total_vs_R_%") for s in LT]
     + [sv("nov2024", "lt_u", "ARIMA") - sv("nov2024", "lt_ua", "ARIMA")] + [sv("nov2024", s, "oracle") for s in LT]
     + [-sv("nov2024", "lt_i", "oracle") / PAPER_NOV["lt_i"], -sv("nov2024", "lt_u", "oracle") / PAPER_NOV["lt_u"]]
     + [ob("nov2024", s, "oracle", "ih_total_vs_R_%") for s in LT]),
    (RES, "TTFT P95 Llama-2 5,21 → 1179 / 1145 / 1145 s; vi phạm SLA một tầng 60 s (D4): Reactive 0,09%, LT-U = LT-UA 30,47%",
     [ob("nov2024", "reactive", "-", "ttft_p95_l2")] + [ob("nov2024", s, "ARIMA", "ttft_p95_l2") for s in LT] + [None, MN[0]["reactive"][1], MN[0]["lt_u"][1]]),
    ("BOUND", "Nov: SLA 60 s LT-U = LT-UA", MN[0]["lt_u"][1] == MN[0]["lt_ua"][1]),
    # Cách đọc số tiết kiệm của LT
    (RES, "LT tiết kiệm Llama-2 −20% trên trace chính", [sv("lt", "lt_u", "ARIMA")]),
    ("BOUND", "ARIMA trace chính: cả 3 làm tròn ra −20%", all(abs(sv("lt", s, "ARIMA") + 20) <= 0.5 for s in LT)),
    (RES, "độ trễ xấu đi (TTFT P95 9,6–60 s, so với 2,60 s)", [ob("lt", "lt_u", "ARIMA", "ttft_p95_l2"), ob("lt", "lt_i", "ARIMA", "ttft_p95_l2"), ob("lt", "reactive", "-", "ttft_p95_l2")]),
    (RES, "nhưng chỉ −15,1 đến −16,6% Llama-2 (0,66–0,77x bài báo) và −2,9 đến −8,3% tổng",
     [sv("lt", "lt_u", "oracle_smooth"), sv("lt", "lt_i", "oracle_smooth"), savo["lt_ua"] / PAPER["lt_ua"], savo["lt_u"] / PAPER["lt_u"],
      ob("lt", "lt_u", "oracle_smooth", "ih_total_vs_R_%"), ob("lt", "lt_i", "oracle_smooth", "ih_total_vs_R_%")]),
    (RES, "(từ +1,3% đến −7,6% Llama-2, tổng +4,2 đến −1,7%)",
     [max(sv("lt", s, "oracle") for s in LT), min(sv("lt", s, "oracle") for s in LT),
      max(ob("lt", s, "oracle", "ih_total_vs_R_%") for s in LT), min(ob("lt", s, "oracle", "ih_total_vs_R_%") for s in LT)]),
    (RES, "tiết kiệm −33 đến −37% (1,45–1,85x bài báo)",
     [max(sv("nov2024", s, "ARIMA") for s in LT), min(sv("nov2024", s, "ARIMA") for s in LT),
      min(-sv("nov2024", s, "ARIMA") / PAPER_NOV[s] for s in LT), max(-sv("nov2024", s, "ARIMA") / PAPER_NOV[s] for s in LT)]),
    (RES, "(1859 lần lấy lại spot hoặc khởi động mới, so với 65 / 51 / 63 lần của LT)", [WN["reactive"]["events"]] + [WN[s]["events"] for s in LT]),
    (RES, "tiết kiệm trên Nov chỉ còn −10,1 đến −10,8% (0,41–0,60x), tổng gần như không đổi (+0,6 đến −1,6%)",
     [max(sv("nov2024", s, "oracle") for s in LT), min(sv("nov2024", s, "oracle") for s in LT),
      min(-sv("nov2024", s, "oracle") / PAPER_NOV[s] for s in LT), max(-sv("nov2024", s, "oracle") / PAPER_NOV[s] for s in LT),
      max(ob("nov2024", s, "oracle", "ih_total_vs_R_%") for s in LT), min(ob("nov2024", s, "oracle", "ih_total_vs_R_%") for s in LT)]),
    (RES, "oracle_smooth trên Nov vẫn tiết kiệm −31 đến −35% nhưng làm xấu độ trễ (TTFT Q3 +43 đến +110%)",
     [max(sv("nov2024", s, "oracle_smooth") for s in LT), min(sv("nov2024", s, "oracle_smooth") for s in LT),
      min(obp("nov2024", s, "oracle_smooth", "ttft_q3_l2") for s in LT), max(obp("nov2024", s, "oracle_smooth", "ttft_q3_l2") for s in LT)]),
    (RES, "(8/18 cấu hình đạt cả hai vế)", [N_DAT, 18]),
    (RES, "vượt mục tiêu 169,5 IH tổng, trong đó 138 IH do sàn 2 instance mỗi endpoint",
     [tt("lt", "lt_i", "tổng", "IH vượt MT"), tt("lt", "lt_i", "tổng", "vượt MT do sàn 2"), None]),
    ("BOUND", "LT-I: không khối nào dưới MT (2 trace), 0 giảm giữa giờ, phần vượt ngoài sàn chỉ ở khối đầu giờ",
     all(tt(tr, "lt_i", "tổng", "IH dưới MT") == 0 and tt(tr, "lt_i", "tổng", "giảm giữa giờ") == 0
         and tt(tr, "lt_i", "tổng", "vượt MT ngoài sàn, ngoài khối đầu giờ") == 0 for tr in ("lt", "nov2024"))),
    (RES, "dưới mục tiêu 207,25 / 206,5 IH tổng (Llama-2 32,5 / 45), giảm giữa giờ 25 / 41 lần",
     [tt("lt", s_, "tổng", "IH dưới MT") for s_ in ("lt_u", "lt_ua")] + [tt("lt", s_, "llama2-70b", "IH dưới MT") for s_ in ("lt_u", "lt_ua")]
     + [tt("lt", s_, "tổng", "giảm giữa giờ") for s_ in ("lt_u", "lt_ua")]),
    (RES, "IH thừa so nhu cầu theo θ (sàn 2) LT-I / LT-U / LT-UA 99 / 148 / 146,25 tổng, IH thiếu 45,75 / 204 / 203,5",
     [None] + [tt("lt", s_, "tổng", "IH thừa") for s_ in LT] + [tt("lt", s_, "tổng", "IH thiếu") for s_ in LT]),
    ("BOUND", "Nov: mục tiêu ILP không khối nào vượt nhu cầu theo θ", all(tt("nov2024", s_, "tổng", "MT thừa so nhu cầu") == 0 for s_ in LT)),
    (RES, "(dưới mục tiêu 38,5 / 36,75 IH tổng), ba chiến lược cách nhau 0,72 điểm",
     [tt("nov2024", s_, "tổng", "IH dưới MT") for s_ in ("lt_u", "lt_ua")] + [max(sv("nov2024", s_, "oracle") for s_ in LT) - min(sv("nov2024", s_, "oracle") for s_ in LT)]),
    ("BOUND", "thu_tu_oracle: IH như S4 của Llama-2 trùng ORC (6 bài oracle)",
     all(abs(tt(tr, s_, "llama2-70b", "IH như S4") - ob(tr, s_, "oracle", "ih_l2")) < 1e-9 for tr in ("lt", "nov2024") for s_ in LT)),
    ("BOUND", "smooth_nov: oracle trùng TPM thực, oracle_smooth trùng trượt 60 phút (lệch 0, 2 trace)", len(SM_DEV) == 4 and max(SM_DEV) == 0),
    (RES, "Đỉnh 1 phút / đỉnh làm trơn trong giờ (Llama-2, cộng 3 vùng) có trung vị 1,66 (max 2,03) trên Nov, so với 1,18 (max 1,30) trên trace chính, "
          "nên trên Nov ILP thấy đỉnh thấp hơn khoảng 40%.",
     [None, None, SM_R["nov2024"][0], SM_R["nov2024"][1], SM_R["lt"][0], SM_R["lt"][1], 100 * (1 - 1 / SM_R["nov2024"][0])]),
    (RES, "12–13/24 giờ thiếu máy so với oracle cùng chiến lược, và các giờ này chứa 99,8–100% số request trễ hạn thêm",
     [min(a for a, _, _ in SM_H), max(a for a, _, _ in SM_H), SM_H[0][1], min(c for _, _, c in SM_H), max(c for _, _, c in SM_H)]),
    # burst, h100 (8/11/2026)
    (RES, "v2.1: vi phạm IW Llama-2 cả ngày LT-UA 38,56% so với LT-U 38,62% / LT-I 43,89%; TTFT Q3 604 so với 610 / 899 s; P95 2779 so với 2488 / 2701 s (LT-UA kém nhất).",
     [v("burst", r, "iw_sla_miss_%", L2) for r in ("lt_ua", "lt_u", "lt_i")] + [v("burst", r, "iw_ttft_q3", L2) for r in ("lt_ua", "lt_u", "lt_i")]
     + [v("burst", r, "iw_ttft_p95", L2) for r in ("lt_ua", "lt_u", "lt_i")]),
    ("BOUND", "burst: P95 LT-UA kém nhất trong 3 LT", v("burst", "lt_ua", "iw_ttft_p95", L2) == max(v("burst", r, "iw_ttft_p95", L2) for r in LT)),
    (RES, "sau burst 1 cả ba không hồi trong cửa sổ 3 giờ (10.798 s); sau burst 2: 3090 so với 4832 / 5180 s; sau burst 3: 4586 so với 4624 / 5336 s (v2: LT-UA thua LT-U ở burst 3). "
          "Reactive hồi trong 818–924 s, nhanh hơn mọi LT.",
     [None, None, None, BD["lt_ua"][1], BD["lt_u"][1], BD["lt_i"][1], None, BD["lt_ua"][2], BD["lt_u"][2], BD["lt_i"][2], None, min(BD["reactive"]), max(BD["reactive"])]),
    ("BOUND", "burst 1: cả 3 LT 10798 s", all(BD[r][0] == 10798 for r in LT)),
    (RES, "Llama-2 469,75 → 306,25 / 323,25 / 321,75 (−34,8 / −31,2 / −31,5%), tổng −28,6 / −20,6 / −24,3%",
     [ih("burst", "reactive", L2)] + [ih("burst", r, L2) for r in LT] + [pct(ih("burst", r, L2), ih("burst", "reactive", L2)) for r in LT]
     + [pct(ih("burst", r), ih("burst", "reactive")) for r in LT]),
    (RES, "A100 (trace chính, ARIMA) LT-UA Llama-2 −20,2% (0,72x), tổng −8,7%; H100 LT-UA −26,4%, tổng −11,5%.",
     [sv("lt", "lt_ua", "ARIMA"), -sv("lt", "lt_ua", "ARIMA") / 28.2, ob("lt", "lt_ua", "ARIMA", "ih_total_vs_R_%"),
      pct(ih("h100", "lt_ua", L2), ih("h100", "reactive", L2)), pct(ih("h100", "lt_ua"), ih("h100", "reactive"))]),
    (RES, "Reactive lấy lại spot nhiều hơn khoảng 5,9x trace chính: Llama-2 có 900 lần, so với 152, bỏ giờ đầu",
     [RBN[0] / RBL[0], RBN[0], RBL[0]]),
    (RES, "Tiết kiệm của LT trên Nov (ARIMA) cũng gần bài báo hơn: 1,45–1,85x, so với 0,84–1,02x ở trace chính.",
     [min(-sv("nov2024", s_, "ARIMA") / PAPER_NOV[s_] for s_ in LT), max(-sv("nov2024", s_, "ARIMA") / PAPER_NOV[s_] for s_ in LT),
      min(-sv("lt", s_, "ARIMA") / PAPER[s_] for s_ in LT), max(-sv("lt", s_, "ARIMA") / PAPER[s_] for s_ in LT)]),
    (RES, "với dự báo oracle, tiết kiệm trên Nov chỉ còn 0,41–0,60x, nên phần lớn",
     [min(-sv("nov2024", s_, "oracle") / PAPER_NOV[s_] for s_ in LT), max(-sv("nov2024", s_, "oracle") / PAPER_NOV[s_] for s_ in LT)]),
    (RES, "Bài `lt` Reactive của nhóm có 152 lần lấy lại spot cho Llama-2 sau giờ đầu, lãng phí 3,44 instance-giờ", [RBL[0], RBL[1]]),
    # SO_DOI nhóm B
    (SO, "| Nov IH Llama-2 Reactive | 254 | **276,5** |", [None, ob("nov2024", "reactive", "-", "ih_l2")]),
    (SO, "| Nov tiết kiệm Llama-2 ARIMA LT-I / LT-U / LT-UA | −31,1 / −27,2 / −27,2% | **−36,7 / −33,1 / −33,2%** |", [None] * 3 + [sv("nov2024", s_, "ARIMA") for s_ in LT]),
    (SO, "| Nov TTFT P95 Llama-2 Reactive → LT-I | 5,2 → 1160 s | 5,21 → 1179 s |", [None, None, ob("nov2024", "reactive", "-", "ttft_p95_l2"), ob("nov2024", "lt_i", "ARIMA", "ttft_p95_l2")]),
    (SO, "| Nov oracle tiết kiệm Llama-2 | −2,2 / −4,4 / −3,6% | **−10,1 / −10,7 / −10,8%** |", [None] * 3 + [sv("nov2024", s_, "oracle") for s_ in LT]),
    (SO, "| Nov oracle_smooth tiết kiệm Llama-2 | −28,7 / −24,9 / −24,9% | −34,5 / −31,0 / −31,0% |", [None] * 3 + [sv("nov2024", s_, "oracle_smooth") for s_ in LT]),
    (SO, "| Nov oracle_smooth TTFT Q3 Llama-2 so Reactive | +107 / +43 / +41% | +110 / +43 / +43% |", [None] * 3 + [obp("nov2024", s_, "oracle_smooth", "ttft_q3_l2") for s_ in LT]),
    (SO, "| Trace chính oracle tiết kiệm Llama-2 LT-I / LT-U / LT-UA | +9,2 / −3,2 / +4,3% | **+1,3 / −4,2 / −7,6%** |", [None] * 3 + [sv("lt", s_, "oracle") for s_ in LT]),
    (SO, "| Dòng chính: số cấu hình đạt (18) | 7 | **8** |", [18, None, N_DAT]),
    (SO, "| burst tiết kiệm Llama-2 | −29,9 / −26,0 / −26,6% | **−34,8 / −31,2 / −31,5%** |", [None] * 3 + [pct(ih("burst", r, L2), ih("burst", "reactive", L2)) for r in LT]),
    (SO, "| burst vi phạm IW Llama-2 cả ngày LT-UA; LT-U; LT-I | 38,8; 39,0; 43,9% | 38,56; 38,62; 43,89% |", [None] * 3 + [v("burst", r, "iw_sla_miss_%", L2) for r in ("lt_ua", "lt_u", "lt_i")]),
    (SO, "| burst hồi bộ nhớ Llama-2 sau burst 2 / burst 3, LT-UA; LT-U; LT-I | 3788 / 5068; 4800 / 4412; 5180 / 5336 s | **3090 / 4586**; 4832 / 4624; 5180 / 5336 s |",
     [None, None] + [None] * 6 + [BD["lt_ua"][1], BD["lt_ua"][2], BD["lt_u"][1], BD["lt_u"][2], BD["lt_i"][1], BD["lt_i"][2]]),
    (SO, "| H100 LT-UA tiết kiệm Llama-2 (tổng) | −17,0% (−7,6%) | **−26,4% (−11,5%)** |", [None, None, pct(ih("h100", "lt_ua", L2), ih("h100", "reactive", L2)), pct(ih("h100", "lt_ua"), ih("h100", "reactive"))]),
    (SO, "| A100 LT-UA tiết kiệm Llama-2 (tổng), trace chính | −14,0% (−6,0%) | **−20,2% (−8,7%)** |", [None, None, sv("lt", "lt_ua", "ARIMA"), ob("lt", "lt_ua", "ARIMA", "ih_total_vs_R_%")]),
    # GĐ5 (8/11/2026): niw9, niw1, scale5, dòng Chạy, Hạn chế
    (RES, "Llama-2 9:1: 388,25 → 308,25 / 316,0 / 310,75 (−20,6 / −18,6 / −20,0%); 1:1: 386,5 → 309,0 / 321,25 / 305,5 (−20,1 / −16,9 / −21,0%). "
          "LT-UA so với bài báo 0,76x và 0,95x; tổng LT-UA −8,5% và −9,8%.",
     [None, None, ih("niw9", "reactive", L2)] + [ih("niw9", r, L2) for r in LT] + [np9(r) for r in LT]
     + [None, None, ih("niw1", "reactive", L2)] + [ih("niw1", r, L2) for r in LT] + [np1(r) for r in LT]
     + [-np9("lt_ua") / 26.3, -np1("lt_ua") / 22, pct(ih("niw9", "lt_ua"), ih("niw9", "reactive")), pct(ih("niw1", "lt_ua"), ih("niw1", "reactive"))]),
    (RES, "(LT-UA 9:1 tiết kiệm ít hơn 1:1 khoảng 1,0 điểm)", [None] * 4 + [np9("lt_ua") - np1("lt_ua")]),
    ("BOUND", "niw: xu hướng 9:1 > 1:1 không lặp lại (LT-UA 9:1 tiết kiệm ít hơn 1:1)", np9("lt_ua") > np1("lt_ua")),
    (RES, "2,60 → 272,18 / 11,95 / 11,38 s (9:1) và 2,64 → 76,35 / 3,38 / 8,67 s (1:1)",
     [v("niw9", "reactive", "iw_ttft_p95", L2)] + [v("niw9", r, "iw_ttft_p95", L2) for r in LT] + [None, None]
     + [v("niw1", "reactive", "iw_ttft_p95", L2)] + [v("niw1", r, "iw_ttft_p95", L2) for r in LT] + [None, None]),
    (RES, "ở 1:1 LT-I chỉ hoàn thành trong ngày 43,4% số request NIW Bloom của Reactive, nên tiết kiệm tổng −19,5% của LT-I ở 1:1",
     [None, None, 100 * v("niw1", "lt_i", "niw_done", B) / v("niw1", "reactive", "niw_done", B), pct(ih("niw1", "lt_i"), ih("niw1", "reactive")), None, None]),
    ("BOUND", "niw1 niw_done Bloom 301.784 / 131.012 / 262.504 / 255.204, Llama-2 349.937 / 305.193 / 346.838 / 344.820",
     [v("niw1", r, "niw_done", m) for m in (B, L2) for r in ["reactive"] + LT] == [301784, 131012, 262504, 255204, 349937, 305193, 346838, 344820]),
    (RES, "IH 333,5 → 265,75 / 266,75 / 263,25 (−20,3 / −20,0 / −21,1%) ✔; tổng −15,5 / −10,5 / −12,6%; TTFT P95 2,70 → 256 / 239 / 218 s ✘",
     [ih("scale5", "reactive", L4)] + [ih("scale5", r, L4) for r in LT] + [pct(ih("scale5", r, L4), ih("scale5", "reactive", L4)) for r in LT]
     + [pct(ih5(r), ih5("reactive")) for r in LT] + [v("scale5", "reactive", "iw_ttft_p95", L4)] + [v("scale5", r, "iw_ttft_p95", L4) for r in LT]),
    (RES, "đo được 1,55 GB (h100) đến 3,38 GB (niw1", [RAMF["h100"], RAMF["niw"]]),
    ("BOUND", "RAM đỉnh: h100 thấp nhất, niw cao nhất trong các họ nhóm B", min(RAMF, key=RAMF.get) == "h100" and max(RAMF, key=RAMF.get) == "niw"),
    (RES, "TTFT P95 tuyệt đối của Unified chỉ 0,41x (Bloom) và 0,15x (Llama-2) Table 1",
     [v("s4", U, "iw_ttft_p95", B) / 12.9, v("s4", U, "iw_ttft_p95", L2) / 34.5, None]),
    (SO, "| niw9 tiết kiệm Llama-2 LT-UA (so bài báo) | −12,7% (0,48x) | **−20,0% (0,76x)** |", [None, None, np9("lt_ua"), -np9("lt_ua") / 26.3]),
    (SO, "| niw1 tiết kiệm Llama-2 LT-UA (so bài báo) | −16,0% (0,73x) | **−21,0% (0,95x)** |", [None, None, np1("lt_ua"), -np1("lt_ua") / 22]),
    (SO, "| niw9 / niw1 tiết kiệm tổng LT-UA | −5,4% / −5,4% | −8,5% / −9,8% |",
     [None, None, pct(ih("niw9", "lt_ua"), ih("niw9", "reactive")), pct(ih("niw1", "lt_ua"), ih("niw1", "reactive"))]),
    (SO, "| scale5 tiết kiệm `llama4-sub` LT-I / LT-U / LT-UA | −12,0 / −10,6 / −11,8% | **−20,3 / −20,0 / −21,1%** |",
     [None] * 3 + [pct(ih("scale5", r, L4), ih("scale5", "reactive", L4)) for r in LT]),
    (SO, "| scale5 TTFT P95 `llama4-sub` Reactive → LT-I / LT-U / LT-UA | 2,72 → 256 / 205 / 256 s | 2,70 → 256 / 239 / 218 s |",
     [None] * 4 + [v("scale5", "reactive", "iw_ttft_p95", L4)] + [v("scale5", r, "iw_ttft_p95", L4) for r in LT]),
    (SO, "biên độ 0,76x và 0,95x đều trong 0,5x–2x; v2 trượt vì 9:1 0,48x", [-np9("lt_ua") / 26.3, -np1("lt_ua") / 22, None, None, None, None, None]),
]

# GĐ6 (8/11/2026): sens / sens2 v2.1 — IH tính lại bằng analyze_s4 trên <gốc sens>; lãng phí lấy từ sens/SENSITIVITY.csv (2 chữ số, hiển thị 2 chữ số)
sys.path.insert(0, REPO)
from analyze_s4 import analyze as _an
SEN, SR = f"{REPO}/SENSITIVITY.md", SENS_ROOT
_ihc = {}


def sih(d, k, m=None):
    if (d, k) not in _ihc:
        _ihc[(d, k)] = _an(f"{SR}/{d}/{k}", 1)[0].instance_hours
    s = _ihc[(d, k)]
    return s.sum() if m is None else s[m]


def rdir(n):                                                     # Reactive của yếu tố n; không chạy thì dùng gốc (như analyze_sensitivity.py)
    return f"sens/{n}" if os.path.isdir(f"{SR}/sens/{n}/reactive") else "sens/base"


def gap(n, m=None):
    u = f"sens/{n}" if os.path.isdir(f"{SR}/sens/{n}/lt_ua") else "sens/base"
    return 100 * (1 - sih(u, "lt_ua", m) / sih(rdir(n), "reactive", m))


SC = pd.read_csv(f"{P}/sens/SENSITIVITY.csv").set_index("yếu tố")


def srow(n, k):                                                  # k số trong nhãn (bỏ qua) + 8 số của dòng bảng
    return [None] * k + [sih(rdir(n), "reactive"), SC.loc[n, "LT-UA IH"], gap(n), gap(n, L2), gap(n, B),
                         SC.loc[n, "Reactive lãng phí"], SC.loc[n, "LT-UA lãng phí"], -SC.loc[n, "giảm lãng phí %"]]


rng = lambda *ks: max(gap(k) for k in ("base",) + ks) - min(gap(k) for k in ("base",) + ks)
RNG = {"θ": rng("thm30", "thp30"), "phút": rng("flat", "spike"), "khởi động": rng("su300", "su1200"), "cooldown": rng("wait"),
       "ε": rng("eps70", "eps100"), "tải": rng("r50", "r150"), "β": rng("b7", "b13")}
_bc = {}
for line in open(f"{P}/sens/burst_cut.txt", encoding="utf-8"):
    if line.startswith("== "):
        case = line.split()[1].rstrip(":")
    m = re.match(r"(\w+)\s+IH\s+([\d.]+) \| SLA L2 ([\d.]+) Bl ([\d.]+) \|.*hồi bộ nhớ L2\s+(\d+) s", line)
    if m:
        _bc[(case, m[1])] = [float(x) for x in m.groups()[1:]]
_h1 = dict(re.findall(r"(\S+) R .* tong ([\d.]+)%", open(f"{P}/sens/h100_cut.txt", encoding="utf-8").read()))
H100 = [100 * (1 - sih("sens2/h100", "lt_ua", m) / sih("sens2/h100", "reactive", m)) for m in (None, L2, B)]

CLAIMS_B += [
    (SEN, "| Gốc | | 200,75 | 166,00 | **17,3%** | 15,9% | 21,6% | 3,25 → 2,19 (−33%) |", srow("base", 0)),
    (SEN, "| d) θ | −30% | 200,75 | 200,00 | **0,4%** | 2,1% | −0,2% | 3,25 → 3,75 (+16%) |", srow("thm30", 1)),
    (SEN, "| d) θ | +30% | 200,75 | 145,50 | **27,5%** | 16,9% | 37,6% | 3,25 → 1,01 (−69%) |", srow("thp30", 1)),
    (SEN, "| a) Dao động phút | phẳng | 227,50 | 156,25 | 31,3% | 21,4% | 40,1% | 4,66 → 1,69 (−64%) |", srow("flat", 0)),
    (SEN, "| a) Dao động phút | gai 1,77× | 236,50 | 162,50 | 31,3% | 16,4% | 41,8% | 5,11 → 1,85 (−64%) |", srow("spike", 1)),
    (SEN, "| b) Khởi động | 300 s | 197,75 | 166,50 | 15,8% | 11,7% | 20,8% | 1,66 → 1,22 (−26%) |", srow("su300", 1)),
    (SEN, "| b) Khởi động | 1200 s | 225,75 | 163,00 | 27,8% | 12,8% | 37,4% | 9,35 → 4,22 (−55%) |", srow("su1200", 1)),
    (SEN, "| c) Cooldown Reactive | chờ instance sẵn sàng | 192,00 | 166,00 | 13,5% | – | – | 2,18 → 2,19 |",
     [sih("sens/wait", "reactive"), sih("sens/base", "lt_ua"), gap("wait"), SC.loc["wait", "Reactive lãng phí"], SC.loc["base", "LT-UA lãng phí"]]),
    (SEN, "| d) ε | 0,63 | 200,75 | 168,50 | 16,1% | 11,8% | 21,2% | 3,25 → 0,91 (−72%) |", srow("eps70", 1)),
    (SEN, "| d) ε | 1,0 | 200,75 | 170,25 | 15,2% | 11,8% | 19,8% | 3,25 → 2,81 (−13%) |", srow("eps100", 1)),
    (SEN, "| d) β | 7% / 13% | 200,75 | 166,00 | 17,3% | 15,9% | 21,6% | không đổi |", srow("b7", 2)[:7]),
    ("BOUND", "sens β: b7 = b13 = gốc (IH và lãng phí)", all(SC.loc[k].drop(["yếu tố"], errors="ignore").equals(SC.loc["base"]) for k in ("b7", "b13"))),
    (SEN, "| e) Mức tải | ×0,5 | 121,75 | 97,75 | 19,7% | 22,7% | 26,4% | 1,31 → 0,20 (−85%) |", srow("r50", 0)),
    (SEN, "| e) Mức tải | ×1,5 | 283,50 | 235,25 | 17,0% | 10,0% | 22,1% | 1,88 → 4,23 (+125%) |", srow("r150", 0)),
    (SEN, "dao động 27,1 điểm, gần gấp 2 yếu tố đứng sau (v2: 21,3 điểm, gần gấp 3 lần)", [RNG["θ"], RNG["θ"] / max(x for k, x in RNG.items() if k != "θ"), None, None]),
    ("BOUND", "sens: θ có khoảng dao động lớn nhất", max(RNG, key=RNG.get) == "θ"),
    (SEN, "Dao động phút: 14,0 điểm.", [RNG["phút"]]),
    ("BOUND", "sens: phẳng và gai đều cho khoảng cách lớn hơn gốc (không đơn điệu)", gap("flat") > gap("base") and gap("spike") > gap("base")),
    (SEN, "Thời gian khởi động: 12,0 điểm (v2: dưới 3 điểm).", [RNG["khởi động"], None]),
    (SEN, "Cooldown 3,8 điểm; mức tải 2,7; ε 2,1.", [RNG["cooldown"], RNG["tải"], RNG["ε"]]),
    (SEN, "IH gốc 191,50 → 200,75, LT-UA gần như không đổi (167,00 → 166,00)", [None, sih("sens/base", "reactive"), None, sih("sens/base", "lt_ua")]),
    (SEN, "Ở v2.1, thời gian khởi động 12,0 điểm và dao động phút 14,0 điểm.", [RNG["khởi động"], RNG["phút"]]),
    (SEN, "| Trong 20 phút cuối giờ | Reactive | 337,0 | 34,75% | 42,60% | 898 s |", [None] + _bc[("burst_in", "reactive")]),
    (SEN, "| | LT-U | 165,0 | 59,82% | 58,55% | 4800 s |", _bc[("burst_in", "lt_u")]),
    (SEN, "| | **LT-UA** | 239,5 | **39,37%** | **47,80%** | **1524 s** |", _bc[("burst_in", "lt_ua")]),
    (SEN, "| Ngoài 20 phút cuối giờ | Reactive | 348,5 | 31,99% | 39,13% | 948 s |", [None] + _bc[("burst_out", "reactive")]),
    (SEN, "| | LT-U = LT-UA | 165,5 | 66,81% | 64,49% | 6600 s |", _bc[("burst_out", "lt_u")]),
    ("BOUND", "sens2: ngoài cửa sổ LT-U = LT-UA = LT-UA tắt luật giảm; trong cửa sổ LT-UA = LT-UA tắt luật giảm",
     _bc[("burst_out", "lt_u")] == _bc[("burst_out", "lt_ua")] == _bc[("burst_out", "lt_ua_nodown")] and _bc[("burst_in", "lt_ua")] == _bc[("burst_in", "lt_ua_nodown")]),
    ("BOUND", "sens2: trong cửa sổ LT-UA vi phạm ít hơn và hồi nhanh hơn LT-U",
     all(a < b for a, b in zip(_bc[("burst_in", "lt_ua")][1:], _bc[("burst_in", "lt_u")][1:]))),
    (SEN, "Bản cắt: A100 17,3%, H100 18,6% (Llama-2 15,0%, Bloom 25,5%), A100 vẫn không hơn H100. Tăng thời gian khởi động A100 lên 1200 s cho 27,8%",
     [gap("base")] + H100 + [None, gap("su1200")]),
    ("BOUND", "h100_cut.txt khớp tính lại", abs(float(_h1["sens2/h100"]) - H100[0]) < 0.006 and abs(float(_h1["sens/base"]) - gap("base")) < 0.006),
    (SEN, "lãng phí khi tăng máy của Reactive lên 9,35 instance-hours (gốc 3,25)", [SC.loc["su1200", "Reactive lãng phí"], SC.loc["base", "Reactive lãng phí"]]),
    (RES, "Bản cắt (v2.1): chỉ hơn khi burst rơi vào 20 phút cuối giờ (vi phạm Llama-2 LT-UA 39,37% so với LT-U 59,82%; ngoài cửa sổ LT-UA trùng LT-U)",
     [None, _bc[("burst_in", "lt_ua")][1], _bc[("burst_in", "lt_u")][1]]),
    (RES, "Bản cắt (v2.1): khởi động A100 1200 s cho khoảng cách Reactive − LT-UA 27,8% so với 17,3% ở gốc, tức **tăng** (v2: 11,2%, không tăng). Bản cắt A100 17,3% vẫn thấp hơn H100 18,6%",
     [None, gap("su1200"), gap("base"), None, gap("base"), H100[0]]),
    (SO, "| sens gốc: Reactive / LT-UA IH, khoảng cách tổng | 191,50 / 167,00, 12,8% | 200,75 / 166,00, 17,3% |",
     [None] * 3 + [sih("sens/base", "reactive"), sih("sens/base", "lt_ua"), gap("base")]),
    (SO, "| sens θ ±30%: khoảng cách tổng | 3,0% / 24,3% | 0,4% / 27,5% |", [None, None, gap("thm30"), gap("thp30")]),
    (SO, "| sens dao động phút phẳng / gai | 19,4% / 20,2% | 31,3% / 31,3% |", [None, None, gap("flat"), gap("spike")]),
    (SO, "| **sens khởi động 300 / 1200 s** | 10,3% / **11,2% (không tăng)** | 15,8% / **27,8% (tăng)** |", [None] * 4 + [gap("su300"), gap("su1200")]),
    (SO, "| sens Reactive chờ instance sẵn sàng | 8,5% | 13,5% |", [None, gap("wait")]),
    (SO, "| sens ε 0,63 / 1,0 | 13,3% / 10,8% | 16,1% / 15,2% |", [None] * 4 + [gap("eps70"), gap("eps100")]),
    (SO, "| sens tải ×0,5 / ×1,5 | 13,8% / 11,7% | 19,7% / 17,0% |", [None, None, gap("r50"), gap("r150")]),
    (SO, "| sens2 burst trong cửa sổ: vi phạm Llama-2 LT-UA / LT-U | 39,4% / 59,4% | 39,37% / 59,82% |", [None, None, _bc[("burst_in", "lt_ua")][1], _bc[("burst_in", "lt_u")][1]]),
    (SO, "| sens2 bản cắt A100 / H100 | 12,8% / 13,5% | 17,3% / 18,6% |", [None, None, gap("base"), H100[0]]),
    (SO, "(dao động phút 14,0 điểm, khởi động 12,0 điểm)", [RNG["phút"], RNG["khởi động"]]),
]

# week v2.1 (11/11/2026; LT-I chạy lần 3 theo D35): S4 week 4 bài (phan_tich/week4), analyze_week, analyze_hourly_miss, fig16b_week
WT = open(f"{P}/week4_ngay.txt", encoding="utf-8").read()
WS = {k: dict((r, float(x)) for r, x in re.findall(r"(\w+) ([\d.]+) \(", WT.split(k + ":")[1].splitlines()[0])) for k in ("ngày thường", "cuối tuần")}
wsp = lambda k, r: pct(WS[k][r], WS[k]["reactive"])
WCN = [float(x) for x in re.search(r"^CN\s+(.*)$", WT, re.M).group(1).split()]  # ih, miss × reactive, lt_i, lt_u, lt_ua, rồi vs_reactive
MW = miss_file("week_miss.txt")
wv = lambda r, m: v("week4", r, m, L2)
wp = lambda r, m=L2: pct(ih("week4", r, m), ih("week4", "reactive", m))
F16 = {(r, k): tuple(map(float, re.search(rf"{r} P95 gộp ([\d.]+) s, trung vị khối 3 h ([\d.]+) s", open(f"{P}/week4_fig16b.txt", encoding="utf-8").read().split(k + ":")[1].splitlines()[0]).groups()))
       for r in ("reactive", "lt_i", "lt_u", "lt_ua") for k in ("ngày thường", "cuối tuần")}
F16T = pd.read_csv(f"{P}/week4_fig16b.csv", index_col=0)
CLAIMS_B += [
    (RES, "LT-I / LT-U / LT-UA: Llama-2 2360,75 → 1831 / 1876,25 / 1820 (−22,4 / −20,5 / −22,9%); tổng 11155,75 → 9214,75 / 9993,75 / 9670 (−17,4 / −10,4 / −13,3%)",
     [ih("week4", r, L2) for r in ["reactive"] + LT] + [wp(r) for r in LT] + [ih("week4", r) for r in ["reactive"] + LT] + [wp(r, None) for r in LT]),
    ("BOUND", "week: số Reactive/LT-U/LT-UA của S4 4 bài trùng S4 3 bài", all(abs(v("week4", r, m, L2) - v("week", r, m, L2)) < 1e-9
                                                                            for r in ("reactive", "lt_u", "lt_ua") for m in ("instance_hours", "iw_ttft_p95", "iw_sla_miss_%"))),
    (RES, "Ngày thường: LT-U −8,0 so với LT-UA −11,1% (cách 3,1 điểm); thứ Bảy, Chủ Nhật: −20,0 so với −22,1% (cách 2,1 điểm). Vi phạm IW Chủ Nhật: LT-UA 7,65%, LT-U 6,36%",
     [wsp("ngày thường", "lt_u"), wsp("ngày thường", "lt_ua"), wsp("ngày thường", "lt_u") - wsp("ngày thường", "lt_ua"),
      wsp("cuối tuần", "lt_u"), wsp("cuối tuần", "lt_ua"), wsp("cuối tuần", "lt_u") - wsp("cuối tuần", "lt_ua"), WCN[7], WCN[5]]),
    (RES, "TTFT P95 Llama-2 2,54 so với 14,15 / 2,86 / 2,96 s, vi phạm IW 6,94 so với 10,24 / 8,18 / 8,58%",
     [wv(r, "iw_ttft_p95") for r in ["reactive"] + LT] + [wv(r, "iw_sla_miss_%") for r in ["reactive"] + LT]),
    (RES, "| Ngày thường, P95 gộp | 2,62 | 20,36 | 2,88 | 3,44 |", [F16[(r, "ngày thường")][0] for r in ["reactive"] + LT]),
    (RES, "| Ngày thường, trung vị P95 các khối | 2,43 | 2,79 | 2,75 | 2,78 |", [F16[(r, "ngày thường")][1] for r in ["reactive"] + LT]),
    (RES, "| Cuối tuần, P95 gộp | 2,24 | 2,85 | 2,39 | 2,48 |", [F16[(r, "cuối tuần")][0] for r in ["reactive"] + LT]),
    (RES, "| Cuối tuần, trung vị P95 các khối | 2,24 | 2,37 | 2,35 | 2,40 |", [F16[(r, "cuối tuần")][1] for r in ["reactive"] + LT]),
    (RES, "ngày thường +0,56 s (P95 gộp), +0,03 s (trung vị khối); cuối tuần +0,09 s, +0,05 s",
     [F16[("lt_ua", k)][i] - F16[("lt_u", k)][i] for k in ("ngày thường", "cuối tuần") for i in (0, 1)]),
    (RES, "(LT-I / LT-U / LT-UA 1508,53 / 1673,92 / 1879,84 s; Reactive 2,60 s) và thứ Ba 6–9 h (882,32 / 821,36 / 934,97 s)",
     [F16T.loc["T4 12h", r] for r in LT] + [F16T.loc["T4 12h", "reactive"], 6, 9] + [F16T.loc["T3 06h", r] for r in LT]),
    ("BOUND", "fig16b: khối xấu nhất của cả 3 LT là T4 12h", all(F16T[r].idxmax() == "T4 12h" for r in LT)),
    ("BOUND", "fig16b: TTFT P95 cả tuần khớp S4 (kiểm trong week4_fig16b.txt)", all(
        abs(float(re.search(rf"{r}: TTFT P95 cả tuần ([\d.]+)", open(f"{P}/week4_fig16b.txt", encoding="utf-8").read()).group(1)) - wv(r, "iw_ttft_p95")) < 0.006
        for r in ["reactive"] + LT)),
    (RES, "`week` 0,36–0,67 (giờ 12, 14, 104, 132, 158: +40.317 trên ròng +35.614)", [MW[3], MW[4]] + MW[5]),
    ("BOUND", "week: +40.317 trên ròng +35.614", MW[2] == 40317 and MW[1] == 35614),
    ("BOUND", "week: tầng IW Llama-2 analyze_hourly_miss = S4 (6,94 / 8,18 / 8,58)", all(abs(MW[0][r][0] - wv(r, "iw_sla_miss_%")) < 0.01 for r in ("reactive", "lt_u", "lt_ua"))),
    (SO, "| Cả tuần Llama-2 so Reactive (LT-I / LT-U / LT-UA) | −14,0 / −11,6 / −13,2% | −22,4 / −20,5 / −22,9% |", [None] * 3 + [wp(r) for r in LT]),
    (SO, "| Cả tuần tổng 4 mô hình | −12,5 / −5,4 / −6,5% | −17,4 / −10,4 / −13,3% |", [4] + [None] * 3 + [wp(r, None) for r in LT]),
    (SO, "| Ngày thường LT-U / LT-UA, khoảng cách | −3,3 / −4,1%, 0,8 điểm | −8,0 / −11,1%, 3,1 điểm |",
     [None] * 3 + [wsp("ngày thường", "lt_u"), wsp("ngày thường", "lt_ua"), wsp("ngày thường", "lt_u") - wsp("ngày thường", "lt_ua")]),
    (SO, "| Cuối tuần LT-U / LT-UA, khoảng cách | −13,8 / −15,7%, 1,9 điểm | −20,0 / −22,1%, 2,1 điểm |",
     [None] * 3 + [wsp("cuối tuần", "lt_u"), wsp("cuối tuần", "lt_ua"), wsp("cuối tuần", "lt_u") - wsp("cuối tuần", "lt_ua")]),
    (SO, "| TTFT P95 Llama-2 Reactive → LT-U / LT-UA | 2,56 → 2,86 / 2,87 s | 2,54 → 2,86 / 2,96 s |", [None] * 3 + [wv(r, "iw_ttft_p95") for r in ("reactive", "lt_u", "lt_ua")]),
    (SO, "| Vi phạm IW Llama-2 Reactive → LT-U / LT-UA | 7,0 → 8,1 / 8,5% | 6,94 → 8,18 / 8,58% |", [None] * 3 + [wv(r, "iw_sla_miss_%") for r in ("reactive", "lt_u", "lt_ua")]),
    (SO, "| TTFT P95 Llama-2 LT-I; vi phạm IW LT-I | – | 14,15 s; 10,24% |", [wv("lt_i", "iw_ttft_p95"), wv("lt_i", "iw_sla_miss_%")]),
    (SO, "khoảng cách ngày thường (3,1 điểm) lớn hơn cuối tuần (2,1 điểm)",
     [wsp("ngày thường", "lt_u") - wsp("ngày thường", "lt_ua"), wsp("cuối tuần", "lt_u") - wsp("cuối tuần", "lt_ua")]),
]

STRIP = [r"[A-Za-zÀ-ỹ§_]+[-.]?\d+(?:\.\d+)?[a-z]*", r"\d+\.\d+", r"\b\d+[a-wyz]\b"]
NUM = re.compile(r"(?:(?<=[\s(|*/;:→≥≤=–])|^)([−+]?)(\d+(?:,\d+)?)")


def nums(snip):
    t = snip
    for p in STRIP:
        t = re.sub(p, " ", t)
    out = []
    for sgn, n in NUM.findall(t):
        d = len(n.split(",")[1]) if "," in n else 0
        x = float(n.replace(",", "."))
        out.append((sgn + n, -x if sgn == "−" else x, d))
    return out


texts = {f: open(f, encoding="utf-8").read() for f in (RES, SO, SEN) if os.path.exists(f)}
n_num, bad, skip = 0, [], 0
for f, snip, vals in CLAIMS + CLAIMS_B:
    if f == "BOUND":
        n_num += 1
        if not vals:
            bad.append(("BOUND", snip, "điều kiện SAI"))
        continue
    if f not in texts:
        skip += 1
        continue
    if snip not in texts[f]:
        bad.append((f, snip, "KHÔNG TÌM THẤY đoạn chữ")); continue
    ns = nums(snip)
    if len(ns) != len(vals):
        bad.append((f, snip, f"tách được {len(ns)} số {[x[0] for x in ns]} nhưng có {len(vals)} giá trị")); continue
    for (txt, shown, d), val in zip(ns, vals):
        if val is None:
            continue
        n_num += 1
        tol = 0.5 * 10 ** -d + 1e-6
        if abs(shown - val) > tol:
            bad.append((f.split("/")[-1], snip[:90], f"'{txt}' nhưng tính lại = {val:.4f}"))
print(f"Đối chiếu: {n_num} số v2.1, {len(bad)} sai" + (f"; bỏ qua {skip} claim vì thiếu file" if skip else ""))
for b in bad:
    print(" -", " | ".join(b))
sys.exit(1 if bad else 0)
