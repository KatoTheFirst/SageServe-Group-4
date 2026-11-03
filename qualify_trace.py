"""
Cổng trace T1–T9 theo TRACE_SPEC.md. Chỉ chấm theo §2–§3, §4, §7.1 của bài báo, không dùng kết quả §7.

Dùng: python qualify_trace.py <trace> --role t7|t11 [--week <trace tuần>] [--day0 N] [--week_day N] [--forecast <thư mục>]
                              [--reactive <bài Reactive>] [--gpu a100|h100] [--variant niw|burst] [--s4]
--day0: thứ của ngày 0 trong trace tuần (0 = Thứ Hai; trace ghép bắt đầu thứ Sáu = 4). --week_day: ngày của trace tuần ứng với trace.
Thoát mã 1 nếu có FAIL. Dòng N/A và INFO không tính.
"""
import argparse
import glob
import os
import re
import subprocess
import sys

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import acf

A, B = "bloom-176b", "llama2-70b"
Q = {"a100": {B: (68, 293), A: (50, 177)}, "h100": {B: (95, 522), A: (82, 397)}}    # §2.1
T6_BAND = {"t7": {"IW-F": (1.00, 1.31), "IW-N": (1.00, 1.38), "NIW": (1.36, 2.13)}, "t11": {"IW": (1.42, 2.21), "NIW": (3.0, 4.7)}}
COLS = ["scenario", "model_type", "client_tenant", "arrival_timestamp", "prompt_size", "token_size"]
ROOT = os.path.dirname(os.path.abspath(__file__))
rows = []


def gate(code, name, ok, value, need):
    state = "N/A" if ok is None else "INFO" if ok == "info" else "PASS" if ok else "FAIL"
    rows.append((code, name, state, value, need))


def inside(v, band):
    return band[0] <= v <= band[1]


def load(path):
    d = pd.read_csv(path, usecols=COLS)
    d["tier"] = d.scenario
    d["iw"] = d.scenario != "NIW"
    return d


