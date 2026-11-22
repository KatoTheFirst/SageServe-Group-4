"""Bảng kết quả tự động cho một nhóm bài mô phỏng (T45 Tuần 9, dùng lại cho T48), theo định nghĩa RESULTS v2.1 (analyze_s4.py).
Mỗi bài ra một dòng gồm:
  - instance-hours, bỏ giờ 0 (v2.1); thêm cột theo định nghĩa T41: chỉ tính [3600, 86400);
  - GPU-giờ = instance-hours × 8 (mỗi instance 8 GPU A100 theo perf_model_4models);
  - TTFT/E2E P95 và vi phạm SLA của IW (TTFT trừ 1 s trễ router, so SLA của trace), vi phạm NIW (> 24 h);
  - sự kiện scale: số lần prod tăng/giảm theo arbiters/<vùng>/*.csv, số dòng SCALEUP_WASTE (lấy lại spot / khởi động);
  - LT-UA: số dòng LTUA_RATIO theo hành động (code D38 trở đi);
  - T44: prod nhỏ nhất/lớn nhất mỗi endpoint sau giờ 0, số endpoint có prod < 2 (sàn deployment).
Ghi thêm bảng bộ nhớ theo giờ (trung bình, Q3) và hình bộ nhớ theo thời gian.
Dùng (qua chay_phan_tich.py, luật 9): python experiments/bang_ket_qua.py <repo> <thư mục ra> <bài1> [<bài2> ...]"""
import glob
import os
import sys

import pandas as pd

REPO, OUT, RUNS = sys.argv[1], sys.argv[2], sys.argv[3:]
sys.path.insert(0, REPO)
from analyze_s4 import ROUTING_DELAY, analyze, sla_of  # noqa: E402

GPU_PER_INSTANCE = 8
os.makedirs(OUT, exist_ok=True)


def scale_events(run, skip=3600):
    rows = []
    for d in sorted(glob.glob(f"{run}/arbiters/*")):
        region = os.path.basename(d)
        a = pd.concat(pd.read_csv(f) for f in glob.glob(f"{d}/*.csv"))
        for m, g in a.sort_values("timestamp", kind="stable").groupby("model"):
            prod, ts = g["prod"].astype(int).to_numpy(), g.timestamp.to_numpy()
            step, keep = prod[1:] - prod[:-1], ts[1:] >= skip
            after = prod[ts >= skip]
            rows.append({"vùng": region, "endpoint": m, "tăng": int(((step > 0) & keep).sum()), "giảm": int(((step < 0) & keep).sum()),
                         "prod_min": int(after.min()) if len(after) else None, "prod_max": int(after.max()) if len(after) else None})
    return pd.DataFrame(rows)


def log_counts(run):
    waste, ltua = {}, {}
    for line in open(f"{run}/run.log", encoding="utf-8", errors="ignore"):
        if "SCALEUP_WASTE," in line:
            kind = line.strip().split("SCALEUP_WASTE,")[1].split(",")[2]
            waste[kind] = waste.get(kind, 0) + 1
        elif "LTUA_RATIO," in line:
            act = line.strip().split(",")[-1]
            ltua[act] = ltua.get(act, 0) + 1
    return waste, ltua


tong, mem_rows = [], []
for run in RUNS:
    name = "/".join(run.replace("\\", "/").rstrip("/").split("/")[-3:])
    res, per15, util = analyze(run, skip_hours=1)
    ih = res.instance_hours.sum()
    ih_t41 = per15[per15.bin < 86400 // 900].instance.sum() / 4
    g = pd.concat(pd.read_csv(f) for f in glob.glob(f"{run}/global_router/*.csv"))
    iw, niw = g[g.workload_type == "prod"], g[g.workload_type == "dev"]
    iw_miss = 100 * ((iw.ttft - ROUTING_DELAY) > sla_of(iw)).mean()      # như analyze_s4: TTFT trừ trễ router, so SLA của trace
    ev = scale_events(run)
    waste, ltua = log_counts(run)
    tong.append({"bài": name, "IW xong": len(iw), "NIW xong": len(niw), "instance-hours (v2.1, bỏ giờ 0)": ih,
                 "instance-hours [3600, 86400) (T41)": ih_t41, "GPU-giờ (×8)": ih * GPU_PER_INSTANCE,
                 "IH Llama-2": res.instance_hours.get("llama2-70b"), "IW TTFT P95 (s)": iw.ttft.quantile(.95),
                 "IW E2E P95 (s)": iw.response_time.quantile(.95), "IW vi phạm SLA (%)": iw_miss,
                 "NIW vi phạm (> 24 h, %)": 100 * (niw.response_time > 86400).mean(),
                 "scale tăng": int(ev["tăng"].sum()) if len(ev) else 0, "scale giảm": int(ev["giảm"].sum()) if len(ev) else 0,
                 "lấy lại spot": waste.get("reclaim_spot", 0), "khởi động mới": waste.get("spin_up", 0),
                 **{f"LT-UA {k}": v for k, v in sorted(ltua.items())},
                 "T44: endpoint prod < 2": int((ev.prod_min < 2).sum()) if len(ev) else 0,
                 "T44: prod min": ev.prod_min.min() if len(ev) else None, "T44: prod max": ev.prod_max.max() if len(ev) else None})
    ev.assign(bài=name).to_csv(f"{OUT}/su_kien_scale.csv", mode="a", header=not os.path.exists(f"{OUT}/su_kien_scale.csv"), index=False)
    util["giờ"] = util.time // 3600
    h = util.groupby(["model", "giờ"]).util.agg(["mean", lambda s: s.quantile(.75)]).reset_index()
    h.columns = ["mô hình", "giờ", "bộ nhớ TB (%)", "bộ nhớ Q3 (%)"]
    mem_rows.append(h.assign(bài=name))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(9, 3))
        for m, s in util.groupby("model"):
            ax.plot(s.time / 3600, s.util, lw=0.6, label=m)
        ax.set_xlabel("giờ mô phỏng"), ax.set_ylabel("bộ nhớ dùng (%)"), ax.set_title(name, loc="left", fontsize=9), ax.legend(fontsize=7)
        fig.tight_layout(), fig.savefig(f"{OUT}/bo_nho_{name.replace('/', '_')}.png", dpi=120), plt.close(fig)
    except Exception as e:  # hình là phụ, bảng mới là chính
        print("không vẽ được hình:", e)

t = pd.DataFrame(tong)
t.to_csv(f"{OUT}/bang_tong.csv", index=False)
pd.concat(mem_rows).to_csv(f"{OUT}/bo_nho_theo_gio.csv", index=False)
print(t.round(3).to_string(index=False))
