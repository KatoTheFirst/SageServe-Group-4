"""Phân tích chỉ đọc (8/11/2026): vì sao oracle_smooth trên Nov hỏng TTFT (Q3 +43..+110%).
1. Kiểm cách tạo dự báo: oracle == TPM IW thực từng phút (vùng = ký tự đầu của 'regions'); oracle_smooth == trung bình trượt 60 phút căn giữa của oracle.
2. Tính giật: theo mô hình x vùng x giờ, tỉ số đỉnh 1 phút (oracle) / đỉnh của chuỗi làm trơn (oracle_smooth) = cái ILP thấy (§6.3 lấy đỉnh dự báo của giờ).
3. Giờ thiếu máy (Nov, Llama-2, cộng 3 vùng): số instance của bài oracle_smooth < bài oracle cùng chiến lược (trung bình giờ của max khối 15 phút,
   như analyze_s4); đối chiếu với số request IW Llama-2 trễ hạn TTFT theo giờ đến (bài smooth trừ bài oracle).
Dùng: python smooth_nov.py"""
import glob
import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
import os
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, REPO)
from analyze_s4 import ROUTING_DELAY, sla_of   # noqa: E402

R = sys.argv[1]                                  # T48: gốc dữ liệu là tham số (bản gốc: D:/SageServe_results/v21)
TRACE = {"lt": "composed_day_3regions_v2", "nov2024": "fork_day_3regions_v2"}
L2 = "llama2-70b"
pd.set_option("display.width", 250)

