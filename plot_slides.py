"""
Biểu đồ minh họa cho slide (PNG, nền sáng):
  nv1 – §4 Siloed vs Unified (instance-hours, số instance theo thời gian, độ trễ P95) so với bài báo (Fig. 8, Table 1)
  nv2 – Load Predictor trong simulator: đỉnh TPM dự báo vs thực tế theo giờ, sai số online vs offline

Dùng: python plot_slides.py nv1 results/s4/unified results/s4/siloed --out "output/Vũ Hoàng Ân_Tuần 5"
      python plot_slides.py nv2 results/nv2/online results/nv2/offline --out "output/Vũ Hoàng Ân_Tuần 6"
"""
import argparse
import os

import matplotlib
import matplotlib.ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from analyze_s4 import MODELS, PAPER, analyze

# Bảng màu categorical mặc định (đã kiểm validate_palette.js: CVD, độ tương phản) – thứ tự cố định
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
REGION = {0: "West", 1: "Central", 2: "East"}
plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
                     "axes.spines.top": False, "axes.spines.right": False, "font.size": 11,
                     "legend.frameon": False})


def save(fig, out, name, rect=(0, 0, 1, 1)):
    fig.tight_layout(rect=rect)
    path = f"{out}_{name}.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print("[+]", path)


def nv1(unified, siloed, out):
    ru, pu, _ = analyze(unified)
    rs, ps, _ = analyze(siloed)
    names = [m.split("-")[0].replace("llama", "Llama ").replace("bloom", "Bloom") + "-" + m.split("-")[1] for m in MODELS]
    x = range(len(MODELS))

    # 1. instance-hours theo mô hình, kèm vạch số liệu bài báo
    fig, ax = plt.subplots(figsize=(10, 5.2))
    w = 0.38
    for off, res, col, lab, pap in [(-w / 2, rs, ORANGE, "Siloed", "paper_siloed_ih"), (w / 2, ru, BLUE, "Unified", "paper_unified_ih")]:
        vals = res.instance_hours.reindex(MODELS).values
        ax.bar([i + off for i in x], vals, w - 0.03, color=col, label=f"{lab} (mô phỏng)")
        for i, v in zip(x, vals):      # nhãn trong đầu cột để không đè vạch số liệu bài báo
            ax.text(i + off, v - 4, f"{v:.0f}", ha="center", va="top", fontsize=10, color="white", fontweight="bold")
        ax.scatter([i + off for i in x], PAPER[pap].reindex(MODELS).values, marker="_", s=420, linewidths=2.5,
                   color=INK, zorder=3, label="Bài báo (Fig. 8a)" if lab == "Unified" else None)
    tu, ts = ru.instance_hours.sum(), rs.instance_hours.sum()
    ax.set_xticks(list(x), names)
    ax.set_ylabel("Instance-hours / ngày")
    ax.set_title(f"Siloed vs Unified – West US, 1 ngày: Unified dùng ít hơn {100 * (1 - tu / ts):.1f}% "
                 f"({tu:.0f} so với {ts:.0f}; bài báo {100 * (1 - PAPER.paper_unified_ih.sum() / PAPER.paper_siloed_ih.sum()):.1f}%)",
                 loc="left", fontsize=12)
    ax.legend(loc="upper right")
    save(fig, out, "1_instance_hours")

    # 2. số instance theo thời gian (max mỗi 15 phút), từng mô hình
    fig, axes = plt.subplots(1, 4, figsize=(15, 4), sharey=True)
    for ax, m, nm in zip(axes, MODELS, names):
        for per15, col, lab, ls in [(ps, ORANGE, "Siloed", "-"), (pu, BLUE, "Unified", "-")]:
            d = per15[(per15.model == m) & (per15.bin >= 1)]      # bỏ 15 phút đầu: trạng thái khởi tạo 20 instance
            ax.step(d.bin / 4, d.instance, where="post", color=col, lw=2, ls=ls, label=lab)
        ax.set_title(nm, loc="left", fontsize=11)
        ax.set_xlabel("Giờ trong ngày (UTC)")
        ax.set_xticks(range(0, 25, 6))
    axes[0].set_ylabel("Số instance (đỉnh mỗi 15 phút)")
    axes[0].legend(loc="upper left")
    fig.suptitle("Số instance theo thời gian – Unified bám tải, Siloed giữ nhóm NIW riêng "
                 "(bỏ 15 phút đầu: trạng thái khởi tạo 20 instance/mô hình)", x=0.01, ha="left", fontsize=12)
    save(fig, out, "2_instances_over_time")

    # 3. độ trễ P95 – Unified không xấu hơn Siloed
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    for ax, col_name, title in [(axes[0], "iw_ttft_p95", "TTFT P95 của IW (giây)"), (axes[1], "iw_e2e_p95", "E2E P95 của IW (giây)")]:
        for off, res, col, lab in [(-w / 2, rs, ORANGE, "Siloed"), (w / 2, ru, BLUE, "Unified")]:
            vals = res[col_name].reindex(MODELS).values
            ax.bar([i + off for i in x], vals, w - 0.03, color=col, label=lab)
            for i, v in zip(x, vals):
                ax.text(i + off, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9, color=INK2)
        ax.set_xticks(list(x), names, fontsize=9)
        ax.set_title(title, loc="left", fontsize=11)
    axes[0].legend(loc="upper right")
    fig.suptitle("Độ trễ đuôi: Unified tiết kiệm instance mà độ trễ tương đương Siloed (Table 1)", x=0.01, ha="left", fontsize=12)
    save(fig, out, "3_latency_p95")
    pd.concat({"siloed": rs, "unified": ru}, axis=1).round(2).to_csv(f"{out}_so_lieu.csv")
    print("[+]", f"{out}_so_lieu.csv")


