"""
So sánh kết quả thí nghiệm §4 (1 vùng westus, 4 mô hình, 1 ngày) với bài báo: Fig. 8a, Fig. 8b, Table 1.

Dùng: python analyze_s4.py <thư mục kết quả 1> [<thư mục kết quả 2> ...] --out <thư mục ảnh/bảng>
Instance-hours tính như plotting_scripts/Figure4.py: số instance lớn nhất trong mỗi 15 phút, cộng lại / 4.
"""
import argparse
import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROUTING_DELAY = 1   # configs/global_router/overheads/zero.yaml
MODELS = ["bloom-176b", "llama2-70b", "llama3.1-8b", "llama3.2-3b"]
# Bài báo: Fig. 8a (instance-hours) và Table 1 (P95, giây) – West US, Tue Nov 2024
PAPER = pd.DataFrame({
    "model": MODELS,
    "paper_siloed_ih": [199.2, 137.2, 101.0, 101.0], "paper_unified_ih": [148.0, 96.8, 53.0, 53.0],
    "paper_unified_ttft_p95": [12.9, 34.5, 1.0, 1.0], "paper_unified_e2e_p95": [53.3, 99.1, 10.5, 18.9],
}).set_index("model")


def sla_of(g):
    """SLA TTFT (giây) của từng request. Kết quả cũ chưa có cột sla: suy từ utility của trace ghép (5 -> 1 s, 3 -> 60 s)."""
    if "sla" in g:
        return g["sla"]
    return g.utility.map({5.0: 1, 3.0: 60}).fillna(86400)


def concat(pattern):
    files = sorted(glob.glob(pattern))
    return pd.concat((pd.read_csv(f) for f in files), ignore_index=True) if files else pd.DataFrame()


def analyze(d, skip_hours=0):
    mem = concat(f"{d}/memory/*.csv")
    # Siloed: endpoint "<model>-p" (IW) và "<model>-d" (NIW) gộp về cùng mô hình
    mem["model"] = mem["instance"].str.split("_").str[1].str.replace(r"-[pd]$", "", regex=True)
    # bỏ giai đoạn khởi động (mọi endpoint bắt đầu với số instance của start state)
    count = mem[mem.time >= 3600 * skip_hours].groupby(["model", "time"]).instance.nunique().reset_index()
    count["bin"] = count.time // 900
    per15 = count.groupby(["model", "bin"]).instance.max().reset_index()
    ih = per15.groupby("model").instance.sum() / 4
    endpoint = mem.groupby(["model", "time"])[["memory", "max_memory"]].sum()
    util = (endpoint.memory / endpoint.max_memory * 100).rename("util").reset_index()

    g = concat(f"{d}/global_router/*.csv")
    g["model_type"] = g["model_type"].str.replace(r"-[pd]$", "", regex=True)
    # SLA (§2.2): IW-F TTFT < 1 s, IW-N TTFT < 60 s, NIW xong trong 24 h.
    # TTFT ghi ra đã gồm độ trễ cố định của global router -> trừ ra trước khi so ngưỡng.
    ttft = g.ttft - ROUTING_DELAY
    g["sla_miss"] = ((g.workload_type == "prod") & (ttft > sla_of(g))) | \
                    ((g.workload_type == "dev") & (g.response_time > 86400))
    iw = g[g.workload_type == "prod"].groupby("model_type")
    niw = g[g.workload_type == "dev"].groupby("model_type")
    u = util.groupby("model").util
    res = pd.DataFrame({
        "instance_hours": ih,
        "iw_done": iw.size(), "iw_ttft_p95": iw.ttft.quantile(.95), "iw_e2e_p95": iw.response_time.quantile(.95),
        "iw_sla_miss_%": 100 * iw.sla_miss.mean(),
        "niw_done": niw.size(), "niw_e2e_p95": niw.response_time.quantile(.95),
        "niw_sla_miss_%": 100 * niw.sla_miss.mean(),
        "mem_util_q1_%": u.quantile(.25), "mem_util_median_%": u.median(), "mem_util_q3_%": u.quantile(.75),
    })
    res = res.reindex(MODELS + [m for m in res.index if m not in MODELS])     # vd. mô hình thứ 5 (§7.2.5)
    return res, per15, util


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--out", default="results/s4_compare")
    ap.add_argument("--skip_hours", type=float, default=0, help="Bỏ N giờ đầu khi tính instance-hours")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    fig, axes = plt.subplots(1, 4, figsize=(16, 3.6), sharey=True)
    tables = []
    for run in a.runs:
        name = os.path.basename(run.rstrip("/\\"))
        res, per15, _ = analyze(run, a.skip_hours)
        tables.append(res.add_prefix(f"{name}:"))
        for ax, m in zip(axes, MODELS):
            x = per15[per15.model == m]
            ax.step(x.bin / 4, x.instance, where="post", label=f"{name} ({res.instance_hours.get(m, 0):.1f} h)")
    for ax, m in zip(axes, MODELS):
        ax.set_title(f"{m}  (bài báo Unified: {PAPER.paper_unified_ih[m]} h)", loc="left", fontsize=10)
        ax.set_xlabel("Giờ trong ngày")
        ax.legend(fontsize=8, frameon=False)
        ax.grid(alpha=.3)
    axes[0].set_ylabel("Số instance")
    fig.tight_layout()
    fig.savefig(f"{a.out}/instances_per_15min.png", dpi=150)
    table = pd.concat([PAPER] + tables, axis=1).round(2)
    table.to_csv(f"{a.out}/compare_with_paper.csv")
    total = table.filter(like="instance_hours").sum().round(1)
    print(table.T.to_string())
    print("\nTổng instance-hours:", total.to_dict(), "| bài báo Unified:", PAPER.paper_unified_ih.sum(),
          "Siloed:", PAPER.paper_siloed_ih.sum())


if __name__ == "__main__":
    main()