def ps(d, mask, hours):
    return float(acf(d[mask].groupby((d[mask].arrival_timestamp // 3600).astype(int)).size().reindex(range(hours), fill_value=0), nlags=24)[24])


def per_minute_ratio(d, mask):
    """Giờ cao điểm là giờ TPS IW lớn nhất. Trả (max/median, CV) của TPS theo phút trong giờ đó."""
    tok = d.prompt_size + d.token_size
    h = (d.arrival_timestamp // 3600).astype(int)
    peak = tok[d.iw].groupby(h[d.iw]).sum().idxmax()
    sel = mask & (h == peak)
    s = tok[sel].groupby((d.arrival_timestamp[sel] // 60).astype(int)).sum()
    s = s.reindex(range(peak * 60, (peak + 1) * 60), fill_value=0)
    return float(s.max() / s.median()), float(s.std() / s.mean())


def check_forecasts(folder):
    """T7d: dự báo canh phút tròn, mỗi giờ đủ 60 phút, phát hành đúng đầu giờ."""
    bad = []
    files = glob.glob(f"{folder}/*_arima.csv")
    for f in files:
        x = pd.read_csv(f)
        x = x[x.Time >= 3600]
        h = x.Time // 3600
        if (x.Time % 60).any() or (x.groupby(h).size() != 60).any() or (x.issue_time != h * 3600).any():
            bad.append(os.path.basename(f))
    return files, bad


def skip_hours_shared():
    """T7e: một tham số skip_hours áp cho mọi bài trong một lần gọi."""
    s4, waste = open(f"{ROOT}/analyze_s4.py", encoding="utf-8").read(), open(f"{ROOT}/analyze_waste.py", encoding="utf-8").read()
    return "analyze(run, a.skip_hours)" in s4 and "a.skip_hours" in waste


def t2_t3(w, a):
    hours = int(w.arrival_timestamp.max() // 3600) + 1
    weekday = ((w.arrival_timestamp // 86400).astype(int) + a.day0) % 7
    if a.role == "t7":
        for name, mask, band in (("IW-F A", (w.tier == "IW-F") & (w.model_type == A), (0.65, 1.00)),
                                 ("IW-N A", (w.tier == "IW-N") & (w.model_type == A), (0.55, 0.85)),
                                 ("IW-N B", (w.tier == "IW-N") & (w.model_type == B), (0.25, 0.55))):
            v = ps(w, mask, hours)
            gate("T2", f"ps {name}", inside(v, band), f"{v:.2f}", f"{band[0]}–{band[1]}")
    else:
        v = ps(w, w.iw & (w.model_type == A), hours)
        gate("T2", "ps IW A", "info", f"{v:.2f}", "bài báo không cho số Nov")
    for m in sorted(w.model_type.unique()):
        v = ps(w, (w.tier == "NIW") & (w.model_type == m), hours)
        gate("T2", f"ps NIW {m}", v <= 0.336, f"{v:.2f}", "≤ 0,336")

    def weekend_ratio(mask):
        per_day = w[mask].groupby(weekday[mask]).size()
        return float(per_day.reindex([5, 6]).mean() / per_day.reindex(range(5)).mean())
    iw_mask = (w.tier == "IW-F") if a.role == "t7" else w.iw
    v = weekend_ratio(iw_mask)
    gate("T3", "cuối tuần/ngày thường IW" + ("-F" if a.role == "t7" else ""), v <= 0.40, f"{v:.2f}", "≤ 0,40")
    v = weekend_ratio(w.tier == "NIW")
    gate("T3", "cuối tuần/ngày thường NIW", inside(v, (0.4, 1.2)), f"{v:.2f}", "0,4–1,2")
    per_day = w[w.iw].groupby((w.arrival_timestamp[w.iw] // 86400).astype(int)).size()
    low = sorted(((per_day.nsmallest(2).index + a.day0) % 7).tolist())
    gate("T7b", "hai ngày tải thấp nhất là cuối tuần", low == [5, 6], f"thứ {low} (0 = Thứ Hai)", "[5, 6]")


def t4(d, a):
    regions = d.client_tenant.nunique()
    if regions == 1:
        gate("T4", "lệch vùng", None, "trace 1 vùng", "—")
        return
    if a.role == "t11":
        c = d[d.iw].groupby("client_tenant").size()
        v = float(c.max() / c.min())
        gate("T4", "IW max/min giữa vùng", v <= 1.5, f"{v:.2f} (W/C/E {c.get(0, 0):,}/{c.get(1, 0):,}/{c.get(2, 0):,})", "≤ 1,5")
        return
    f = d[d.tier == "IW-F"].groupby("client_tenant").size()
    gate("T4", "IW-F E > C > W", f[2] > f[1] > f[0], f"{f[0]:,}/{f[1]:,}/{f[2]:,}", "E > C > W")
    x = d[(d.tier == "IW-F") & (d.model_type == A)].groupby("client_tenant").size()
    v = float(x[2] / x[0])
    gate("T4", "A IW-F East/West", inside(v, (3, 7)), f"{v:.2f}", "3–7")
    y = d[(d.tier == "IW-F") & (d.model_type == B)].groupby("client_tenant").size()
    gate("T4", "B IW-F cao nhất ở Central", y.idxmax() == 1, f"vùng {y.idxmax()}", "1")
    z = d[(d.tier == "IW-N") & (d.model_type == B)].groupby("client_tenant").size()
    gate("T4", "B IW-N cao nhất ở West", z.idxmax() == 0, f"vùng {z.idxmax()}", "0")
    n = d[d.tier == "NIW"].groupby("client_tenant").size()
    v = float(100 * n.get(0, 0) / n.sum())
    gate("T4", "NIW ở West", v <= 10, f"{v:.1f}%", "≤ 10%")


def t5(d):
    iw = d[d.iw]
    for m, x in iw.groupby("model_type"):
        i, o, c = 100 * (x.prompt_size > 1000).mean(), 100 * (x.token_size < 1000).mean(), 100 * (x.prompt_size >= 8192).mean()
        gate("T5", f"token {m}", i > 50 and o > 50 and c <= 10, f"input>1k {i:.0f}%, output<1k {o:.0f}%, cắt {c:.1f}%", "> 50, > 50, ≤ 10")


def t6(d, a):
    if a.variant == "burst":
        gate("T6", "dao động mức phút", None, "trace burst cố ý đổi", "—")
        return
    for tier, band in T6_BAND[a.role].items():
        mask = d.iw if tier == "IW" else d.tier == tier
        r, cv = per_minute_ratio(d, mask)
        gate("T6", f"max/median {tier}", inside(r, band), f"{r:.2f} (CV {cv:.2f})", f"{band[0]}–{band[1]}")


def t7(d, a, week):
    t = d.arrival_timestamp
    days = int(np.ceil(t.max() / 86400))
    gate("T7a", "timestamp đơn điệu, đúng đơn vị", bool(t.is_monotonic_increasing) and t.min() >= 0 and t.max() < days * 86400, f"{t.min():.1f}–{t.max():.1f} s", "không giảm, trong số ngày")
    if week is not None and a.week_day is not None:
        x = d[d.iw].groupby((t[d.iw] // 3600).astype(int)).size().reindex(range(24), fill_value=0)
        wt = week.arrival_timestamp - a.week_day * 86400
        sel = week.iw & (wt >= 0) & (wt < 86400)
        y = week[sel].groupby((wt[sel] // 3600).astype(int)).size().reindex(range(24), fill_value=0)
        v = float(np.corrcoef(x, y)[0, 1])
        gate("T7c", "trace ngày khớp ngày thứ Ba của trace tuần", v >= 0.95, f"tương quan {v:.3f}", "≥ 0,95")
    if a.forecast:
        files, bad = check_forecasts(a.forecast)
        gate("T7d", "dự báo canh phút, đúng giờ kế tiếp", bool(files) and not bad, f"{len(files)} file, sai {len(bad)}", "0 sai")
    gate("T7e", "skip_hours chung cho mọi chiến lược", skip_hours_shared(), "kiểm mã nguồn", "đúng")


def t8_t9(a):
    if not a.reactive:
        gate("T8", "G10", None, "chưa cung cấp bài Reactive", "—")
        gate("T9", "θ cùng cỡ §2.1", None, "chưa cung cấp bài Reactive", "—")
        return
    p = subprocess.run([sys.executable, f"{ROOT}/check_g10.py", a.reactive], capture_output=True, text=True, encoding="utf-8", errors="ignore")
    gate("T8", "Bloom, Llama-2 ≥ 4 instance mọi vùng", p.returncode == 0, p.stdout.strip().splitlines()[-1][-30:] if p.stdout.strip() else p.stderr[-80:], "≥ 4")
    p = subprocess.run([sys.executable, f"{ROOT}/analyze_capacity.py", a.reactive, a.trace], capture_output=True, text=True, encoding="utf-8", errors="ignore")
    for m in (A, B):
        hit = re.search(rf"^\s*{re.escape(m)}.*$", p.stdout, re.M)
        nums = re.findall(r"[-+]?\d+\.?\d*", hit.group(0).replace(m, "")) if hit else []
        lo, hi = Q[a.gpu][m]
        v = float(nums[5]) if len(nums) > 5 else float("nan")       # cột "tps/inst khi bộ nhớ 60-80%"
        gate("T9", f"θ {m} (analyze_capacity)", lo / 10 <= v <= hi * 10, f"{v:.0f} TPS", f"{lo / 10:g}–{hi * 10:g}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--role", choices=["t7", "t11"], required=True)
    ap.add_argument("--week")
    ap.add_argument("--day0", type=int, default=4)
    ap.add_argument("--week_day", type=int)
    ap.add_argument("--forecast")
    ap.add_argument("--reactive")
    ap.add_argument("--gpu", choices=["a100", "h100"], default="a100")
    ap.add_argument("--variant", choices=["niw", "burst"])
    ap.add_argument("--s4", action="store_true", help="Trace §4: IW:NIW = 7:1")
    a = ap.parse_args()
    d = load(a.trace)
    w = None if a.week is None else (d if a.week == a.trace else load(a.week))

    share = 100 * d.iw.mean()
    band = (82, 93) if a.s4 else (65, 80)
    gate("T1", "IW / tổng request", None if a.variant == "niw" else inside(share, band), f"{share:.1f}%", f"{band[0]}–{band[1]}%")
    if w is not None:
        t2_t3(w, a)
    else:
        gate("T2", "ps", None, "chưa cung cấp trace tuần", "—")
        gate("T3", "cuối tuần", None, "chưa cung cấp trace tuần", "—")
    t4(d, a)
    t5(d)
    t6(d, a)
    t7(d, a, w)
    t8_t9(a)

    print(f"Trace: {a.trace} | vai trò {a.role} | {len(d):,} request")
    print(pd.DataFrame(rows, columns=["mã", "chỉ số", "kết quả", "đo được", "ngưỡng"]).to_string(index=False))
    fails = sum(r[2] == "FAIL" for r in rows)
    print(f"KẾT QUẢ: {sum(r[2] == 'PASS' for r in rows)} PASS, {fails} FAIL, {sum(r[2] == 'N/A' for r in rows)} N/A")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