# ---- 1 + 2 ----
ratios = []
for tr, name in TRACE.items():
    t = pd.read_csv(f"{REPO}/traces/{name}.csv", usecols=["model_type", "workload_type", "arrival_timestamp", "prompt_size", "regions"],
                    dtype={"regions": str})
    t = t[t.workload_type == "prod"]
    t["region"] = t.regions.str.zfill(3).str[0].astype(int)
    dmax_o = dmax_s = 0.0
    glob_o, glob_s = {}, {}
    for f in sorted(p.replace("\\", "/") for p in glob.glob(f"{REPO}/traces/forecasts/{name}_oracle/final_*_prod_1minute_region*_arima.csv")):
        model = f.split("final_")[1].split("_prod")[0]
        r = int(f.split("_region")[-1][0])
        o = pd.read_csv(f).Predicted.values
        s = pd.read_csv(f.replace("_oracle/", "_oracle_smooth/")).Predicted.values
        x = t[(t.model_type == model) & (t.region == r)]
        tpm = x.groupby((x.arrival_timestamp // 60).astype(int)).prompt_size.sum().reindex(range(len(o)), fill_value=0).values.astype(float)
        dmax_o = max(dmax_o, np.abs(o - tpm).max())
        dmax_s = max(dmax_s, np.abs(s - pd.Series(tpm).rolling(60, center=True, min_periods=1).mean().round(2).values).max())
        h = np.arange(len(o)) // 60
        po, ps = pd.Series(o).groupby(h).max(), pd.Series(s).groupby(h).max()
        for hr in po.index:
            ratios.append({"trace": tr, "model": model, "region": r, "hour": hr, "peak_1min": po[hr], "peak_smooth": ps[hr]})
        glob_o[(model, r)], glob_s[(model, r)] = o, s
    for model in {m for m, _ in glob_o}:
        so = sum(v for (m, _), v in glob_o.items() if m == model)
        ss = sum(v for (m, _), v in glob_s.items() if m == model)
        h = np.arange(len(so)) // 60
        po, ps = pd.Series(so).groupby(h).max(), pd.Series(ss).groupby(h).max()
        for hr in po.index:
            ratios.append({"trace": tr, "model": model, "region": "tổng", "hour": hr, "peak_1min": po[hr], "peak_smooth": ps[hr]})
    print(f"[kiểm dự báo] {tr}: max |oracle - TPM thực| = {dmax_o:.4f}; max |oracle_smooth - trượt 60 phút căn giữa| = {dmax_s:.4f}")
rt = pd.DataFrame(ratios)
rt = rt[(rt.hour >= 1) & (rt.peak_smooth > 0)]
rt["ratio"] = rt.peak_1min / rt.peak_smooth
print("\n[tỉ số đỉnh 1 phút / đỉnh làm trơn trong giờ, bỏ giờ đầu]")
for (tr, sc), g in rt.groupby(["trace", rt.region.astype(str).eq("tổng")]):
    for lab, gg in (("4 mô hình", g), ("llama2-70b", g[g.model == L2])):
        print(f"  {tr:8s} {'tổng 3 vùng' if sc else 'từng vùng  '} {lab:11s}: trung vị {gg.ratio.median():.3f}, P90 {gg.ratio.quantile(.9):.3f}, max {gg.ratio.max():.3f} (n={len(gg)})")


# ---- 3 ----
def inst_hour(d):
    x = pd.concat((pd.read_csv(f, usecols=["time", "instance"]) for f in glob.glob(f"{d}/memory/*.csv")), ignore_index=True)
    x = x[x.instance.str.split("_").str[1].str.replace(r"-[pd]$", "", regex=True) == L2]
    c = x.groupby("time").instance.nunique().reset_index()
    c["bin"] = (c.time // 900).astype(int)
    b = c.groupby("bin").instance.max()
    return b.groupby(b.index // 4).mean()


def miss_hour(d):
    g = pd.concat((pd.read_csv(f) for f in glob.glob(f"{d}/global_router/*.csv")), ignore_index=True)
    g["model_type"] = g.model_type.str.replace(r"-[pd]$", "", regex=True)
    g = g[(g.workload_type == "prod") & (g.model_type == L2)]
    hr = ((g.completion_time - g.response_time) // 3600).astype(int)
    miss = (g.ttft - ROUTING_DELAY) > sla_of(g)
    return miss.groupby(hr).sum(), g.ttft.groupby(hr).quantile(.95)


rn = rt[(rt.trace == "nov2024") & (rt.model == L2) & (rt.region.astype(str) == "tổng")].set_index("hour").ratio
print("\n[Nov, Llama-2, cộng 3 vùng: giờ thiếu máy (smooth < oracle >= 0,5 instance TB) và request IW trễ hạn TTFT]")
for s in ("lt_i", "lt_u", "lt_ua"):
    io, is_ = inst_hour(f"{R}/oracle/nov2024/{s}"), inst_hour(f"{R}/oracle_smooth/nov2024/{s}")
    (mo, po), (ms, ps) = miss_hour(f"{R}/oracle/nov2024/{s}"), miss_hour(f"{R}/oracle_smooth/nov2024/{s}")
    df = pd.DataFrame({"inst_oracle": io, "inst_smooth": is_, "miss_oracle": mo, "miss_smooth": ms, "p95_smooth": ps,
                       "ratio_peak": rn}).fillna(0)
    df = df[df.index >= 1]
    df["thieu"] = df.inst_oracle - df.inst_smooth >= 0.5
    df["miss_them"] = (df.miss_smooth - df.miss_oracle).clip(lower=0)
    tot = df.miss_them.sum()
    print(f"  {s}: giờ thiếu máy {int(df.thieu.sum())}/{len(df)}; IH thiếu so oracle {(df.inst_oracle - df.inst_smooth).clip(lower=0).sum():.2f}; "
          f"request trễ hạn thêm {int(tot)}, trong giờ thiếu máy {int(df.miss_them[df.thieu].sum())} ({100 * df.miss_them[df.thieu].sum() / tot:.1f}%); "
          f"tương quan Spearman(tỉ số đỉnh, trễ hạn thêm) = {df.ratio_peak.corr(df.miss_them, method='spearman'):.3f}")
    top = df.sort_values("miss_them", ascending=False).head(5)
    print(top[["inst_oracle", "inst_smooth", "miss_oracle", "miss_smooth", "p95_smooth", "ratio_peak"]].round(2).to_string())
