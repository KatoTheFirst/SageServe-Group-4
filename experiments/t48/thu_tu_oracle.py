"""Phân tích chỉ đọc (8/11/2026): vì sao với dự báo oracle thứ tự tiết kiệm là LT-UA ≥ LT-U ≥ LT-I (ngược bài báo).
Cho mỗi trace (lt, nov2024) x chiến lược (lt_i, lt_u, lt_ua), theo vùng x mô hình x khối 15 phút (cùng định nghĩa instance-giờ của analyze_s4):
  - inst  = số instance thực (max số instance khác nhau trong memory/ trong khối 15 phút, như analyze_s4)
  - target = mục tiêu ILP của giờ = "Current allocation" + "ILP forecast" trong run.log
  - need  = max theo phút trong khối của ceil(TPM IW thực của vùng / (60 θ))   (θ: data/theta_tps_v2.csv; ILP dùng cap = n·60θ)
  - floor = 2 (scale_down_to_spot không bớt dưới 1 deployment 2 instance)
Báo: IH (đối chiếu orc_full), IH vượt / dưới mục tiêu, IH thừa so với max(need, floor), IH thiếu, số lần giảm instance giữa giờ.
Bỏ giờ đầu (như analyze_oracle: analyze(d, 1)).
Dùng: python thu_tu_oracle.py [<thư mục oracle>=D:/SageServe_results/v21/oracle] [--csv <file chi tiết>]"""
import ast
import glob
import math
import re
import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

import os
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
O = next((a for a in sys.argv[1:] if not a.startswith("--") and not a.endswith(".csv")), "D:/SageServe_results/v21/oracle")
TOM = sys.argv[sys.argv.index("--tom") + 1]          # T48: đích bảng tóm tắt là tham số (bản gốc ghi cứng v21/phan_tich)
CSV = sys.argv[sys.argv.index("--csv") + 1] if "--csv" in sys.argv else None
TRACE = {"lt": "composed_day_3regions_v2", "nov2024": "fork_day_3regions_v2"}
REG = ["westus", "centralus", "eastus"]                       # region_id 0..2 (configs/controller/us3-4models.yaml)
MOD = ["bloom-176b", "llama2-70b", "llama3.1-8b", "llama3.2-3b"]   # chỉ số ILP = thứ tự sorted (global_arbiter.py:137)
FLOOR = 2
theta = pd.read_csv(f"{REPO}/data/theta_tps_v2.csv").set_index("model").theta_tps


def targets(d):
    cur, out = {}, []
    for line in open(f"{d}/run.log", encoding="utf-8", errors="ignore"):
        m = re.search(r"(Current allocation|ILP forecast) at time ([0-9.]+): (\[.*\])", line)
        if not m:
            continue
        t, v = float(m.group(2)), ast.literal_eval(m.group(3))
        if m.group(1) == "Current allocation":
            cur[t] = v
        else:
            c = cur[t]
            for r in range(3):
                for k in range(4):
                    out.append({"hour": int(t // 3600), "region": REG[r], "model": MOD[k], "target": c[r][k][0] + v[r][k][0]})
    return pd.DataFrame(out)


def need(trace):
    t = pd.read_csv(f"{REPO}/traces/{trace}.csv", usecols=["model_type", "workload_type", "arrival_timestamp", "prompt_size", "regions"],
                    dtype={"regions": str})
    t = t[t.workload_type == "prod"]
    t["region"] = t.regions.str.zfill(3).str[0].astype(int).map(dict(enumerate(REG)))   # như generate_causal_arima_forecasts.py
    t["minute"] = (t.arrival_timestamp // 60).astype(int)
    tpm = t.groupby(["region", "model_type", "minute"]).prompt_size.sum().rename("tpm").reset_index().rename(columns={"model_type": "model"})
    full = pd.MultiIndex.from_product([REG, MOD, range(24 * 60)], names=["region", "model", "minute"])
    tpm = tpm.set_index(["region", "model", "minute"]).reindex(full, fill_value=0).reset_index()
    tpm["need"] = np.ceil(tpm.tpm / (60 * tpm.model.map(theta))).astype(int)
    tpm["bin"] = tpm.minute // 15
    return tpm.groupby(["region", "model", "bin"]).need.max().reset_index()


def counts(d):
    x = pd.concat((pd.read_csv(f, usecols=["time", "instance"]) for f in glob.glob(f"{d}/memory/*.csv")), ignore_index=True)
    s = x.instance.str.split("_")
    x["region"], x["model"] = s.str[0], s.str[1].str.replace(r"-[pd]$", "", regex=True)
    return x.groupby(["region", "model", "time"]).instance.nunique().rename("n").reset_index().sort_values("time")


rows, detail = [], []
for tr, trace in TRACE.items():
    nd = need(trace)
    for s in ("lt_i", "lt_u", "lt_ua"):
        d = f"{O}/{tr}/{s}"
        c = counts(d)
        c = c[c.time >= 3600]
        c["bin"] = (c.time // 900).astype(int)
        b = c.groupby(["region", "model", "bin"]).n.max().rename("inst").reset_index()
        g4 = c.groupby(["model", "time"]).n.sum().reset_index()          # như analyze_s4: max khối 15 phút của tổng 3 vùng
        g4["bin"] = (g4.time // 900).astype(int)
        ih_s4 = g4.groupby(["model", "bin"]).n.max().groupby("model").sum() / 4
        b["hour"] = b.bin // 4
        b = b.merge(targets(d), on=["hour", "region", "model"], how="left").merge(nd, on=["region", "model", "bin"], how="left")
        b["need_f"] = b.need.clip(lower=FLOOR)
        # giảm instance giữa giờ: số instance (theo thời điểm) giảm khi đã quá 10 phút đầu giờ
        dec = 0
        for _, g in c.groupby(["region", "model"]):
            dn = g.n.diff() < 0
            dec += int((dn & (g.time % 3600 >= 600)).sum())
        q = lambda e: float(e.sum() / 4)
        for mdl, bb in (("tổng", b), ("llama2-70b", b[b.model == "llama2-70b"])):
            rows.append({"trace": tr, "chiến lược": s, "mô hình": mdl,
                         "IH như S4": float(ih_s4.sum() if mdl == "tổng" else ih_s4[mdl]), "IH": q(bb.inst),
                         "IH mục tiêu": q(bb.target), "IH vượt MT": q((bb.inst - bb.target).clip(lower=0)),
                         "IH dưới MT": q((bb.target - bb.inst).clip(lower=0)),
                         "vượt MT ngoài sàn, ngoài khối đầu giờ": q((bb.inst - bb.target.clip(lower=FLOOR)).clip(lower=0)[bb.bin % 4 != 0]),
                         "vượt MT do sàn 2": q(np.minimum((bb.inst - bb.target).clip(lower=0), (FLOOR - bb.target).clip(lower=0))),
                         "IH nhu cầu θ (sàn 2)": q(bb.need_f), "IH thừa": q((bb.inst - bb.need_f).clip(lower=0)),
                         "IH thiếu": q((bb.need - bb.inst).clip(lower=0)),
                         "khối thiếu": int((bb.inst < bb.need).sum()),
                         "MT thừa so nhu cầu": q((bb.target - bb.need_f).clip(lower=0)),
                         "giảm giữa giờ": dec if mdl == "tổng" else None})
        detail.append(b.assign(trace=tr, strategy=s))
res = pd.DataFrame(rows).round(2)
res.to_csv(TOM, index=False)
pd.set_option("display.width", 250)
print(res.to_string(index=False))
if CSV:
    pd.concat(detail).to_csv(CSV, index=False)
    print("[+] chi tiết ->", CSV)