def nv2(online, offline, out):
    on = pd.read_csv(f"{online}/forecast_log.csv")
    off = pd.read_csv(f"{offline}/forecast_log.csv")
    m = on.merge(off, on=["hour", "region", "model"], suffixes=("", "_off"))
    diff = 100 * ((m.pred_peak_tpm - m.pred_peak_tpm_off).abs() / m.pred_peak_tpm_off.clip(lower=1)).max()
    pairs = [("bloom-176b", 2), ("bloom-176b", 0), ("llama2-70b", 1), ("llama2-70b", 0)]
    big = on[on.model.isin(["bloom-176b", "llama2-70b"])]

    # 4. đỉnh TPM theo giờ: thực tế vs dự báo của Load Predictor
    fig, axes = plt.subplots(2, 2, figsize=(14, 7.5), sharex=True)
    for ax, (mo, r) in zip(axes.flat, pairs):
        d = big[(big.model == mo) & (big.region == r) & (big.hour > 0)].sort_values("hour")   # giờ 0: chưa có lịch sử
        ax.plot(d.hour, d.actual_peak_tpm / 1e3, color=BLUE, lw=2, marker="o", ms=4, label="Thực tế (quan sát trong simulator)")
        ax.plot(d.hour, d.pred_peak_tpm / 1e3, color=ORANGE, lw=2, marker="s", ms=4, label="Dự báo ARIMA-60 (Load Predictor)")
        ax.set_title(f"{mo} – {REGION[r]}", loc="left", fontsize=11)
        ax.set_ylabel("Đỉnh TPM trong giờ (nghìn)")
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    for ax in axes[1]:
        ax.set_xlabel("Giờ (UTC) – mỗi giờ huấn luyện lại trên 60 phút vừa quan sát")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper left", bbox_to_anchor=(0.01, 0.95), ncol=2, fontsize=10)
    fig.suptitle(f"Load Predictor trong vòng lặp mô phỏng: đỉnh tải dự báo so với thực tế "
                 f"(online trùng offline, lệch tối đa {diff:.2g}%)", x=0.01, ha="left", fontsize=12)
    save(fig, out, "4_forecast_vs_actual", rect=(0, 0, 1, 0.91))

    # 5. sai số: MAPE đỉnh giờ theo mô hình–vùng + tán xạ dự báo vs thực tế (bỏ giờ 0: chưa có lịch sử)
    d = big[(big.hour > 0) & (big.actual_peak_tpm > 0)].copy()
    d["ape"] = 100 * (d.pred_peak_tpm - d.actual_peak_tpm).abs() / d.actual_peak_tpm
    mape = d.groupby(["model", "region"]).ape.mean()
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(14, 5), gridspec_kw={"width_ratios": [1.3, 1]})
    labels = [k[0].split("-")[0].capitalize() + "\n" + REGION[k[1]] for k in mape.index]
    ax.bar(range(len(mape)), mape.values, 0.6, color=BLUE)
    for i, v in enumerate(mape.values):
        ax.text(i, v - 0.8, f"{v:.0f}%", ha="center", va="top", fontsize=10, color="white", fontweight="bold")
    ax.axhline(20, color=INK2, lw=1, ls=":", label="Bài báo: ARIMA-60 ~20%")
    ax.set_ylim(0, mape.max() * 1.3)
    ax.legend(loc="upper left")
    ax.set_xticks(range(len(mape)), labels)
    ax.set_ylabel("MAPE đỉnh giờ (%)")
    ax.set_title(f"Sai số dự báo đỉnh giờ – trung bình {d.ape.mean():.1f}%", loc="left", fontsize=11)
    lim = max(d.actual_peak_tpm.max(), d.pred_peak_tpm.max()) / 1e3 * 1.05
    for mo, col in [("bloom-176b", BLUE), ("llama2-70b", ORANGE)]:
        x = d[d.model == mo]
        ax2.scatter(x.actual_peak_tpm / 1e3, x.pred_peak_tpm / 1e3, s=36, color=col, edgecolor=SURFACE, linewidth=1,
                    label=mo.split("-")[0].capitalize())
    ax2.plot([0, lim], [0, lim], color=INK2, lw=1, ls="--")
    ax2.text(lim * 0.30, lim * 0.36, "dự báo = thực tế", ha="right", fontsize=9, color=INK2)
    ax2.text(lim * 0.97, lim * 0.05, "điểm dưới đường chéo = dự báo thấp hơn thực tế", ha="right", fontsize=9, color=INK2)
    ax2.set_xlim(0, lim); ax2.set_ylim(0, lim)
    ax2.set_xlabel("Đỉnh TPM thực tế (nghìn)"); ax2.set_ylabel("Đỉnh TPM dự báo (nghìn)")
    ax2.set_title("Mỗi điểm = 1 giờ × 1 vùng", loc="left", fontsize=11)
    ax2.legend(loc="upper left")
    fig.suptitle("Độ chính xác của Load Predictor (đại lượng ILP dùng để chọn số instance mỗi giờ)", x=0.01, ha="left", fontsize=12)
    save(fig, out, "5_forecast_error")
    mape.round(1).rename("mape_dinh_gio_%").to_csv(f"{out}_sai_so_du_bao.csv")
    print("[+]", f"{out}_sai_so_du_bao.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("task", choices=["nv1", "nv2"])
    ap.add_argument("run_a")
    ap.add_argument("run_b")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    (nv1 if a.task == "nv1" else nv2)(a.run_a, a.run_b, a.out)
